import json
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "app"))

from dom_risk_analyzer import SIGNAL_ORDER, analyze_dom_risk, registrable_domain


CASES = json.loads((SERVICE_DIR / "fixtures" / "dom_rules" / "cases.json").read_text(encoding="utf-8"))


def analyze(case, **updates):
    payload = {"inputs": [], "forms": [], "links": [], "dom_signals": {}, **CASES.get(case, {}), **updates}
    return analyze_dom_risk(payload)


def test_official_bank_subdomain_is_not_a_mismatch():
    result = analyze("official_bank", final_url="https://obank.kbstar.com/login")
    assert result["impersonation"]["brand"] == "KB국민은행"
    assert result["credentialIntent"]["types"] == ["PASSWORD"]
    assert "PASSWORD_FIELD" in result["detectedSignals"]
    assert result["domainAnalysis"]["domainBrandMismatch"] is False
    assert "BRAND_DOMAIN_MISMATCH" not in result["detectedSignals"]


def test_fake_bank_detects_credentials_mismatch_and_social_engineering():
    result = analyze("fake_bank")
    assert result["credentialIntent"]["types"] == ["PASSWORD", "OTP"]
    assert {"BRAND_DOMAIN_MISMATCH", "URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE"} <= set(result["detectedSignals"])


def test_generic_password_login_has_no_brand_or_mismatch_and_no_verdict_fields():
    result = analyze("generic_login")
    assert result["detectedSignals"] == ["PASSWORD_FIELD"]
    assert result["impersonation"]["detected"] is False
    assert result["domainAnalysis"]["domainBrandMismatch"] is False
    assert not {"verdict", "pageRiskScore", "risk_score", "confidence", "reasons"} & result.keys()


def test_all_required_sensitive_input_types_are_detected_and_deduplicated():
    result = analyze_dom_risk({
        "inputs": [
            {"type": "tel", "name": "phone"}, {"label": "주민등록번호", "name": "rrn"},
            {"placeholder": "계좌번호", "name": "account_number"}, {"label": "카드번호", "name": "card_number"},
            {"type": "password"}, {"type": "password", "name": "password"},
        ],
        "forms": [], "links": [], "dom_signals": {},
    })
    assert result["credentialIntent"]["types"] == ["PASSWORD", "PHONE", "RESIDENT_NUMBER", "ACCOUNT_NUMBER", "CARD_NUMBER"]
    assert len(result["detectedSignals"]) == len(set(result["detectedSignals"]))


def test_post_and_external_form_action_compare_registrable_domains():
    same = analyze_dom_risk({"final_url": "https://login.bank.example.com", "inputs": [], "links": [], "forms": [{"method": "POST", "action": "https://www.bank.example.com/submit"}]})
    assert "POST_FORM" in same["detectedSignals"]
    assert "EXTERNAL_FORM_ACTION" not in same["detectedSignals"]
    external = analyze_dom_risk({"final_url": "https://bank.example.com", "inputs": [], "links": [], "forms": [{"method": "post", "action": "https://collector.example.net/submit"}]})
    assert "EXTERNAL_FORM_ACTION" in external["detectedSignals"]


def test_benefit_urgency_financial_action_and_account_field():
    signals = analyze("government_benefit")["detectedSignals"]
    assert {"BENEFIT_LURE", "URGENCY_MESSAGE", "FINANCIAL_ACTION_REQUEST", "ACCOUNT_FIELD"} <= set(signals)


def test_external_contact_and_download_sources():
    assert "EXTERNAL_CONTACT" in analyze("external_contact")["detectedSignals"]
    assert "DOWNLOAD_REQUEST" in analyze("download")["detectedSignals"]
    link_download = analyze_dom_risk({"final_url": "https://example.com", "inputs": [], "forms": [], "links": [{"href": "/installer.exe"}]})
    assert "DOWNLOAD_REQUEST" in link_download["detectedSignals"]


def test_signal_order_is_deterministic():
    first = analyze("fake_bank")["detectedSignals"]
    second = analyze("fake_bank")["detectedSignals"]
    assert first == second
    assert first == [signal for signal in SIGNAL_ORDER if signal in first]


def test_brand_detection_does_not_join_separate_text_sources():
    result = analyze_dom_risk({
        "final_url": "https://example.com",
        "title": "My Account",
        "page_text": "Sale",
        "inputs": [], "forms": [], "links": [], "dom_signals": {},
    })
    assert result["impersonation"]["brand"] is None
    assert "BRAND_IMPERSONATION" not in result["detectedSignals"]
    assert "BRAND_DOMAIN_MISMATCH" not in result["detectedSignals"]


def test_registrable_domain_handles_korean_suffixes_and_subdomains():
    assert registrable_domain("https://card.nonghyup.com") == "nonghyup.com"
    assert registrable_domain("https://service.ibk.co.kr") == "ibk.co.kr"
