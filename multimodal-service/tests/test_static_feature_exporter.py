import json
import socket
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from evaluation.adapters.common import validate_inert_record
from evaluation.adapters.safe_html import extract_features
from evaluation.exporters.static_feature_exporter import ExportConfig, export_jsonl


SYNTHETIC_HTML = """<!doctype html>
<html><head>
  <title>Example Account</title>
  <style>.hidden { display: none }</style>
  <meta http-equiv="refresh" content="0; url=javascript:placeholder()">
</head><body onanimationstart="placeholder()">
  <p>Verify your account details</p>
  <form method="POST" action="https://submit.example.invalid/session" onsubmit="placeholder()">
    <label for="password">Password</label>
    <input type="password" name="password" id="password" placeholder="Enter password">
    <label>One-time code<input type="text" name="otp" id="otp" autocomplete="one-time-code"></label>
  </form>
  <a href="https://help.example.invalid/">Help</a>
  <a href="javascript:placeholder()">Continue</a>
  <a href="data:text/html,placeholder">Data</a>
  <a href="blob:https://example.invalid/id">Blob</a>
  <p>Encoded AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA</p>
  <p>Documentation residue: function example() and javascript: are inert text.</p>
  <script>function placeholder(){ eval('placeholder'); window.location='https://example.invalid'; }</script>
  <iframe src="https://frame.example.invalid/">Frame payload</iframe>
  <svg onload="placeholder()"><text>SVG payload</text></svg>
</body></html>"""


def _config():
    return ExportConfig(
        source="public-example",
        dataset_name="example/inert-test",
        dataset_revision="revision-1",
        source_split="test",
        extraction_timestamp="2026-09-03T00:00:00Z",
        benign_label="benign",
        phishing_label="phish",
    )


def _write_source(path):
    row = {
        "sha256": "a" * 64,
        "url": "https://page.example.invalid/login",
        "label": "phish",
        "targetBrand": "Example Brand",
        "html": SYNTHETIC_HTML,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_static_exporter_extracts_features_and_removes_executable_content(tmp_path, monkeypatch):
    source = tmp_path / "source.jsonl"
    output = tmp_path / "output.jsonl"
    _write_source(source)

    def block_network(*args, **kwargs):
        raise AssertionError("exporter attempted network access")

    monkeypatch.setattr(socket, "create_connection", block_network)
    result = export_jsonl(source, output, _config())

    assert result.stats.converted == 1
    record = result.records[0]
    page = record["input"]["page"]
    assert page["title"] == "Example Account"
    assert "Verify your account details" in page["visibleText"]
    assert all(text not in page["visibleText"] for text in (
        "placeholder()", "Frame payload", "SVG payload", "A" * 200,
        "function example()", "javascript:",
    ))
    assert page["html"] == ""
    assert record["input"]["statusCode"] is None
    assert record["input"]["finalUrl"] is None

    password, otp = record["input"]["inputs"]
    assert password == {
        "type": "password", "name": "password", "id": "password",
        "placeholder": "Enter password", "autocomplete": None, "label": "Password",
    }
    assert otp["name"] == "otp" and otp["label"] == "One-time code"
    assert otp["autocomplete"] == "one-time-code"
    assert record["input"]["forms"][0]["method"] == "POST"
    assert record["input"]["forms"][0]["action"] == "https://submit.example.invalid/session"
    assert record["input"]["links"] == [
        {"text": "Help", "href": "https://help.example.invalid/"},
        {"text": "Continue", "href": None},
        {"text": "Data", "href": None},
        {"text": "Blob", "href": None},
    ]
    assert record["provenance"]["featureAvailability"]["rawHtmlStored"] is False
    assert record["provenance"]["featureAvailability"]["javascriptExecuted"] is False
    validate_inert_record(record)


def test_static_exporter_is_deterministic_with_fixed_provenance(tmp_path):
    source = tmp_path / "source.jsonl"
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_source(source)
    export_jsonl(source, first, _config())
    export_jsonl(source, second, _config())
    assert first.read_bytes() == second.read_bytes()


def test_static_extraction_preserves_financial_and_login_analysis_context():
    features = extract_features(
        "<p>금융 로그인 즉시 계정 정지 송금 이체 계좌번호 입력 "
        "카드정보 입력 대출 신청 상담 문의</p>"
    )
    assert features.visible_text == (
        "금융 로그인 즉시 계정 정지 송금 이체 계좌번호 입력 "
        "카드정보 입력 대출 신청 상담 문의"
    )


def test_static_exporter_source_has_no_network_browser_or_subprocess_capability():
    source = (SERVICE_DIR / "evaluation" / "exporters" / "static_feature_exporter.py").read_text(encoding="utf-8")
    forbidden = (
        "import requests", "import httpx", "import urllib.request", "import socket",
        "import subprocess", "playwright", "selenium", "urlopen(", "page.goto(",
        "driver.get(",
    )
    assert all(token not in source.casefold() for token in forbidden)
