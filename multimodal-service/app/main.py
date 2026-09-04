"""Connect collected page facts to deterministic rules, optional Gemini, and fusion."""
from __future__ import annotations
import base64, binascii, tempfile, uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException

try:
    from .analyzer import analyze
    from .config import Settings
    from .dom_risk_analyzer import analyze_dom_risk
    from .risk_fusion import fuse_analysis
    from .schemas import AnalyzeRequest, AnalyzeResponse
except ImportError:
    from analyzer import analyze
    from config import Settings
    from dom_risk_analyzer import analyze_dom_risk
    from risk_fusion import fuse_analysis
    from schemas import AnalyzeRequest, AnalyzeResponse

app = FastAPI(title="fin-der Multimodal Service", version="3.0.0")

def _clean_text(value: str) -> str:
    return " ".join(value.split())

def extract_dom_context(html: str, base_url: str | None) -> dict:
    if not html:
        return {"visible_text": "", "forms": [], "buttons": [], "links": [], "downloads": []}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    forms = []
    for form in soup.find_all("form", limit=50):
        inputs = [{key: element.get(key) for key in ("type", "name", "id", "autocomplete", "placeholder")}
                  for element in form.find_all(["input", "select", "textarea"], limit=100)]
        forms.append({"action": urljoin(base_url or "", form.get("action", "")),
                      "method": str(form.get("method", "get")).upper(), "inputs": inputs})
    buttons = [_clean_text(e.get_text(" ", strip=True) or e.get("value", ""))
               for e in soup.find_all(["button", "input"], limit=100)
               if e.name == "button" or e.get("type") in {"button", "submit"}]
    links, downloads = [], []
    suffixes = {".apk", ".exe", ".msi", ".dmg", ".pkg", ".zip"}
    for anchor in soup.find_all("a", href=True, limit=200):
        destination = urljoin(base_url or "", anchor["href"])
        item = {"text": _clean_text(anchor.get_text(" ", strip=True)), "destination": destination}
        links.append(item)
        if anchor.has_attr("download") or Path(urlparse(destination).path).suffix.lower() in suffixes:
            downloads.append(item)
    return {"visible_text": _clean_text(soup.get_text(" ", strip=True)), "forms": forms,
            "buttons": [v for v in buttons if v], "links": links, "downloads": downloads}

def _decode_screenshot(value: str, max_bytes: int) -> bytes:
    encoded = value.strip()
    if encoded.startswith("data:"):
        try:
            header, encoded = encoded.split(",", 1)
        except ValueError as error:
            raise HTTPException(422, "Invalid screenshot data URI") from error
        if ";base64" not in header.lower():
            raise HTTPException(422, "Screenshot data URI must be base64")
    if len(encoded) > ((max_bytes + 2) // 3) * 4 + 8:
        raise HTTPException(413, "Screenshot exceeds size limit")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "Invalid screenshot base64") from error
    if not decoded:
        raise HTTPException(422, "Screenshot is empty")
    if len(decoded) > max_bytes:
        raise HTTPException(413, "Screenshot exceeds size limit")
    return decoded

def _semantic_view(result: dict | None) -> dict | None:
    """Adapt the existing Gemini contract to the bounded fusion hints."""
    if not result:
        return None
    if "semanticRisk" in result:
        return result
    score = int(result.get("risk_score", 0))
    return {
        "semanticRisk": "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW",
        "impersonationContext": bool(result.get("impersonated_brand")),
        "credentialHarvestingContext": bool(result.get("credential_request")),
        "socialEngineeringContext": result.get("verdict") in {"SUSPICIOUS", "PHISHING"},
        "financialManipulationContext": bool(result.get("financial_action_request")),
        "semanticEvidence": list(result.get("evidence") or []),
        "confidence": 0.7,
    }

@app.get("/health")
def health() -> dict[str, object]:
    settings = Settings.from_env()
    return {"status": "UP", "service": "multimodal-service", "model": settings.gemini_model,
            "gemini_api_key_configured": settings.gemini_api_key is not None}

@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    settings = Settings.from_env()
    title, visible_text, html = request.page_values()
    if len(html.encode("utf-8")) > settings.max_html_bytes:
        raise HTTPException(413, "HTML exceeds size limit")
    final_url = request.final_url or request.requested_url or ""
    dom = extract_dom_context(html, final_url)
    screenshot_value = request.screenshot if isinstance(request.screenshot, str) else None
    screenshot_bytes = _decode_screenshot(screenshot_value, settings.max_screenshot_bytes) if screenshot_value else None
    redirect_urls = [item.get("url", "") if isinstance(item, dict) else str(item) for item in request.redirect_chain]
    input_data = {
        "analysis_id": request.analysis_id or uuid.uuid4().hex,
        "original_url": request.requested_url or final_url, "final_url": final_url,
        "status_code": request.status_code, "title": title, "page_text": visible_text or dom["visible_text"],
        "html": html, "inputs": [item.model_dump() for item in request.inputs],
        "forms": [item.model_dump() for item in request.forms] or dom["forms"],
        "links": [item.model_dump() for item in request.links] or dom["links"],
        "network": request.network.model_dump() if request.network else {}, "redirect_chain": redirect_urls,
        "dom_signals": {"buttons": dom["buttons"], "links": [item.model_dump() for item in request.links] or dom["links"], "downloads": dom["downloads"]},
    }
    rule_result = analyze_dom_risk(input_data)
    tmp_path, semantic_result = None, None
    try:
        if screenshot_bytes is not None:
            with tempfile.NamedTemporaryFile(prefix="multimodal-", suffix=".img", delete=False) as tmp:
                tmp.write(screenshot_bytes)
                tmp_path = Path(tmp.name)
            input_data["screenshot_path"] = str(tmp_path)
        if settings.gemini_api_key is not None:
            try:
                semantic_result = _semantic_view(analyze(input_data))
            except Exception:
                semantic_result = None
        collection_status = {
            "analysis_id": input_data["analysis_id"], "html": html, "visible_text": input_data["page_text"],
            "inputs": input_data["inputs"], "forms": input_data["forms"], "links": input_data["links"],
            "status_code": request.status_code, "screenshot": bool(screenshot_bytes),
            "semantic_available": semantic_result is not None, "error": request.error,
        }
        return AnalyzeResponse.model_validate(fuse_analysis(rule_result, semantic_result, collection_status))
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
