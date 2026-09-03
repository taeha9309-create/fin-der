"""Financial-brand impersonation features backed by an auditable CSV registry."""

from __future__ import annotations

import csv
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

BRANDS_PATH = Path(__file__).resolve().parents[1] / "data" / "financial_brands.csv"
KOREAN_PUBLIC_SUFFIXES = {"co.kr", "or.kr", "go.kr", "ac.kr", "ne.kr", "re.kr"}


@lru_cache(maxsize=1)
def load_brands(path: str = str(BRANDS_PATH)) -> tuple[dict[str, object], ...]:
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = []
        for row in csv.DictReader(stream):
            rows.append({
                **row,
                "keywords": tuple(value.strip().lower() for value in row["keywords"].split("|") if value.strip()),
            })
    return tuple(rows)


def registered_domain(hostname: str) -> str:
    host = hostname.lower().strip(".")
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in KOREAN_PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def analyze_financial_domain(raw_url: str) -> dict[str, object]:
    url = raw_url if "://" in raw_url else f"http://{raw_url}"
    parsed = urlsplit(url)
    domain = registered_domain(parsed.hostname or "")
    searchable = raw_url.lower()
    best: dict[str, object] | None = None
    best_keyword = ""

    for brand in load_brands():
        for keyword in brand["keywords"]:
            if keyword in searchable and len(keyword) > len(best_keyword):
                best, best_keyword = brand, keyword

    official_domains = {str(item["official_domain"]).lower() for item in load_brands()}
    official_match = domain in official_domains
    expected_domain = str(best["official_domain"]).lower() if best else ""
    similarity = SequenceMatcher(None, domain, expected_domain).ratio() if expected_domain else 0.0
    return {
        "registered_domain": domain,
        "matched_brand": str(best["brand"]) if best else "",
        "matched_keyword": best_keyword,
        "expected_official_domain": expected_domain,
        "official_domain_match": official_match,
        "brand_domain_similarity": similarity,
        "brand_domain_mismatch": bool(best and domain != expected_domain),
    }
