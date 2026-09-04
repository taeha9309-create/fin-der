"""Offline evaluation runner for the baseline-v1 page behavior pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

SERVICE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = SERVICE_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from dom_risk_analyzer import analyze_dom_risk  # noqa: E402
from risk_fusion import fuse_analysis  # noqa: E402
from schemas import AnalyzeRequest, AnalyzeResponse  # noqa: E402

VALID_LABELS = {"BENIGN", "PHISHING", "UNKNOWN", "SKIP"}
VALID_SPLITS = {"train", "validation", "test", "holdout"}
SEMANTIC_MODES = {"rule-only", "mock-low", "mock-medium", "mock-high"}
VERDICTS = ("NORMAL", "SUSPICIOUS", "PHISHING", "UNKNOWN")


class ManifestError(ValueError):
    pass


def load_manifest(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    samples: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    urls: dict[str, str] = {}
    warnings: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ManifestError(f"Cannot read manifest {path}: {error}") from error
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            sample = json.loads(line)
        except json.JSONDecodeError as error:
            raise ManifestError(f"Malformed JSON on line {line_number}: {error.msg}") from error
        if not isinstance(sample, dict):
            raise ManifestError(f"Line {line_number}: sample must be an object")
        sample_id = sample.get("sampleId")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ManifestError(f"Line {line_number}: sampleId must be a non-empty string")
        if sample_id in seen_ids:
            raise ManifestError(f"Line {line_number}: duplicate sampleId {sample_id!r}")
        seen_ids.add(sample_id)
        label = sample.get("label")
        if label not in VALID_LABELS:
            raise ManifestError(f"Line {line_number}: invalid label {label!r}")
        split = sample.get("split")
        if split not in VALID_SPLITS:
            raise ManifestError(f"Line {line_number}: invalid split {split!r}")
        if not isinstance(sample.get("input"), dict):
            raise ManifestError(f"Line {line_number}: input must be an object")
        url = sample["input"].get("finalUrl") or sample["input"].get("requestedUrl")
        if url and url in urls:
            warnings.append(f"duplicate URL {url!r}: {urls[url]} and {sample_id}")
        elif url:
            urls[url] = sample_id
        samples.append(sample)
    if not samples:
        raise ManifestError("Manifest contains no samples")
    return samples, warnings


def semantic_for_mode(mode: str) -> dict[str, Any] | None:
    if mode == "rule-only":
        return None
    level = mode.removeprefix("mock-").upper()
    if mode not in SEMANTIC_MODES:
        raise ValueError(f"Unsupported semantic mode: {mode}")
    return {
        "semanticRisk": level,
        "impersonationContext": level == "HIGH",
        "credentialHarvestingContext": level == "HIGH",
        "socialEngineeringContext": level == "HIGH",
        "financialManipulationContext": level == "HIGH",
        "semanticEvidence": [],
        "confidence": {"LOW": 0.8, "MEDIUM": 0.7, "HIGH": 0.8}[level],
    }


def _pipeline_input(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    request = AnalyzeRequest.model_validate(raw)
    page = request.page
    final_url = request.final_url or request.requested_url or ""
    title = page.title if page and page.title else request.title
    html = page.html if page and page.html else request.html
    visible_text = page.visible_text if page and page.visible_text else request.visible_text
    inputs = [item.model_dump() for item in request.inputs]
    forms = [item.model_dump() for item in request.forms]
    links = [item.model_dump() for item in request.links]
    network = request.network.model_dump() if request.network else None
    data = {
        "analysis_id": request.analysis_id or "evaluation",
        "original_url": request.requested_url or final_url,
        "final_url": final_url,
        "status_code": request.status_code,
        "title": title,
        "page_text": visible_text,
        "html": html,
        "inputs": inputs,
        "forms": forms,
        "links": links,
        "network": network,
        "redirect_chain": request.redirect_chain,
        "dom_signals": {"buttons": [], "links": links, "downloads": []},
    }
    status = {
        "analysis_id": data["analysis_id"], "html": html, "visible_text": visible_text,
        "inputs": inputs, "forms": forms, "links": links,
        "status_code": request.status_code, "error": request.error,
        "screenshot": False, "semantic_available": False,
    }
    return data, status


def evaluate_sample(sample: dict[str, Any], semantic_mode: str) -> dict[str, Any]:
    data, status = _pipeline_input(sample["input"])
    rule = analyze_dom_risk(data)
    semantic = semantic_for_mode(semantic_mode)
    status["semantic_available"] = semantic is not None
    public = AnalyzeResponse.model_validate(fuse_analysis(rule, semantic, status)).model_dump()
    return {
        "sampleId": sample["sampleId"], "source": sample.get("source"),
        "split": sample["split"], "label": sample["label"],
        "pageRiskScore": public["pageRiskScore"], "verdict": public["verdict"],
        "confidence": public["confidence"], "detectedSignals": public["detectedSignals"],
        "reasons": public["reasons"], "impersonation": public["impersonation"],
        "credentialIntent": public["credentialIntent"], "domainAnalysis": public["domainAnalysis"],
        "ruleAnalysis": rule,
    }


def safe_div(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def classification_metrics(predictions: Iterable[dict[str, Any]], view: str) -> dict[str, Any]:
    rows = [row for row in predictions if row["label"] in {"BENIGN", "PHISHING"}]
    tp = tn = fp = fn = abstain = 0
    for row in rows:
        verdict, positive = row["verdict"], row["label"] == "PHISHING"
        if verdict == "UNKNOWN" or (view == "strict" and verdict == "SUSPICIOUS"):
            abstain += 1
            continue
        predicted_positive = verdict == "PHISHING" if view == "strict" else verdict in {"SUSPICIOUS", "PHISHING"}
        if positive and predicted_positive: tp += 1
        elif not positive and not predicted_positive: tn += 1
        elif not positive and predicted_positive: fp += 1
        else: fn += 1
    evaluated = tp + tn + fp + fn
    return {
        "totalSamples": len(rows), "evaluatedSamples": evaluated,
        "benignCount": sum(row["label"] == "BENIGN" for row in rows),
        "phishingCount": sum(row["label"] == "PHISHING" for row in rows),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": safe_div(tp + tn, evaluated), "precision": safe_div(tp, tp + fp),
        "recall": safe_div(tp, tp + fn), "f1": safe_div(2 * tp, 2 * tp + fp + fn),
        "falsePositiveRate": safe_div(fp, fp + tn), "falseNegativeRate": safe_div(fn, fn + tp),
        "specificity": safe_div(tn, tn + fp), "abstainCount": abstain,
        "coverage": safe_div(evaluated, len(rows)),
    }


def _percentile(values: list[int], percentile: float) -> float:
    if not values: return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 4)


def score_statistics(predictions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    rows = list(predictions)
    for label in ("BENIGN", "PHISHING"):
        values = [row["pageRiskScore"] for row in rows if row["label"] == label]
        result[label] = {"count": len(values), "min": min(values) if values else None,
                         "max": max(values) if values else None,
                         "mean": round(mean(values), 4) if values else None,
                         "median": round(median(values), 4) if values else None,
                         "p25": _percentile(values, .25), "p50": _percentile(values, .5),
                         "p75": _percentile(values, .75), "p90": _percentile(values, .9)}
    return result


def score_overlap(predictions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(predictions)
    benign = [row["pageRiskScore"] for row in rows if row["label"] == "BENIGN"]
    phishing = [row["pageRiskScore"] for row in rows if row["label"] == "PHISHING"]
    if not benign or not phishing:
        return {"available": False, "overlaps": None, "lower": None, "upper": None}
    lower = max(min(benign), min(phishing))
    upper = min(max(benign), max(phishing))
    return {"available": True, "overlaps": lower <= upper,
            "lower": lower if lower <= upper else None,
            "upper": upper if lower <= upper else None,
            "benignMax": max(benign), "phishingMin": min(phishing)}


def verdict_distribution(predictions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(predictions); result = {}
    for label in ("BENIGN", "PHISHING"):
        selected = [row for row in rows if row["label"] == label]
        counts = Counter(row["verdict"] for row in selected)
        result[label] = {verdict: {"count": counts[verdict], "rate": safe_div(counts[verdict], len(selected))} for verdict in VERDICTS}
    return result


def field_metrics(samples: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [(sample.get("expected") or {}, prediction) for sample, prediction in zip(samples, predictions)]
    brand = [(expected["brand"], pred["ruleAnalysis"]["impersonation"].get("brand")) for expected, pred in pairs if "brand" in expected]
    creds = [(set(expected["credentialTypes"]), set(pred["credentialIntent"]["types"])) for expected, pred in pairs if "credentialTypes" in expected]
    mismatch = [(expected["domainBrandMismatch"], pred["domainAnalysis"]["domainBrandMismatch"]) for expected, pred in pairs if "domainBrandMismatch" in expected]
    cred_tp = sum(len(a & b) for a, b in creds); cred_fp = sum(len(b - a) for a, b in creds); cred_fn = sum(len(a - b) for a, b in creds)
    signals = [(set(expected["detectedSignals"]), set(pred["detectedSignals"])) for expected, pred in pairs if "detectedSignals" in expected]
    return {
        "brandCandidate": {"annotated": len(brand), "correct": sum(a == b for a, b in brand), "accuracy": safe_div(sum(a == b for a, b in brand), len(brand))},
        "credentialTypes": {"annotated": len(creds), "exactMatchAccuracy": safe_div(sum(a == b for a, b in creds), len(creds)),
                            "microPrecision": safe_div(cred_tp, cred_tp + cred_fp), "microRecall": safe_div(cred_tp, cred_tp + cred_fn),
                            "microF1": safe_div(2 * cred_tp, 2 * cred_tp + cred_fp + cred_fn)},
        "domainBrandMismatch": {"annotated": len(mismatch), "accuracy": safe_div(sum(a == b for a, b in mismatch), len(mismatch))},
        "detectedSignals": {"annotated": len(signals), "exactMatchAccuracy": safe_div(sum(a == b for a, b in signals), len(signals)),
                            "subsetAccuracy": safe_div(sum(a <= b for a, b in signals), len(signals))},
    }


def collect_cases(predictions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors, reviews = [], []
    for row in predictions:
        base = {key: row[key] for key in ("sampleId", "label", "verdict", "pageRiskScore", "detectedSignals", "reasons", "source")}
        base["prediction"] = row["verdict"]
        if row["label"] == "BENIGN" and row["verdict"] == "PHISHING": errors.append({**base, "errorType": "FALSE_POSITIVE", "metricView": "strict_and_alert"})
        if row["label"] == "PHISHING" and row["verdict"] == "NORMAL": errors.append({**base, "errorType": "FALSE_NEGATIVE", "metricView": "strict_and_alert"})
        if row["verdict"] in {"SUSPICIOUS", "UNKNOWN"}: reviews.append({**base, "reviewType": row["verdict"]})
    return errors, reviews


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=SERVICE_DIR, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError): return None


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _table(metrics: dict[str, Any]) -> str:
    keys = ("evaluatedSamples", "tp", "tn", "fp", "fn", "accuracy", "precision", "recall", "f1", "falsePositiveRate", "falseNegativeRate", "specificity", "coverage")
    return "| Metric | Value |\n|---|---:|\n" + "\n".join(f"| {key} | {metrics[key]} |" for key in keys)


def render_report(summary: dict[str, Any], errors: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> str:
    scores, fields = summary["scoreDistribution"], summary["fieldMetrics"]
    case_lines = lambda rows: "\n".join(f"- `{row['sampleId']}`: {row['label']} → {row['verdict']} (score {row['pageRiskScore']})" for row in rows) or "- None"
    return f"""# FinDer Page Behavior AI Evaluation

