import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from response_parser import parse_multimodal_response


def valid_response() -> dict:
    return {
        "verdict": "PHISHING",
        "risk_score": 92,
        "impersonation_type": "POLICY_FUND",
        "impersonated_brand": "서민금융진흥원",
        "credential_request": True,
        "financial_action_request": True,
        "app_install_request": False,
        "external_contact_request": True,
        "evidence": ["주민등록번호 입력 필드와 카카오톡 상담 버튼이 발견되었습니다."],
    }


def test_parse_plain_json():
    assert parse_multimodal_response(json.dumps(valid_response())) == valid_response()


def test_parse_fenced_json_with_whitespace():
    payload = "  ```json\n" + json.dumps(valid_response()) + "\n```  "
    assert parse_multimodal_response(payload)["verdict"] == "PHISHING"


def test_invalid_json_has_clear_error():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_multimodal_response("{not-json}")


def test_missing_required_field_has_clear_error():
    payload = valid_response()
    del payload["evidence"]
    with pytest.raises(ValueError, match="missing required fields.*evidence"):
        parse_multimodal_response(json.dumps(payload))


def test_boolean_fields_must_be_json_booleans():
    payload = valid_response()
    payload["credential_request"] = "true"
    with pytest.raises(ValueError, match="does not match the required schema"):
        parse_multimodal_response(json.dumps(payload))


def test_legacy_nested_response_is_adapted():
    legacy = {
        "analysis_id": "old-1",
        "status": "completed",
        "multimodal_result": {
            "multimodal_risk_score": 95,
            "risk_level": "high_risk_suspected",
            "is_financial_impersonation": True,
            "impersonated_brand": "정부24",
            "brand_category": "government",
            "attack_type": "government_support_scam",
            "detected_elements": ["account_password_input"],
            "reasons": [{"code": "RISK", "description": "계좌 비밀번호 입력을 요구합니다."}],
            "confidence": 0.99,
        },
        "model_name": "gemini-3.1-flash-lite-preview",
        "prompt_version": "mm_prompt_v1",
    }
    result = parse_multimodal_response(json.dumps(legacy))
    assert result["verdict"] == "PHISHING"
    assert result["impersonation_type"] == "GOVERNMENT_SUPPORT"
    assert result["credential_request"] is True
