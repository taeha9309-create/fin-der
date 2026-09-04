import json
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "app"))

import brand_reference
from brand_reference import find_brand_candidates, get_brand_by_name, get_official_domains


def test_reference_json_is_utf8_and_has_required_entries():
    entries = json.loads((SERVICE_DIR / "data" / "brand_reference.json").read_text(encoding="utf-8"))
    assert len(entries) == 23
    assert {"KB국민은행", "토스뱅크", "NH농협카드", "정부24", "금융감독원"}.issubset(
        {entry["brand"] for entry in entries}
    )
    assert all({"brand", "category", "officialDomains", "aliases"} <= entry.keys() for entry in entries)


def test_alias_search_normalizes_case_spaces_and_punctuation():
    result = find_brand_candidates("Kakao-Bank를 사칭한 문구와 KB 국민은행 안내")
    assert {item["brand"] for item in result} >= {"카카오뱅크", "KB국민은행"}


@pytest.mark.parametrize(
    "text",
    (
        "contents", "events", "comments", "appointments", "treatments",
        "patients", "points", "prevents", "documents", "accounts",
    ),
)
def test_short_latin_acronym_does_not_match_inside_words(text):
    assert "국세청" not in {item["brand"] for item in find_brand_candidates(text)}


@pytest.mark.parametrize("text", ("NTS", "NTS login", "(NTS)", "NTS-portal", "nts"))
def test_short_latin_acronym_matches_complete_tokens(text):
    assert "국세청" in {item["brand"] for item in find_brand_candidates(text)}


def test_other_short_latin_acronyms_require_complete_tokens():
    assert not find_brand_candidates("prefixfsssuffix prefixfscsuffix")
    brands = {item["brand"] for item in find_brand_candidates("FSS notice and FSC portal")}
    assert {"금융감독원", "금융위원회"} <= brands


def test_brand_matching_preserves_source_boundaries():
    assert "국세청" not in {
        item["brand"] for item in find_brand_candidates(["My Account", "Sale"])
    }


@pytest.mark.parametrize(
    ("text", "brand"),
    (
        ("국세청 안내", "국세청"),
        ("KB국민은행", "KB국민은행"),
        ("국민은행", "KB국민은행"),
        ("shinhan bank", "신한은행"),
        ("kakaobank", "카카오뱅크"),
        ("Government24", "정부24"),
    ),
)
def test_korean_and_long_latin_aliases_still_match(text, brand):
    assert brand in {item["brand"] for item in find_brand_candidates(text)}


def test_brand_lookup_and_domains():
    assert get_brand_by_name("kb 국민은행")["category"] == "BANK"
    assert get_official_domains("KB국민은행") == ["kbstar.com"]
    assert get_official_domains("없는 기관") == []


def test_missing_reference_has_clear_error(monkeypatch, tmp_path):
    brand_reference.load_brand_reference.cache_clear()
    monkeypatch.setattr(brand_reference, "REFERENCE_PATH", tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="missing"):
        brand_reference.load_brand_reference()
    brand_reference.load_brand_reference.cache_clear()
