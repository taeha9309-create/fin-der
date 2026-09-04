"""Deterministic DOM behavior signal extraction; this module does not classify pages."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from .brand_reference import brand_alias_match_count, find_brand_candidates
except ImportError:
    from brand_reference import brand_alias_match_count, find_brand_candidates


SIGNAL_ORDER = (
    "PASSWORD_FIELD", "OTP_FIELD", "PHONE_FIELD", "RESIDENT_NUMBER_FIELD",
    "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD", "EMAIL_FIELD", "USER_ID_FIELD",
    "POST_FORM", "EXTERNAL_FORM_ACTION", "BRAND_IMPERSONATION",
    "BRAND_DOMAIN_MISMATCH", "EXTERNAL_CONTACT", "DOWNLOAD_REQUEST",
    "URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE", "BENEFIT_LURE",
    "FINANCIAL_ACTION_REQUEST",
)
CREDENTIAL_SIGNALS = {
    "PASSWORD": "PASSWORD_FIELD", "OTP": "OTP_FIELD", "PHONE": "PHONE_FIELD",
    "RESIDENT_NUMBER": "RESIDENT_NUMBER_FIELD", "ACCOUNT_NUMBER": "ACCOUNT_FIELD",
    "CARD_NUMBER": "CARD_FIELD", "PIN": "PIN_FIELD", "EMAIL": "EMAIL_FIELD",
    "USER_ID": "USER_ID_FIELD",
}
CREDENTIAL_PATTERNS = {
    "OTP": ("otp", "인증번호", "일회용비밀번호", "onetimepassword"),
    "RESIDENT_NUMBER": ("주민등록번호", "주민번호", "residentnumber", "rrn"),
    "ACCOUNT_NUMBER": ("계좌번호", "accountnumber", "bankaccount"),
    "CARD_NUMBER": ("카드번호", "cardnumber", "creditcardnumber"),
    "PHONE": ("휴대폰번호", "휴대전화번호", "전화번호", "phonenumber", "mobile", "tel"),
    "PIN": ("핀번호", "pin", "pincode"),
    "EMAIL": ("이메일", "email", "emailaddress"),
    "USER_ID": ("아이디", "userid", "username", "loginid"),
}
TEXT_SIGNALS = {
    "URGENCY_MESSAGE": ("즉시", "긴급", "지금바로", "오늘까지", "오늘마감", "30분이내", "제한시간", "기한내"),
    "ACCOUNT_SUSPENSION_MESSAGE": ("계좌정지", "계좌가정지", "계정정지", "계정이정지", "거래제한", "이용제한", "계좌가잠깁니다", "인증하지않으면정지"),
    "BENEFIT_LURE": ("지원금", "환급금", "보상금", "대출승인", "저금리", "특별지원", "정부지원금"),
    "FINANCIAL_ACTION_REQUEST": ("송금", "이체", "입금", "계좌번호입력", "카드정보입력", "대출신청", "수수료납부"),
}
CONTACT_PATTERNS = ("kakao", "카카오톡", "telegram", "텔레그램", "open.kakao.com", "t.me", "whatsapp", "line", "상담", "문의")
DOWNLOAD_SUFFIXES = {".apk", ".exe", ".msi", ".dmg", ".pkg", ".zip"}
MULTIPART_SUFFIXES = ("co.kr", "or.kr", "go.kr", "ne.kr", "ac.kr", "re.kr")


def _normalized(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())


def registrable_domain(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"//{value}")
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    if not hostname:
        return None
    labels = hostname.split(".")
    if len(labels) <= 2 or re.fullmatch(r"[0-9.]+", hostname):
        return hostname
    suffix_length = 2 if any(hostname.endswith(f".{suffix}") or hostname == suffix for suffix in MULTIPART_SUFFIXES) else 1
    return ".".join(labels[-(suffix_length + 1):])


def _credential_types(inputs: list[dict], forms: list[dict]) -> list[str]:
    combined = list(inputs)
    for form in forms:
        combined.extend(form.get("inputs") or [])
    found = set()
    for item in combined:
        input_type = _normalized(item.get("type"))
        if input_type == "password":
            found.add("PASSWORD")
        if input_type in {"tel", "telephone"}:
            found.add("PHONE")
        if input_type == "email":
            found.add("EMAIL")
        searchable = _normalized(" ".join(str(item.get(key) or "") for key in ("type", "name", "id", "placeholder", "label", "autocomplete")))
        for credential_type, patterns in CREDENTIAL_PATTERNS.items():
            if any(_normalized(pattern) in searchable for pattern in patterns):
                found.add(credential_type)
    return [item for item in CREDENTIAL_SIGNALS if item in found]


def analyze_dom_risk(input_data: dict) -> dict:
    final_url = input_data.get("final_url") or input_data.get("original_url") or ""
    inputs = input_data.get("inputs") or []
    forms = input_data.get("forms") or []
    links = input_data.get("links") or []
    dom_signals = input_data.get("dom_signals") or {}
    buttons = dom_signals.get("buttons") or []
    text_parts = [input_data.get("title", ""), input_data.get("page_text", ""), input_data.get("html", ""), *buttons]
    text_parts.extend(link.get("text", "") for link in links)
    full_text = " ".join(str(part or "") for part in text_parts)
    normalized_text = _normalized(full_text)

    candidates = find_brand_candidates(text_parts)
    candidates.sort(key=lambda item: (
        -sum(brand_alias_match_count(text_parts, alias) for alias in item["matchedAliases"]),
        item["brand"],
    ))
    primary = candidates[0] if candidates else None
    current_domain = registrable_domain(final_url)
    official_domains = list(primary["officialDomains"]) if primary else []
    mismatch = bool(primary and current_domain and official_domains and all(current_domain != registrable_domain(domain) for domain in official_domains))

    credential_types = _credential_types(inputs, forms)
    found_signals = {CREDENTIAL_SIGNALS[item] for item in credential_types}
    external_form_actions = []
    for form in forms:
        if str(form.get("method") or "").upper() == "POST":
            found_signals.add("POST_FORM")
        action = form.get("action")
        if action:
            action_url = urljoin(final_url, action)
            action_domain = registrable_domain(action_url)
            if current_domain and action_domain and action_domain != current_domain:
                found_signals.add("EXTERNAL_FORM_ACTION")
                external_form_actions.append(action_url)

    external_contacts = []
    for link in links:
        href = str(link.get("href") or link.get("destination") or "")
        label = str(link.get("text") or "")
        contact_text = f"{label} {href}".casefold()
        contact_hint = any(pattern in contact_text for pattern in CONTACT_PATTERNS)
        contact_scheme = urlparse(href).scheme.casefold() in {"tel", "sms"}
        contact_host = (urlparse(href).hostname or "").casefold() in {"open.kakao.com", "t.me", "wa.me"}
        if contact_scheme or contact_host or contact_hint and registrable_domain(href) not in {None, current_domain}:
            found_signals.add("EXTERNAL_CONTACT")
            external_contacts.append({"text": label, "href": href})

    network = input_data.get("network") or {}
    downloads = dom_signals.get("downloads") or input_data.get("downloads") or []
    download_detected = bool(network.get("download_detected") or network.get("downloadDetected") or downloads)
    if not download_detected:
        download_detected = any(Path(urlparse(str(link.get("href") or link.get("destination") or "")).path).suffix.casefold() in DOWNLOAD_SUFFIXES for link in links)
    if download_detected:
        found_signals.add("DOWNLOAD_REQUEST")
    if primary:
        found_signals.add("BRAND_IMPERSONATION")
    if mismatch:
        found_signals.add("BRAND_DOMAIN_MISMATCH")
    for signal, patterns in TEXT_SIGNALS.items():
        if any(_normalized(pattern) in normalized_text for pattern in patterns):
            found_signals.add(signal)

    return {
        "impersonation": {
            "detected": primary is not None,
            "brand": primary["brand"] if primary else None,
            "category": primary["category"] if primary else None,
            "matchedAliases": primary["matchedAliases"] if primary else [],
            "candidateBrands": [
                {"brand": item["brand"], "category": item["category"], "matchedAliases": item["matchedAliases"]}
                for item in candidates
            ],
        },
        "credentialIntent": {"detected": bool(credential_types), "types": credential_types},
        "domainAnalysis": {
            "currentDomain": current_domain,
            "officialDomains": official_domains,
            "domainBrandMismatch": mismatch,
            "redirectDomains": [domain for domain in (registrable_domain(url) for url in input_data.get("redirect_chain") or []) if domain],
        },
        "behaviorAnalysis": {
            "financialActionRequest": "FINANCIAL_ACTION_REQUEST" in found_signals,
            "externalContactRequest": "EXTERNAL_CONTACT" in found_signals,
            "downloadRequest": download_detected,
        },
        "detectedSignals": [signal for signal in SIGNAL_ORDER if signal in found_signals],
        "evidenceMetadata": {"externalFormActions": external_form_actions, "externalContacts": external_contacts},
    }