- Run ID: `{summary['runId']}`
- Baseline commit: `{summary['baselineCommit']}`
- Dataset: `{summary['dataset']}`
- Semantic mode: `{summary['semanticMode']}`
- Sample count: {summary['sampleCount']}

## Strict Metrics

{_table(summary['strict'])}

## Alert Metrics

{_table(summary['alert'])}

## Coverage

| Verdict | Count | Rate |
|---|---:|---:|
""" + "\n".join(f"| {v} | {summary['coverage'][v]['count']} | {summary['coverage'][v]['rate']} |" for v in VERDICTS) + f"""

## Score Distribution

| Label | Count | Min | Max | Mean | Median | P25 | P75 | P90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {label} | {s['count']} | {s['min']} | {s['max']} | {s['mean']} | {s['median']} | {s['p25']} | {s['p75']} | {s['p90']} |" for label, s in scores.items()) + f"""

Score overlap: `{json.dumps(summary['scoreOverlap'], ensure_ascii=False)}`

## Verdict Distribution

```json
{json.dumps(summary['verdictDistribution'], ensure_ascii=False, indent=2)}
```

## Field Metrics

```json
{json.dumps(fields, ensure_ascii=False, indent=2)}
```

## False Positives

{case_lines([r for r in errors if r['errorType'] == 'FALSE_POSITIVE'])}

