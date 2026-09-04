"""Shared, network-free helpers for public dataset adapters."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit

VALID_LABELS = {"BENIGN", "PHISHING"}
VALID_SPLITS = {"train", "validation", "test", "holdout"}

# These patterns describe executable markup, not ordinary uses of words such as
# "script" in visible prose.  Keep this validator independent from antivirus:
# it is a final fail-closed check on every generated record.
EXECUTABLE_PATTERNS = (
    re.compile(r"<\s*/?\s*script\b", re.IGNORECASE),
    re.compile(r"\bjavascript\s*:", re.IGNORECASE),
    re.compile(r"\bdata\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"\bblob\s*:", re.IGNORECASE),
    re.compile(r"\bon[a-z][a-z0-9_-]*\s*=", re.IGNORECASE),
    re.compile(r"<\s*/?\s*(?:iframe|object|embed|svg)\b", re.IGNORECASE),
    re.compile(r"\beval\s*\(", re.IGNORECASE),
    re.compile(r"\bdocument\s*\.\s*write\s*\(", re.IGNORECASE),
    re.compile(r"\bwindow\s*\.\s*location\b", re.IGNORECASE),
    re.compile(r"\bfunction(?:\s+[A-Za-z_$][\w$]*)?\s*\(", re.IGNORECASE),
    re.compile(r"\batob\s*\(", re.IGNORECASE),
    re.compile(r"\bfromCharCode\s*\(", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z0-9+/]{200,}={0,2})"),
)


def sanitize_inert_text(value: str) -> str:
    """Remove validator-blocked residues from statically extracted text."""
    for pattern in EXECUTABLE_PATTERNS:
        value = pattern.sub("", value)
    return value


class UnsafeContentError(ValueError):
    """Raised when generated output still contains executable-looking content."""


@dataclass
class AdapterStats:
    discovered: int = 0
    converted: int = 0
    skipped: int = 0
    errors: int = 0
    duplicates: int = 0
    messages: list[str] = field(default_factory=list)


@dataclass
class AdapterResult:
    records: list[dict[str, Any]]
    stats: AdapterStats


def normalized_url(value: str) -> str:
    """Normalize a URL as text only; this function performs no DNS or I/O."""
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http(s) and include a hostname")
    host = parsed.hostname.casefold().rstrip(".")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL contains an invalid port") from error
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit(SplitResult(scheme, netloc, path, parsed.query, ""))


def deterministic_split(url: str) -> str:
    """Assign a stable 80/10/5/5 split without inspecting page content."""
    bucket = int(hashlib.sha256(normalized_url(url).encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    if bucket < 95:
        return "test"
    return "holdout"


def inert_record(
    *,
    sample_id: str,
    source: str,
    label: str,
    url: str,
    final_url: str | None = None,
    split: str,
    title: str = "",
    visible_text: str = "",
    inputs: list[dict[str, Any]] | None = None,
    forms: list[dict[str, Any]] | None = None,
    links: list[dict[str, Any]] | None = None,
    brand: str | None = None,
    credential_types: list[str] | None = None,
    domain_brand_mismatch: bool | None = None,
    status_code: int | None = None,
) -> dict[str, Any]:
    if label not in VALID_LABELS:
        raise ValueError(f"unsupported label: {label!r}")
    if split not in VALID_SPLITS:
        raise ValueError(f"unsupported split: {split!r}")
    normalized = normalized_url(url)
    normalized_final = normalized_url(final_url) if final_url else None
    record = {
        "sampleId": sample_id,
        "source": source,
        "split": split,
        "label": label,
        "input": {
            "analysisId": sample_id,
            "requestedUrl": normalized,
            "finalUrl": normalized_final,
            "statusCode": status_code,
            "page": {"title": title, "visibleText": visible_text, "html": ""},
            "inputs": inputs or [],
            "forms": forms or [],
            "links": links or [],
            "network": {"requestDomains": [], "downloadDetected": False},
            "redirectChain": [],
            "screenshot": {"available": False, "url": None},
            "error": None,
        },
        "expected": {
            "brand": brand,
            "credentialTypes": credential_types or [],
            "domainBrandMismatch": domain_brand_mismatch,
        },
    }
    validate_inert_record(record)
    return record


def validate_inert_record(record: dict[str, Any]) -> None:
    page = ((record.get("input") or {}).get("page") or {})
    if page.get("html") != "":
        raise UnsafeContentError("page.html must be empty for public dataset records")
    serialized = json.dumps(record, ensure_ascii=False)
    for pattern in EXECUTABLE_PATTERNS:
        if pattern.search(serialized):
            raise UnsafeContentError(f"executable-looking content matched {pattern.pattern!r}")


def deduplicate(records: Iterable[dict[str, Any]], stats: AdapterStats) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        raw_url = record["input"].get("finalUrl") or record["input"].get("requestedUrl")
        url = normalized_url(raw_url)
        if url in seen:
            stats.duplicates += 1
            continue
        seen.add(url)
        unique.append(record)
    return unique


def write_manifest(path: Path, records: Iterable[dict[str, Any]]) -> None:
    checked = list(records)
    for record in checked:
        validate_inert_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in checked),
        encoding="utf-8",
    )
