"""Deterministic policy that fuses rule facts with bounded semantic context."""

from __future__ import annotations

from typing import Any


SIGNAL_WEIGHTS = {
    "BRAND_DOMAIN_MISMATCH": 30,
    "PASSWORD_FIELD": 8,
    "OTP_FIELD": 12,
    "RESIDENT_NUMBER_FIELD": 15,
    "ACCOUNT_FIELD": 12,
    "CARD_FIELD": 15,
    "PIN_FIELD": 10,
    "PHONE_FIELD": 4,
    "EMAIL_FIELD": 1,
    "USER_ID_FIELD": 2,
    "POST_FORM": 3,
    "EXTERNAL_FORM_ACTION": 12,
    "EXTERNAL_CONTACT": 8,
    "DOWNLOAD_REQUEST": 10,
    "URGENCY_MESSAGE": 8,
    "ACCOUNT_SUSPENSION_MESSAGE": 10,
    "BENEFIT_LURE": 6,
    "FINANCIAL_ACTION_REQUEST": 10,
    # This rule signal means a brand candidate was found, not proven impersonation.
    "BRAND_IMPERSONATION": 1,
}

SYNERGY_WEIGHTS = {
    "MISMATCH_AUTH": 15,
    "MISMATCH_SENSITIVE": 15,
    "URGENCY_SUSPENSION": 8,
    "MISMATCH_CONTACT": 8,
    "BENEFIT_FINANCIAL": 8,
    "EXTERNAL_FORM_CREDENTIAL": 10,
    "DOWNLOAD_INSTITUTION": 8,
}

NORMAL_MAX = 29
SUSPICIOUS_MAX = 59
SEMANTIC_ADJUSTMENTS = {"LOW": -8, "MEDIUM": 0, "HIGH": 8}
OFFICIAL_SAFE_CAP = 20
UNKNOWN_REASON = "페이지 정보를 충분히 수집하지 못해 위험 여부를 판단할 수 없습니다."

AUTH_SIGNALS = {"PASSWORD_FIELD", "OTP_FIELD"}
SENSITIVE_SIGNALS = {
    "RESIDENT_NUMBER_FIELD", "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD"
}
CREDENTIAL_SIGNALS = {
    "PASSWORD_FIELD", "OTP_FIELD", "PHONE_FIELD", "RESIDENT_NUMBER_FIELD",
    "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD", "EMAIL_FIELD", "USER_ID_FIELD",
}
INDEPENDENT_HIGH_RISK = {
    "EXTERNAL_FORM_ACTION", "EXTERNAL_CONTACT", "DOWNLOAD_REQUEST",
    "FINANCIAL_ACTION_REQUEST",
}


def collection_is_analyzable(collection_status: dict[str, Any] | None) -> bool:
    """Collection errors are tolerated only when objective page facts remain."""
    status = collection_status or {}
    return any(
        bool(status.get(key))
        for key in ("html", "visible_text", "inputs", "forms", "links")
    ) or bool(status.get("screenshot") and status.get("semantic_available"))


def _score(signals: set[str]) -> int:
    score = sum(SIGNAL_WEIGHTS.get(signal, 0) for signal in signals)
    if "BRAND_DOMAIN_MISMATCH" in signals and signals & AUTH_SIGNALS:
        score += SYNERGY_WEIGHTS["MISMATCH_AUTH"]
    if "BRAND_DOMAIN_MISMATCH" in signals and signals & SENSITIVE_SIGNALS:
        score += SYNERGY_WEIGHTS["MISMATCH_SENSITIVE"]
    if {"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE"} <= signals:
        score += SYNERGY_WEIGHTS["URGENCY_SUSPENSION"]
    if {"BRAND_DOMAIN_MISMATCH", "EXTERNAL_CONTACT"} <= signals:
        score += SYNERGY_WEIGHTS["MISMATCH_CONTACT"]
    if {"BENEFIT_LURE", "FINANCIAL_ACTION_REQUEST"} <= signals:
        score += SYNERGY_WEIGHTS["BENEFIT_FINANCIAL"]
    if "EXTERNAL_FORM_ACTION" in signals and signals & CREDENTIAL_SIGNALS:
        score += SYNERGY_WEIGHTS["EXTERNAL_FORM_CREDENTIAL"]
    if "DOWNLOAD_REQUEST" in signals and "BRAND_IMPERSONATION" in signals:
        score += SYNERGY_WEIGHTS["DOWNLOAD_INSTITUTION"]
    return score


