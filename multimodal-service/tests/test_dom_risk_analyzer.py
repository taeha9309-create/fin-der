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


def test_brand_mention_keeps_candidate_without_impersonation_signals():
    result = analyze_dom_risk({
        "final_url": "https://news.example.com/article",
        "page_text": "KB국민은행의 예금 금리를 비교합니다.",
        "inputs": [], "forms": [], "links": [], "dom_signals": {},
    })
    assert result["impersonation"]["brand"] == "KB국민은행"
    assert result["impersonation"]["detected"] is False
    assert "BRAND_IMPERSONATION" not in result["detectedSignals"]
    assert "BRAND_DOMAIN_MISMATCH" not in result["detectedSignals"]


def test_comparison_page_can_keep_multiple_candidates_without_impersonation():
    result = analyze_dom_risk({
        "final_url": "https://finance.example.com/cards",
        "page_text": "신한카드와 현대카드 혜택을 비교합니다.",
        "inputs": [], "forms": [], "links": [], "dom_signals": {},
    })
    brands = {candidate["brand"] for candidate in result["impersonation"]["candidateBrands"]}
    assert {"신한카드", "현대카드"} <= brands
    assert result["impersonation"]["detected"] is False
    assert "BRAND_DOMAIN_MISMATCH" not in result["detectedSignals"]


def test_synthetic_bank_impersonation_still_has_mismatch():
    result = analyze_dom_risk({
        "final_url": "https://kb-auth.test.invalid/",
        "title": "KB국민은행 보안 인증",
        "inputs": [{"type": "password"}, {"name": "otp"}],
        "forms": [{"method": "POST", "action": "https://collector.test.invalid/submit"}],
        "links": [], "dom_signals": {},
    })
    assert result["impersonation"]["brand"] == "KB국민은행"
    assert result["impersonation"]["detected"] is True
    assert {"BRAND_IMPERSONATION", "BRAND_DOMAIN_MISMATCH"} <= set(result["detectedSignals"])


def test_benign_ecommerce_boilerplate_does_not_trigger_text_signals():
    # Regression for BUG-06: generic UI/legal copy ("즉시 사용", "이용제한",
    # "무통장입금") used to trip URGENCY_MESSAGE / ACCOUNT_SUSPENSION_MESSAGE /
    # FINANCIAL_ACTION_REQUEST on virtually any ordinary Korean shopping page.
    result = analyze_dom_risk({
        "final_url": "https://example-shop.co.kr/product/123",
        "title": "겨울 니트 원피스 - 무료배송",
        "page_text": (
            "겨울 신상 니트 원피스 할인 이벤트. 5만원 이상 구매 시 무료배송, 무통장입금 시 당일 발송. "
            "적립금 즉시 사용 가능. 교환/환불은 이용약관에 따라 이용제한될 수 있습니다."
        ),
        "inputs": [], "forms": [], "links": [], "dom_signals": {},
    })
    assert not {"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE", "FINANCIAL_ACTION_REQUEST"} & set(result["detectedSignals"])


def test_text_signals_ignore_raw_html_markup_noise():
    # Regression for BUG-06: TEXT_SIGNALS must only scan user-visible text
    # (title/page_text/buttons/links), not the raw HTML source, since markup,
    # class names, and boilerplate footers can contain a keyword by accident.
    result = analyze_dom_risk({
        "final_url": "https://example.com/",
        "title": "일반 페이지",
        "page_text": "평범한 내용입니다.",
        "html": "<footer class='account-suspension-notice'>부정 이용 시 계좌가 정지됩니다.</footer>",
        "inputs": [], "forms": [], "links": [], "dom_signals": {},
    })
    assert "ACCOUNT_SUSPENSION_MESSAGE" not in result["detectedSignals"]


def test_security_vendor_block_page_is_detected_from_title():
    # Regression for BUG-07: a Cloudflare "Suspected Phishing" (or Google Safe
    # Browsing "Deceptive site ahead") interstitial means a third party has
    # already confirmed the domain is malicious, even though the interstitial
    # itself has no password fields or brand mismatch to key off of.
    result = analyze_dom_risk({
        "final_url": "https://bancaribe.pages.dev/",
        "title": "Suspected Phishing | Cloudflare",
        "page_text": "",
        "inputs": [], "forms": [{"method": "GET", "action": "https://bancaribe.pages.dev/cdn-cgi/phish-bypass"}],
        "links": [], "dom_signals": {},
    })
    assert "SECURITY_VENDOR_BLOCKED" in result["detectedSignals"]


def test_government_mention_and_synthetic_impersonation_are_separated():
    mention = analyze_dom_risk({"final_url": "https://news.example.com/tax",
        "page_text": "국세청이 새로운 세금 신고 일정을 발표했습니다.",
        "inputs": [], "forms": [], "links": [], "dom_signals": {}})
    phishing = analyze_dom_risk({"final_url": "https://refund.test.invalid/",
        "page_text": "국세청 환급금 지급을 위해 본인 인증이 필요합니다.",
        "inputs": [{"name": "account_number"}],
        "forms": [{"method": "POST", "action": "/claim"}], "links": [], "dom_signals": {}})
    assert mention["impersonation"]["brand"] == "국세청"
    assert mention["impersonation"]["detected"] is False
    assert "BRAND_DOMAIN_MISMATCH" not in mention["detectedSignals"]
    assert phishing["impersonation"]["detected"] is True
    assert "BRAND_DOMAIN_MISMATCH" in phishing["detectedSignals"]
