"""Select canonical PhreshPhish samples and export inert static features.

This command reads one local Parquet shard and never fetches or renders a URL.
Raw HTML is projected only for the selected rows, passed through the existing
static feature exporter, and held in a temporary exporter-input file.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.adapters.common import normalized_url
from evaluation.exporters.static_feature_exporter import ExportConfig, export_jsonl


def _select_rows(parquet_path: Path, per_label: int) -> list[dict[str, Any]]:
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("duckdb is required to read the local Parquet shard") from error

    connection = duckdb.connect()
    metadata = connection.execute(
        "SELECT sha256, url, label FROM read_parquet(?) ORDER BY label, sha256",
        [str(parquet_path)],
    ).fetchall()
    selected_ids: list[str] = []
    counts: Counter[str] = Counter()
    seen_urls: dict[str, set[str]] = {"benign": set(), "phish": set()}
    for sha256, url, label in metadata:
        if label not in seen_urls or counts[label] >= per_label:
            continue
        try:
            canonical_url = normalized_url(url)
        except (TypeError, ValueError):
            continue
        if canonical_url in seen_urls[label]:
            continue
        seen_urls[label].add(canonical_url)
        selected_ids.append(sha256)
        counts[label] += 1
    if counts != Counter({"benign": per_label, "phish": per_label}):
        raise ValueError(f"insufficient valid samples: {dict(counts)}")

    rows = connection.execute(
        "SELECT sha256, url, label, target, html FROM read_parquet(?) "
        "WHERE sha256 IN (SELECT unnest(?::VARCHAR[]))",
        [str(parquet_path), selected_ids],
    ).fetchall()
    by_id = {
        row[0]: {"sha256": row[0], "url": row[1], "label": row[2],
                 "targetBrand": row[3], "html": row[4]}
        for row in rows
    }
    return [by_id[source_id] for source_id in selected_ids]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--extraction-timestamp", required=True)
    parser.add_argument("--per-label", type=int, default=20)
    args = parser.parse_args()

    rows = _select_rows(args.parquet, args.per_label)
    config = ExportConfig(
        source="phreshphish",
        dataset_name="KevinRoshan8/phreshphish",
        dataset_revision=args.dataset_revision,
        source_split="test",
        extraction_timestamp=args.extraction_timestamp,
        benign_label="benign",
        phishing_label="phish",
    )
    with tempfile.TemporaryDirectory(prefix="finder-phreshphish-") as directory:
        exporter_input = Path(directory) / "selected.jsonl"
        exporter_input.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        result = export_jsonl(exporter_input, args.output, config)
    print(json.dumps({"stats": result.stats.__dict__, "featureCounts": result.feature_counts}))
    return 0 if result.stats.errors == 0 and len(result.records) == args.per_label * 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
