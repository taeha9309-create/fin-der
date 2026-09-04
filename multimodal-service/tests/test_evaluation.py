import json
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR / "evaluation"))

from run_evaluation import (ManifestError, classification_metrics, collect_cases,
                            evaluate_sample, load_manifest, run_evaluation,
                            score_overlap, score_statistics, verdict_distribution)

MANIFEST = SERVICE_DIR / "evaluation" / "datasets" / "baseline_manifest.jsonl"


def prediction(label, verdict, score=0):
    return {"sampleId": f"{label}-{verdict}", "source": "test", "label": label,
            "verdict": verdict, "pageRiskScore": score, "detectedSignals": [], "reasons": []}


def write_manifest(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def sample(sample_id="one", label="BENIGN"):
    return {"sampleId": sample_id, "source": "test", "split": "test", "label": label,
            "input": {"analysisId": sample_id, "requestedUrl": "https://example.test",
                      "page": {"title": "plain", "visibleText": "content", "html": "<p>content</p>"}}}


def test_manifest_loads_and_has_expected_baseline_size():
    rows, warnings = load_manifest(MANIFEST)
    assert len(rows) == 18 and not warnings


def test_duplicate_sample_id_is_rejected(tmp_path):
    path = tmp_path / "data.jsonl"; write_manifest(path, [sample(), sample()])
    with pytest.raises(ManifestError, match="duplicate sampleId"): load_manifest(path)


def test_invalid_label_is_rejected(tmp_path):
    path = tmp_path / "data.jsonl"; write_manifest(path, [sample(label="MAYBE")])
    with pytest.raises(ManifestError, match="invalid label"): load_manifest(path)


def test_malformed_json_reports_line(tmp_path):
    path = tmp_path / "data.jsonl"; path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ManifestError, match="line 1"): load_manifest(path)


def test_strict_metrics_abstain_on_suspicious_and_unknown():
    rows = [prediction("PHISHING", "PHISHING"), prediction("BENIGN", "NORMAL"),
            prediction("BENIGN", "PHISHING"), prediction("PHISHING", "NORMAL"),
            prediction("PHISHING", "SUSPICIOUS"), prediction("BENIGN", "UNKNOWN")]
    result = classification_metrics(rows, "strict")
    assert (result["tp"], result["tn"], result["fp"], result["fn"]) == (1, 1, 1, 1)
    assert result["abstainCount"] == 2 and result["coverage"] == 0.6667


def test_alert_metrics_include_suspicious_positive_and_unknown_abstains():
    rows = [prediction("PHISHING", "SUSPICIOUS"), prediction("BENIGN", "SUSPICIOUS"),
            prediction("BENIGN", "NORMAL"), prediction("PHISHING", "UNKNOWN")]
    result = classification_metrics(rows, "alert")
    assert (result["tp"], result["tn"], result["fp"], result["fn"]) == (1, 1, 1, 0)
    assert result["abstainCount"] == 1


def test_metrics_are_zero_division_safe():
    result = classification_metrics([prediction("PHISHING", "UNKNOWN")], "strict")
    assert result["accuracy"] == result["precision"] == result["recall"] == result["f1"] == 0.0


def test_score_statistics_and_percentiles():
    rows = [prediction("BENIGN", "NORMAL", 0), prediction("BENIGN", "NORMAL", 20), prediction("PHISHING", "PHISHING", 80)]
    stats = score_statistics(rows)
    assert stats["BENIGN"]["mean"] == stats["BENIGN"]["median"] == 10
    assert stats["PHISHING"]["p90"] == 80


def test_score_overlap_reports_intersecting_ranges():
    rows = [prediction("BENIGN", "NORMAL", 10), prediction("BENIGN", "NORMAL", 40),
            prediction("PHISHING", "PHISHING", 30), prediction("PHISHING", "PHISHING", 80)]
    assert score_overlap(rows) == {
        "available": True, "overlaps": True, "lower": 30, "upper": 40,
        "benignMax": 40, "phishingMin": 30,
    }


def test_verdict_distribution_is_by_label():
    result = verdict_distribution([prediction("BENIGN", "NORMAL"), prediction("BENIGN", "SUSPICIOUS")])
    assert result["BENIGN"]["NORMAL"] == {"count": 1, "rate": 0.5}


def test_false_positive_false_negative_and_review_collection():
    errors, reviews = collect_cases([prediction("BENIGN", "PHISHING"), prediction("PHISHING", "NORMAL"), prediction("PHISHING", "SUSPICIOUS")])
    assert [row["errorType"] for row in errors] == ["FALSE_POSITIVE", "FALSE_NEGATIVE"]
    assert reviews[0]["reviewType"] == "SUSPICIOUS"


def test_rule_only_is_deterministic_and_needs_no_provider():
    row = load_manifest(MANIFEST)[0][0]
    assert evaluate_sample(row, "rule-only") == evaluate_sample(row, "rule-only")


@pytest.mark.parametrize("mode", ["mock-low", "mock-high"])
def test_deterministic_semantic_modes(mode):
    row = load_manifest(MANIFEST)[0][0]
    assert evaluate_sample(row, mode)["verdict"] in {"NORMAL", "SUSPICIOUS", "PHISHING", "UNKNOWN"}


def test_run_writes_summary_report_and_jsonl(tmp_path):
    run_dir, summary = run_evaluation(MANIFEST, "rule-only", tmp_path, "fixed", split="test", limit=2)
    assert summary["sampleCount"] == 2
    assert {"summary.json", "report.md", "predictions.jsonl", "errors.jsonl", "review_cases.jsonl"} == {p.name for p in run_dir.iterdir()}
    assert "Strict Metrics" in (run_dir / "report.md").read_text(encoding="utf-8")
    assert "Synthetic fixture performance is not an estimate" in (run_dir / "report.md").read_text(encoding="utf-8")
    assert "static URL metadata" in (run_dir / "report.md").read_text(encoding="utf-8")
    json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def test_runner_source_contains_no_network_client():
    source = (SERVICE_DIR / "evaluation" / "run_evaluation.py").read_text(encoding="utf-8")
    assert all(token not in source for token in ("requests.get(", "urllib.request", "playwright", "httpx."))