def _semantic_adjustment(semantic: dict[str, Any] | None) -> int:
    if not semantic:
        return 0
    return SEMANTIC_ADJUSTMENTS.get(str(semantic.get("semanticRisk", "")).upper(), 0)


def _is_official_safe_context(rule: dict[str, Any], signals: set[str]) -> bool:
    domain = rule.get("domainAnalysis") or {}
    return bool(
        rule.get("impersonation", {}).get("brand")
        and domain.get("currentDomain")
        and domain.get("officialDomains")
        and not domain.get("domainBrandMismatch")
        and not (signals & INDEPENDENT_HIGH_RISK)
        and not ({"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE"} <= signals)
    )


def _reasons(rule: dict[str, Any], signals: set[str], semantic: dict[str, Any] | None) -> list[str]:
    brand = rule.get("impersonation", {}).get("brand") or "탐지된 기관"
    reasons: list[str] = []
    if "BRAND_DOMAIN_MISMATCH" in signals:
        reasons.append(f"{brand}의 공식 도메인과 현재 접속 도메인이 일치하지 않습니다.")
    if {"PASSWORD_FIELD", "OTP_FIELD"} <= signals:
        reasons.append("비밀번호와 OTP 인증번호 입력을 요구합니다.")
    elif "PASSWORD_FIELD" in signals:
        reasons.append("비밀번호 입력 필드가 확인되었습니다.")
    elif "OTP_FIELD" in signals:
        reasons.append("OTP 인증번호 입력을 요구합니다.")
    credential_templates = (
        ("RESIDENT_NUMBER_FIELD", "주민등록번호 입력을 요구합니다."),
        ("ACCOUNT_FIELD", "계좌번호 입력을 요구합니다."),
        ("CARD_FIELD", "카드번호 입력을 요구합니다."),
        ("PIN_FIELD", "PIN 또는 비밀번호 입력을 요구합니다."),
    )
    for signal, text in credential_templates:
        if signal in signals:
            reasons.append(text)
            break
    templates = (
        ("EXTERNAL_FORM_ACTION", "입력 정보가 현재 사이트와 다른 외부 도메인으로 전송될 수 있습니다."),
        ("EXTERNAL_CONTACT", "외부 상담 또는 메신저 채널로 이동을 유도합니다."),
        ("DOWNLOAD_REQUEST", "파일 또는 프로그램 다운로드를 유도하는 정황이 확인되었습니다."),
        ("ACCOUNT_SUSPENSION_MESSAGE", "계정 또는 계좌 이용 제한을 경고하는 문구가 확인되었습니다."),
        ("URGENCY_MESSAGE", "즉시 행동을 요구하는 긴급성 문구가 확인되었습니다."),
        ("BENEFIT_LURE", "지원금·환급금·대출 등 금전적 혜택을 강조하는 문구가 확인되었습니다."),
        ("FINANCIAL_ACTION_REQUEST", "송금·이체·계좌정보 입력 등 금융 행동을 요구합니다."),
    )
    for signal, text in templates:
        if signal in signals and text not in reasons:
            reasons.append(text)
        if len(reasons) >= 5:
            break
    if len(reasons) < 3 and semantic:
        for item in semantic.get("semanticEvidence") or []:
            text = str(item).strip()
            if text and text not in reasons:
                reasons.append(text)
            if len(reasons) >= 3:
                break
    return reasons[:5] or ["분석 가능한 고위험 행동 신호가 발견되지 않았습니다."]


