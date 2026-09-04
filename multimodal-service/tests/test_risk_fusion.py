import json
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "app"))

from dom_risk_analyzer import analyze_dom_risk
from risk_fusion import fuse_analysis

CASES = json.loads((SERVICE_DIR / "fixtures" / "dom_rules" / "cases.json").read_text(encoding="utf-8"))


def semantic(risk, impersonation=False):
    return {"semanticRisk": risk, "impersonationContext": impersonation,
            "credentialHarvestingContext": risk == "HIGH", "socialEngineeringContext": risk == "HIGH",
            "financialManipulationContext": False, "semanticEvidence": [], "confidence": 0.9}


def result(case=None, semantic_result=None, **payload):
    source = {"inputs": [], "forms": [], "links": [], "dom_signals": {}, **(CASES.get(case, {}) if case else {}), **payload}
    rule = analyze_dom_risk(source)
    status = {"analysis_id": source.get("analysis_id", case or "test"), "html": source.get("html", ""),
              "visible_text": source.get("page_text", ""), "inputs": source.get("inputs", []),
              "forms": source.get("forms", []), "links": source.get("links", []), "status_code": 200}
    return fuse_analysis(rule, semantic_result, status)


def test_official_kb_login_is_normal_and_not_impersonation():
    fused = result("official_bank", semantic_result=semantic("LOW"), final_url="https://obank.kbstar.com/",
                   inputs=[{"name": "user_id"}, {"type": "password"}],
                   forms=[{"method": "POST", "action": "https://obank.kbstar.com/login"}])
    assert fused["pageRiskScore"] <= 20 and fused["verdict"] == "NORMAL"
    assert fused["impersonation"]["detected"] is False


def test_fake_kb_is_phishing_with_fact_grounded_reasons():
    fused = result("fake_bank", semantic_result=semantic("HIGH", True))
    assert fused["pageRiskScore"] >= 60 and fused["verdict"] == "PHISHING"
    assert fused["impersonation"]["detected"] is True
    assert any("공식 도메인" in reason for reason in fused["reasons"])
    assert any("비밀번호와 OTP" in reason for reason in fused["reasons"])


def test_generic_login_remains_normal():
    fused = result("generic_login", semantic_result=semantic("MEDIUM"), inputs=[{"name": "user_id"}, {"type": "password"}],
                   forms=[{"method": "POST", "action": "/login"}])
    assert fused["pageRiskScore"] <= 29 and fused["verdict"] == "NORMAL"


def test_government_benefit_is_at_least_suspicious():
    fused = result("government_benefit", semantic_result=semantic("MEDIUM"))
    assert fused["pageRiskScore"] >= 30 and fused["verdict"] in {"SUSPICIOUS", "PHISHING"}


def test_external_form_contact_and_download_raise_rule_signals():
    external = result(semantic_result=semantic("MEDIUM"), final_url="https://example.com", page_text="login",
                      inputs=[{"type": "password"}], forms=[{"method": "POST", "action": "https://collector.example.net/submit"}])
    assert "EXTERNAL_FORM_ACTION" in external["detectedSignals"] and external["verdict"] == "SUSPICIOUS"
    assert "EXTERNAL_CONTACT" in result("external_contact", semantic_result=semantic("MEDIUM"))["detectedSignals"]
    assert "DOWNLOAD_REQUEST" in result("download", semantic_result=semantic("MEDIUM"), page_text="download")["detectedSignals"]


def test_empty_collection_is_unknown():
    rule = analyze_dom_risk({"inputs": [], "forms": [], "links": [], "dom_signals": {}})
    fused = fuse_analysis(rule, None, {"analysis_id": "failed", "error": "timeout"})
    assert fused["verdict"] == "UNKNOWN" and fused["pageRiskScore"] == 0 and fused["confidence"] == 0


def test_semantic_adjustment_is_bounded_both_directions():
    weak = result("generic_login", semantic_result=semantic("HIGH", True))
    strong = result("fake_bank", semantic_result=semantic("LOW"))
    assert weak["pageRiskScore"] <= 29 and weak["verdict"] == "NORMAL"
    assert strong["pageRiskScore"] >= 60 and strong["verdict"] == "PHISHING"
    assert weak["detectedSignals"] == ["PASSWORD_FIELD"]


def test_score_confidence_and_rule_facts_are_bounded_and_canonical():
    fused = result("fake_bank", semantic_result=semantic("HIGH", True))
    rule_domain = analyze_dom_risk(CASES["fake_bank"])["domainAnalysis"]
    assert 0 <= fused["pageRiskScore"] <= 100 and 0 <= fused["confidence"] <= 1
    assert fused["domainAnalysis"] == {key: rule_domain[key] for key in ("currentDomain", "officialDomains", "domainBrandMismatch")}
