import base64, sys
from pathlib import Path
from fastapi.testclient import TestClient
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "app"))
import main
from schemas import AnalyzeResponse
client = TestClient(main.app)
OUTPUT_FIELDS = {"analysisId", "pageRiskScore", "verdict", "impersonation", "credentialIntent", "domainAnalysis", "behaviorAnalysis", "domSummary", "detectedSignals", "reasons", "confidence"}

def test_health_does_not_require_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/health").json()["gemini_api_key_configured"] is False

def test_collection_failure_returns_unknown(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    body = client.post("/v1/analyze", json={"analysisId": "failed", "requestedUrl": "https://blocked.example", "error": "CAPTCHA"}).json()
    assert body["analysisId"] == "failed" and body["verdict"] == "UNKNOWN"

def test_canonical_nested_payload_runs_rule_only(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = client.post("/v1/analyze", json={"analysisId": "fake-1", "requestedUrl": "https://kb-secure.example/login", "finalUrl": "https://kb-secure.example/login", "statusCode": 200, "page": {"title": "KB국민은행 보안 인증", "visibleText": "계정 인증", "html": ""}, "inputs": [{"type": "password"}, {"name": "otp", "label": "OTP 인증번호"}], "forms": [], "links": [], "network": {}, "redirectChain": []})
    assert response.status_code == 200 and response.json()["verdict"] == "PHISHING"
    assert {"PASSWORD_FIELD", "OTP_FIELD", "BRAND_DOMAIN_MISMATCH"} <= set(response.json()["detectedSignals"])

def test_flat_fallback_and_screenshot_are_accepted(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    screenshot = (SERVICE_DIR / "fixtures" / "fake_bank" / "test.png").read_bytes()
    response = client.post("/v1/analyze", json={"url": "https://example.com", "title": "Login", "html": "<form><input type='password'></form>", "screenshotBase64": base64.b64encode(screenshot).decode("ascii")})
    assert response.status_code == 200 and response.json()["verdict"] == "NORMAL"

def test_gemini_error_falls_back_to_rules(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    def fail(_): raise RuntimeError("down")
    monkeypatch.setattr(main, "analyze", fail)
    response = client.post("/v1/analyze", json={"requestedUrl": "https://example.com", "html": "<p>content</p>"})
    assert response.status_code == 200 and response.json()["verdict"] == "NORMAL"

def test_invalid_base64_returns_422():
    assert client.post("/v1/analyze", json={"url": "https://example.com", "screenshot": "bad!"}).status_code == 422

def test_response_model_has_only_latest_contract_fields():
    assert set(AnalyzeResponse.model_fields) == OUTPUT_FIELDS