def _confidence(signals: set[str], rule: dict[str, Any], semantic: dict[str, Any] | None,
                collection_status: dict[str, Any]) -> float:
    completeness = sum(bool(collection_status.get(key)) for key in
                       ("html", "visible_text", "inputs", "forms", "links", "status_code")) / 6
    categories = sum(bool(signals & group) for group in (
        CREDENTIAL_SIGNALS, {"BRAND_DOMAIN_MISMATCH"},
        {"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE", "BENEFIT_LURE"},
        INDEPENDENT_HIGH_RISK,
    ))
    value = 0.35 + 0.25 * completeness + min(0.18, len(signals) * 0.025) + min(0.12, categories * 0.03)
    if rule.get("domainAnalysis", {}).get("domainBrandMismatch"):
        value += 0.05
    if semantic:
        semantic_confidence = max(0.0, min(1.0, float(semantic.get("confidence", 0.0))))
        value += 0.05 * semantic_confidence
        rule_level = "HIGH" if _score(signals) >= 60 else "MEDIUM" if _score(signals) >= 30 else "LOW"
        semantic_level = str(semantic.get("semanticRisk", "MEDIUM")).upper()
        value += 0.04 if rule_level == semantic_level else -0.04
    else:
        value -= 0.08
    return round(max(0.0, min(1.0, value)), 2)


def fuse_analysis(rule_analysis: dict[str, Any], gemini_analysis: dict[str, Any] | None,
                  collection_status: dict[str, Any]) -> dict[str, Any]:
    analysis_id = str(collection_status.get("analysis_id") or "unknown")
    if not collection_is_analyzable(collection_status):
        return {
            "analysisId": analysis_id, "pageRiskScore": 0, "verdict": "UNKNOWN",
            "impersonation": {"detected": False, "brand": None, "category": None},
            "credentialIntent": {"detected": False, "types": []},
            "domainAnalysis": {"currentDomain": None, "officialDomains": [], "domainBrandMismatch": False},
            "behaviorAnalysis": {"financialActionRequest": False, "externalContactRequest": False, "downloadRequest": False},
            "detectedSignals": [], "reasons": [UNKNOWN_REASON], "confidence": 0.0,
        }

    ordered_signals = list(rule_analysis.get("detectedSignals") or [])
    signals = set(ordered_signals)
    score = _score(signals) + _semantic_adjustment(gemini_analysis)
    if _is_official_safe_context(rule_analysis, signals):
        score = min(score, OFFICIAL_SAFE_CAP)
    score = max(0, min(100, score))
    verdict = "NORMAL" if score <= NORMAL_MAX else "SUSPICIOUS" if score <= SUSPICIOUS_MAX else "PHISHING"
    candidate = rule_analysis.get("impersonation") or {}
    semantic_impersonation = bool(gemini_analysis and gemini_analysis.get("impersonationContext"))
    impersonation_detected = bool(candidate.get("brand") and (
        rule_analysis.get("domainAnalysis", {}).get("domainBrandMismatch") or semantic_impersonation
    ))
    return {
        "analysisId": analysis_id,
        "pageRiskScore": score,
        "verdict": verdict,
        "impersonation": {"detected": impersonation_detected, "brand": candidate.get("brand"), "category": candidate.get("category")},
        "credentialIntent": rule_analysis.get("credentialIntent") or {"detected": False, "types": []},
        "domainAnalysis": {key: (rule_analysis.get("domainAnalysis") or {}).get(key) for key in ("currentDomain", "officialDomains", "domainBrandMismatch")},
        "behaviorAnalysis": rule_analysis.get("behaviorAnalysis") or {},
        "detectedSignals": ordered_signals,
        "reasons": _reasons(rule_analysis, signals, gemini_analysis),
        "confidence": _confidence(signals, rule_analysis, gemini_analysis, collection_status),
    }
