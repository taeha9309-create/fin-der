"""Parsing, legacy adaptation, and validation for Gemini responses."""

import json
import re

from pydantic import ValidationError

try:
    from .schemas import AnalyzeResponse
except ImportError:  # Direct script/fixture execution from app/.
    from schemas import AnalyzeResponse


def _contains_any(values: list[str], keywords: tuple[str, ...]) -> bool:
    text = " ".join(str(value).lower() for value in values)
    return any(keyword in text for keyword in keywords)


def _adapt_legacy_response(payload: dict) -> dict:
    """Convert the original nested analyzer contract without discarding old results."""
    legacy = payload.get("multimodal_result")
    if not isinstance(legacy, dict):
        return payload

    score = legacy.get("multimodal_risk_score", 0)
    is_impersonation = legacy.get("is_financial_impersonation") is True
    risk_level = str(legacy.get("risk_level", "")).lower()
    if is_impersonation and (score >= 70 or risk_level == "high_risk_suspected"):
        verdict = "PHISHING"
    elif score >= 40 or is_impersonation:
        verdict = "SUSPICIOUS"
    else:
        verdict = "NORMAL"

    category = str(legacy.get("brand_category") or "").lower()
    attack_type = str(legacy.get("attack_type") or "").lower()
    if category in {"bank", "card", "capital", "savings_bank"}:
        impersonation_type = "FINANCIAL_INSTITUTION"
    elif attack_type == "government_support_scam":
        impersonation_type = "GOVERNMENT_SUPPORT"
    elif attack_type == "loan_scam":
        impersonation_type = "POLICY_FUND"
    elif attack_type in {"credential_theft", "financial_information_theft"}:
        impersonation_type = "GENERIC_CREDENTIAL_THEFT"
    elif is_impersonation:
        impersonation_type = "OTHER"
    else:
        impersonation_type = "UNKNOWN"

    elements = [str(value) for value in legacy.get("detected_elements", [])]
    reason_objects = legacy.get("reasons", [])
    evidence = [
        str(reason.get("description"))
        for reason in reason_objects
        if isinstance(reason, dict) and reason.get("description")
    ]
    if not evidence:
        evidence = ["분석 가능한 위험 근거가 발견되지 않았습니다."]

    return {
        "verdict": verdict,
        "risk_score": score,
        "impersonation_type": impersonation_type,
        "impersonated_brand": legacy.get("impersonated_brand"),
        "credential_request": attack_type in {
            "credential_theft",
            "financial_information_theft",
        }
        or _contains_any(elements, ("password", "otp", "credential", "resident_number")),
        "financial_action_request": attack_type in {
            "loan_scam",
            "government_support_scam",
        }
        or _contains_any(elements, ("loan", "transfer", "payment", "account_input")),
        "app_install_request": attack_type == "malicious_app_install"
        or _contains_any(elements, ("apk", "app_install", "remote_control")),
        "external_contact_request": _contains_any(
            elements, ("kakao", "telegram", "phone_contact", "external_contact")
        ),
        "evidence": evidence,
    }


def parse_multimodal_response(response_text: str) -> dict:
    """Parse plain or fenced JSON and enforce the public response contract."""
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("Multimodal response is empty")

    cleaned = response_text.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Multimodal response is not valid JSON: {error.msg}"
        ) from error

    try:
        validated = AnalyzeResponse.model_validate(_adapt_legacy_response(result))
    except ValidationError as error:
        missing = [
            ".".join(str(part) for part in item["loc"])
            for item in error.errors()
            if item["type"] == "missing"
        ]
        if missing:
            raise ValueError(
                "Multimodal response is missing required fields: " + ", ".join(missing)
            ) from error
        raise ValueError(
            f"Multimodal response does not match the required schema: {error}"
        ) from error

    return validated.model_dump(mode="json")