## False Negatives

{case_lines([r for r in errors if r['errorType'] == 'FALSE_NEGATIVE'])}

## Review Cases

{case_lines(reviews)}

## Interpretation and Limitations

Synthetic fixture performance is not an estimate of real-world phishing detection performance.

For public archived-page manifests, this is a sanitized, feature-only evaluation. Raw HTML and
JavaScript are intentionally not retained. Malicious JavaScript behavior is not executed, dynamic
DOM mutations and real network behavior are not observed, redirect behavior may be unavailable,
raw script-level obfuscation signals are intentionally excluded, and screenshot visual similarity
may be unavailable. Therefore, this evaluates the available URL/domain/text/form/input/link-centered
page-risk analysis, not full browser-runtime phishing detection.

These samples evaluate only the subset of FinDer features available from static URL metadata and
should not be interpreted as full page-behavior evaluation when the manifest is URL-only.
"""


def run_evaluation(manifest: Path, semantic_mode: str, output_dir: Path, run_id: str | None = None,
                   split: str | None = None, limit: int | None = None) -> tuple[Path, dict[str, Any]]:
    samples, warnings = load_manifest(manifest)
    if split: samples = [sample for sample in samples if sample["split"] == split]
    samples = [sample for sample in samples if sample["label"] not in {"SKIP", "UNKNOWN"}]
    if limit is not None: samples = samples[:limit]
    if not samples: raise ManifestError("No evaluable samples remain after filtering")
    predictions = [evaluate_sample(sample, semantic_mode) for sample in samples]
    errors, reviews = collect_cases(predictions)
    counts = Counter(row["verdict"] for row in predictions)
    resolved_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    summary = {
        "runId": resolved_run_id, "generatedAt": datetime.now(timezone.utc).isoformat(),
        "baseline": "baseline-v1", "baselineCommit": git_commit(), "pythonVersion": platform.python_version(),
        "semanticMode": semantic_mode, "dataset": str(manifest.resolve()), "manifestSha256": manifest_hash,
        "split": split, "sampleCount": len(samples), "warnings": warnings,
        "strict": classification_metrics(predictions, "strict"), "alert": classification_metrics(predictions, "alert"),
        "coverage": {v: {"count": counts[v], "rate": safe_div(counts[v], len(predictions))} for v in VERDICTS},
        "scoreDistribution": score_statistics(predictions), "scoreOverlap": score_overlap(predictions),
        "verdictDistribution": verdict_distribution(predictions),
        "fieldMetrics": field_metrics(samples, predictions),
    }
    serializable = [{k: v for k, v in row.items() if k != "ruleAnalysis"} for row in predictions]
    _write_jsonl(run_dir / "predictions.jsonl", serializable)
    _write_jsonl(run_dir / "errors.jsonl", errors)
    _write_jsonl(run_dir / "review_cases.jsonl", reviews)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(render_report(summary, errors, reviews), encoding="utf-8")
    return run_dir, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the baseline-v1 page behavior AI offline")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--semantic-mode", choices=sorted(SEMANTIC_MODES), default="rule-only")
    parser.add_argument("--output-dir", type=Path, default=SERVICE_DIR / "evaluation" / "results")
    parser.add_argument("--run-id")
    parser.add_argument("--split", choices=sorted(VALID_SPLITS))
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_dir, summary = run_evaluation(args.manifest, args.semantic_mode, args.output_dir, args.run_id, args.split, args.limit)
    except (ManifestError, ValueError, OSError) as error:
        print(f"evaluation failed: {error}", file=sys.stderr); return 2
    print(json.dumps({"runDirectory": str(run_dir), "strict": summary["strict"], "alert": summary["alert"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())