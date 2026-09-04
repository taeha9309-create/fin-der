"""Offline adapter for Phishpedia's documented info.txt/shot.png layout."""

from __future__ import annotations

from pathlib import Path

from .common import AdapterResult
from .phishintention_adapter import adapt_directory as _adapt_site_directories


def adapt_directory(
    root: Path,
    *,
    label: str,
    split: str | None = "test",
) -> AdapterResult:
    """Convert local URL metadata only; screenshots are intentionally ignored."""
    result = _adapt_site_directories(root, label=label, split=split, parse_html=False)
    for record in result.records:
        record["source"] = "phishpedia"
        record["sampleId"] = record["sampleId"].replace("phishintention-", "phishpedia-", 1)
        record["input"]["analysisId"] = record["sampleId"]
    return result
