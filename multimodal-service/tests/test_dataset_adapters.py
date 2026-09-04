import json
import socket
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "evaluation"))

from adapters.common import UnsafeContentError, inert_record, normalized_url, validate_inert_record
from adapters.phishintention_adapter import adapt_directory
from adapters.phishpedia_adapter import adapt_directory as adapt_phishpedia
from adapters.safe_html import extract_features


def test_safe_html_extracts_features_without_preserving_active_content():
    html = """<html><head><title>Account notice</title><style>hidden</style></head>
    <body onblur='bad()'><p>Verify your account</p>
    <form method='post' action='/login' onanimationstart='bad()'>
    <label>Password<input type='password' name='pw' onpointerenter='bad()'></label></form>
    <a href='javascript:bad()'>Continue</a><script>bad()</script>
    <iframe src='data:text/html,bad'>ignored</iframe></body></html>"""
    page = extract_features(html)
    assert page.title == "Account notice"
    assert page.visible_text == "Verify your account Password Continue"
    assert page.inputs[0]["type"] == "password"
    assert page.forms[0]["action"] == "/login"
    assert page.links == [{"text": "Continue", "href": None}]
    serialized = json.dumps(page.__dict__)
    assert "bad()" not in serialized and "data:text" not in serialized


def test_public_record_is_inert_and_does_not_invent_observations():
    record = inert_record(
        sample_id="public-1", source="phishintention", label="PHISHING",
        url="HTTPS://Example.Invalid:443/path/#fragment", split="test",
    )
    assert record["input"]["page"]["html"] == ""
    assert record["input"]["statusCode"] is None
    assert record["input"]["network"] == {"requestDomains": [], "downloadDetected": False}
    assert record["input"]["redirectChain"] == []
    assert record["expected"] == {
        "brand": None, "credentialTypes": [], "domainBrandMismatch": None,
    }
    assert record["input"]["finalUrl"] is None


@pytest.mark.parametrize(
    "payload",
    [
        "<script src=x>", "</script>", "javascript:run", "data:text/html,x", "blob:payload",
        "onload=x", "onclick=x", "onerror=x", "onmouseover=x", "<iframe>",
        "<object>", "<embed>", "eval(x)", "document.write(x)",
        "window.location=x", "window.location.href", "function run()", "atob(x)",
        "fromCharCode(x)", "A" * 220, "</iframe>", "<svg onload=x>",
        "onblur=run()", "onfocus = run()", "ONCLICK=run()",
        "onpointerenter = evil()", "onanimationstart=evil()",
    ],
)
def test_output_validator_rejects_executable_patterns(payload):
    record = inert_record(
        sample_id="safe", source="test", label="BENIGN",
        url="https://example.invalid", split="test",
    )
    record["input"]["page"]["visibleText"] = payload
    with pytest.raises(UnsafeContentError):
        validate_inert_record(record)


@pytest.mark.parametrize("text", ["online banking", "once verified"])
def test_output_validator_allows_benign_on_prefix_words(text):
    record = inert_record(
        sample_id="safe-text", source="test", label="BENIGN",
        url="https://example.invalid", split="test", visible_text=text,
    )
    validate_inert_record(record)


def test_public_record_uses_source_status_only_when_provided():
    record = inert_record(
        sample_id="with-status", source="test", label="BENIGN",
        url="https://example.invalid", split="test", status_code=204,
    )
    assert record["input"]["statusCode"] == 204


def test_public_record_uses_final_url_only_when_provided():
    without_final = inert_record(
        sample_id="without-final", source="test", label="BENIGN",
        url="https://requested.example.invalid", split="test",
    )
    with_final = inert_record(
        sample_id="with-final", source="test", label="BENIGN",
        url="https://requested.example.invalid", final_url="https://final.example.invalid/path",
        split="test",
    )
    assert without_final["input"]["finalUrl"] is None
    assert with_final["input"]["finalUrl"] == "https://final.example.invalid/path"


def test_phishintention_adapter_reads_local_metadata_only(tmp_path, monkeypatch):
    site = tmp_path / "case-1"
    site.mkdir()
    (site / "info.txt").write_text("https://archive.example.invalid/login", encoding="utf-8")
    (site / "html.txt").write_text("<title>Ignored by default</title>", encoding="utf-8")

    def block_network(*args, **kwargs):
        raise AssertionError("adapter attempted network access")

    monkeypatch.setattr(socket, "create_connection", block_network)
    result = adapt_directory(tmp_path, label="PHISHING")
    assert result.stats.converted == 1 and result.stats.errors == 0
    assert result.records[0]["input"]["page"] == {"title": "", "visibleText": "", "html": ""}


def test_phishpedia_adapter_uses_documented_url_metadata(tmp_path):
    site = tmp_path / "case-1"
    site.mkdir()
    (site / "info.txt").write_text("https://archive.example.invalid/", encoding="utf-8")
    result = adapt_phishpedia(tmp_path, label="PHISHING")
    assert result.records[0]["source"] == "phishpedia"
    assert result.records[0]["sampleId"] == "phishpedia-case-1"


def test_normalized_url_dedup_key_is_text_only():
    assert normalized_url("HTTPS://Example.COM:443/a/#x") == "https://example.com/a"


def test_adapter_modules_contain_no_network_or_browser_clients():
    adapter_dir = SERVICE_DIR / "evaluation" / "adapters"
    source = "\n".join(path.read_text(encoding="utf-8") for path in adapter_dir.glob("*.py"))
    forbidden = (
        "requests.get(", "httpx.get(", "urllib.request", "urlopen(",
        "page.goto(", "driver.get(", "socket.socket(", "subprocess.",
    )
    assert all(token not in source for token in forbidden)


def test_local_public_manifest_is_inert_if_present():
    manifest = SERVICE_DIR / "evaluation" / "local-data" / "real_public_url_only_manifest.jsonl"
    if not manifest.exists():
        pytest.skip("no safely acquired public manifest is checked in")
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    assert rows
    for row in rows:
        validate_inert_record(row)
