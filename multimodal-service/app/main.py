"""FastAPI boundary compatible with the current Sandbox response."""

from __future__ import annotations

import base64
import binascii
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException

try:
    from .analyzer import analyze
    from .config import Settings
    from .schemas import AnalyzeRequest, AnalyzeResponse, unknown_response
except ImportError:  # Uvicorn started from app/ as used by the Dockerfile.
    from analyzer import analyze
    from config import Settings
    from schemas import AnalyzeRequest, AnalyzeResponse, unknown_response

app = FastAPI(title="fin-der Multimodal Service", version="2.0.0")


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def extract_dom_context(html: str, base_url: str | None) -> dict:
    """Extract analysis signals without executing page code or fetching links."""
    if not html:
        return {"visible_text": "", "forms": [], "buttons": [], "links": [], "downloads": []}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    forms = []
    for form in soup.find_all("form", limit=50):
        inputs = []
        for element in form.find_all(["input", "select", "textarea"], limit=100):
            inputs.append({
                "type": element.get("type", element.name),
                "name": element.get("name"),
                "autocomplete": element.get("autocomplete"),
                "placeholder": element.get("placeholder"),
            })
        forms.append({
            "action": urljoin(base_url or "", form.get("action", "")),
            "method": str(form.get("method", "get")).upper(),
            "inputs": inputs,
        })

    buttons = [
        _clean_text(element.get_text(" ", strip=True) or element.get("value", ""))
        for element in soup.find_all(["button", "input"], limit=100)
        if element.name == "button" or element.get("type") in {"button", "submit"}
    ]
    buttons = [text for text in buttons if text]

    links = []
    downloads = []
    download_suffixes = {".apk", ".exe", ".msi", ".dmg", ".pkg", ".zip"}
    for anchor in soup.find_all("a", href=True, limit=200):
        destination = urljoin(base_url or "", anchor["href"])
        item = {"text": _clean_text(anchor.get_text(" ", strip=True)), "destination": destination}
        links.append(item)
        if anchor.has_attr("download") or Path(urlparse(destination).path).suffix.lower() in download_suffixes:
            downloads.append(item)

    return {
        "visible_text": _clean_text(soup.get_text(" ", strip=True)),
        "forms": forms,
        "buttons": buttons,
        "links": links,
        "downloads": downloads,
    }


def _decode_screenshot(value: str, max_bytes: int) -> bytes:
    encoded = value.strip()
    if encoded.startswith("data:"):
        try:
            header, encoded = encoded.split(",", 1)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="screenshotBase64 data URI가 올바르지 않습니다.") from error
        if ";base64" not in header.lower():
            raise HTTPException(status_code=422, detail="스크린샷 data URI는 Base64 형식이어야 합니다.")
    if len(encoded) > ((max_bytes + 2) // 3) * 4 + 8:
        raise HTTPException(status_code=413, detail="스크린샷이 허용 크기를 초과했습니다.")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="screenshotBase64 디코딩에 실패했습니다.") from error
    if not decoded:
        raise HTTPException(status_code=422, detail="스크린샷 데이터가 비어 있습니다.")
    if len(decoded) > max_bytes:
        raise HTTPException(status_code=413, detail="스크린샷이 허용 크기를 초과했습니다.")
    return decoded


@app.get("/health")
def health() -> dict[str, object]:
    current_settings = Settings.from_env()
    return {
        "status": "UP",
        "service": "multimodal-service",
        "model": current_settings.gemini_model,
        "gemini_api_key_configured": current_settings.gemini_api_key is not None,
    }


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    current_settings = Settings.from_env()
    if len(request.html.encode("utf-8")) > current_settings.max_html_bytes:
        raise HTTPException(status_code=413, detail="HTML이 허용 크기를 초과했습니다.")
    has_screenshot = bool(request.screenshot_base64 and request.screenshot_base64.strip())
    has_document = bool(request.html.strip() or request.visible_text.strip())

    if not has_screenshot and not has_document:
        if request.error:
            return unknown_response(f"Sandbox 수집 실패로 분석할 수 없습니다: {request.error}")
        return unknown_response("Screenshot과 HTML/Text가 없어 페이지를 분석할 수 없습니다.")

    if current_settings.gemini_api_key is None:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY가 설정되어 있지 않아 Gemini 분석을 수행할 수 없습니다.",
        )

    final_url = request.final_url or request.requested_url or ""
    dom = extract_dom_context(request.html, final_url)
    screenshot_bytes = (
        _decode_screenshot(request.screenshot_base64, current_settings.max_screenshot_bytes)
        if has_screenshot and request.screenshot_base64
        else None
    )

    tmp_path: Path | None = None
    try:
        if screenshot_bytes is not None:
            with tempfile.NamedTemporaryFile(prefix="multimodal-", suffix=".img", delete=False) as tmp_file:
                tmp_file.write(screenshot_bytes)
                tmp_path = Path(tmp_file.name)

        input_data = {
            "analysis_id": uuid.uuid4().hex,
            "original_url": request.requested_url or final_url,
            "final_url": final_url,
            "title": request.title,
            "screenshot_path": str(tmp_path) if tmp_path else None,
            "page_text": request.visible_text or dom["visible_text"],
            "html": request.html,
            "forms": request.forms or dom["forms"],
            "dom_signals": {
                "buttons": dom["buttons"],
                "links": dom["links"],
                "downloads": dom["downloads"],
            },
        }
        return AnalyzeResponse.model_validate(analyze(input_data))
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Gemini 분석 또는 응답 검증에 실패했습니다.",
        ) from error
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
