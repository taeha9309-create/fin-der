"""Load and search the curated Korean financial/public brand reference."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable


REFERENCE_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_reference.json"


def normalize_brand_text(value: str) -> str:
    """Normalize aliases while preserving Korean and Latin letters and digits."""
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value).casefold())


@lru_cache(maxsize=1)
def load_brand_reference() -> tuple[dict, ...]:
    try:
        raw = REFERENCE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RuntimeError(f"Brand reference file is missing: {REFERENCE_PATH}") from error
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Brand reference JSON is invalid: {REFERENCE_PATH}: {error}") from error
    if not isinstance(entries, list):
        raise RuntimeError(f"Brand reference root must be a list: {REFERENCE_PATH}")
    required = {"brand", "category", "officialDomains", "aliases"}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not required.issubset(entry):
            raise RuntimeError(f"Brand reference entry {index} has an invalid structure")
    return tuple(entries)


def _text_sources(value: str | Iterable[str]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else tuple(str(item or "") for item in value)


def brand_alias_match_count(text: str | Iterable[str], alias: str) -> int:
    """Count alias matches without joining independent text sources."""
    sources = _text_sources(text)
    normalized_alias = normalize_brand_text(alias)
    if not normalized_alias:
        return 0
    if len(normalized_alias) <= 3 and normalized_alias.isascii() and normalized_alias.isalpha():
        pattern = re.compile(
            rf"(?<![0-9a-z]){re.escape(normalized_alias)}(?![0-9a-z])",
            re.IGNORECASE,
        )
        return sum(len(pattern.findall(source.casefold())) for source in sources)
    return sum(normalize_brand_text(source).count(normalized_alias) for source in sources)


def find_brand_candidates(text: str | Iterable[str]) -> list[dict]:
    sources = _text_sources(text)
    candidates = []
    for entry in load_brand_reference():
        matches = []
        for alias in entry["aliases"]:
            if brand_alias_match_count(sources, alias):
                matches.append(alias)
        if matches:
            candidates.append({**entry, "matchedAliases": matches})
    return candidates


def get_brand_by_name(name: str) -> dict | None:
    normalized = normalize_brand_text(name)
    return next(
        (entry for entry in load_brand_reference() if normalize_brand_text(entry["brand"]) == normalized),
        None,
    )


def get_official_domains(brand: str) -> list[str]:
    entry = get_brand_by_name(brand)
    return list(entry["officialDomains"]) if entry else []
