"""Convert local archived HTML records into inert FinDer evaluation JSONL.

This module is intended for a disposable isolated Linux research environment.
It performs local static parsing only: it has no network, browser, JavaScript,
resource-loading, DNS, or subprocess capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evaluation.adapters.common import (
    AdapterStats,
    UnsafeContentError,
    deduplicate,
    inert_record,
    validate_inert_record,
    write_manifest,
)
from evaluation.adapters.safe_html import extract_features

EXTRACTION_VERSION = "static-features-v1"
MAX_SOURCE_RECORD_BYTES = 10 * 1024 * 1024
SAFE_ID = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class ExportConfig:
    source: str
    dataset_name: str
    dataset_revision: str
    source_split: str
    extraction_timestamp: str
    benign_label: str = "BENIGN"
    phishing_label: str = "PHISHING"


@dataclass
class ExportResult:
    records: list[dict[str, Any]]
    stats: AdapterStats
    feature_counts: dict[str, int] = field(default_factory=dict)


def _sample_id(config: ExportConfig, source_record_id: str) -> str:
    prefix = SAFE_ID.sub("-", config.source.casefold()).strip("-") or "public"
    digest = hashlib.sha256(
        f"{config.dataset_name}\0{config.dataset_revision}\0{source_record_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _label(value: Any, config: ExportConfig) -> str:
    if value == config.benign_label:
        return "BENIGN"
    if value == config.phishing_label:
        return "PHISHING"
    raise ValueError("source label is not covered by the explicit label mapping")


def _optional_string(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _convert_row(row: dict[str, Any], config: ExportConfig) -> dict[str, Any]:
    source_record_id = row.get("sourceRecordId") or row.get("sha256")
    if not isinstance(source_record_id, str) or not source_record_id.strip():
        raise ValueError("sourceRecordId or sha256 is required")
    requested_url = row.get("requestedUrl") or row.get("url")
    if not isinstance(requested_url, str):
        raise ValueError("requestedUrl or url is required")
    html = row.get("html")
    if not isinstance(html, str):
        raise ValueError("local archived html string is required")
    status_code = row.get("statusCode")
    if status_code is not None and (isinstance(status_code, bool) or not isinstance(status_code, int)):
        raise ValueError("statusCode must be an integer or null")

    features = extract_features(html)
    source_title = _optional_string(row, "title") or ""
    title = features.title or source_title
    target_brand = _optional_string(row, "targetBrand")
    record = inert_record(
        sample_id=_sample_id(config, source_record_id),
        source=config.source,
        label=_label(row.get("label"), config),
        url=requested_url,
        final_url=_optional_string(row, "finalUrl"),
        split=config.source_split,
        title=title,
        visible_text=features.visible_text,
        inputs=features.inputs,
        forms=features.forms,
        links=features.links,
        brand=target_brand,
        status_code=status_code,
    )
    record["sourceRecordId"] = source_record_id
    record["datasetName"] = config.dataset_name
    record["provenance"] = {
        "datasetRevision": config.dataset_revision,
        "sourceSplit": config.source_split,
        "extractionVersion": EXTRACTION_VERSION,
        "extractionTimestamp": config.extraction_timestamp,
        "featureAvailability": {
            "title": bool(title),
            "visibleText": bool(features.visible_text),
            "inputs": True,
            "forms": True,
            "links": True,
            "rawHtmlStored": False,
            "javascriptExecuted": False,
        },
    }
    validate_inert_record(record)
    return record


def export_jsonl(input_path: Path, output_path: Path, config: ExportConfig) -> ExportResult:
    stats = AdapterStats()
    records: list[dict[str, Any]] = []
    with input_path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            if not raw_line.strip():
                continue
            stats.discovered += 1
            if len(raw_line) > MAX_SOURCE_RECORD_BYTES:
                stats.skipped += 1
                stats.messages.append(f"line {line_number}: source record exceeds safety limit")
                continue
            try:
                row = json.loads(raw_line.decode("utf-8"))
                if not isinstance(row, dict):
                    raise ValueError("source record must be an object")
                records.append(_convert_row(row, config))
            except (UnicodeError, json.JSONDecodeError, UnsafeContentError, ValueError) as error:
                stats.errors += 1
                stats.messages.append(f"line {line_number}: {type(error).__name__}")

    records = deduplicate(records, stats)
    stats.converted = len(records)
    write_manifest(output_path, records)
    feature_counts = {
        "title": sum(bool(row["input"]["page"]["title"]) for row in records),
        "visibleText": sum(bool(row["input"]["page"]["visibleText"]) for row in records),
        "inputs": sum(bool(row["input"]["inputs"]) for row in records),
        "forms": sum(bool(row["input"]["forms"]) for row in records),
        "links": sum(bool(row["input"]["links"]) for row in records),
    }
    return ExportResult(records, stats, feature_counts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Statically export local archived HTML to inert JSONL")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--source-split", choices=("train", "validation", "test", "holdout"), required=True)
    parser.add_argument("--extraction-timestamp", required=True)
    parser.add_argument("--benign-label", default="BENIGN")
    parser.add_argument("--phishing-label", default="PHISHING")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ExportConfig(
        source=args.source,
        dataset_name=args.dataset_name,
        dataset_revision=args.dataset_revision,
        source_split=args.source_split,
        extraction_timestamp=args.extraction_timestamp,
        benign_label=args.benign_label,
        phishing_label=args.phishing_label,
    )
    result = export_jsonl(args.input, args.output, config)
    print(json.dumps({"stats": result.stats.__dict__, "featureCounts": result.feature_counts}))
    return 0 if result.stats.errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
