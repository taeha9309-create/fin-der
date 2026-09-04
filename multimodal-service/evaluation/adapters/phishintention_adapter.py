"""Offline adapter for PhishIntention's documented site-folder format.

Expected local input (one directory per archived site): ``info.txt`` containing
the URL, ``shot.png`` (ignored), and optional ``html.txt``.  A caller must supply
the ground-truth label because the documented folder itself does not encode one.
No browser, subprocess, socket, or HTTP client is used.
"""

from __future__ import annotations

from pathlib import Path

from .common import AdapterResult, AdapterStats, deduplicate, deterministic_split, inert_record
from .safe_html import ExtractedPage, extract_features

MAX_HTML_BYTES = 5 * 1024 * 1024


def _local_features(site_dir: Path, parse_html: bool) -> ExtractedPage:
    html_path = site_dir / "html.txt"
    if not parse_html or not html_path.is_file():
        return ExtractedPage()
    if html_path.stat().st_size > MAX_HTML_BYTES:
        raise ValueError("local HTML exceeds the 5 MiB safety limit")
    # Reading may itself be blocked by endpoint protection.  The caller must stop
    # rather than retry or add an antivirus exception if that happens.
    return extract_features(html_path.read_text(encoding="utf-8", errors="replace"))


def adapt_directory(
    root: Path,
    *,
    label: str,
    split: str | None = "test",
    parse_html: bool = False,
) -> AdapterResult:
    stats = AdapterStats()
    records = []
    for site_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        stats.discovered += 1
        info_path = site_dir / "info.txt"
        if not info_path.is_file():
            stats.skipped += 1
            stats.messages.append(f"{site_dir.name}: missing info.txt")
            continue
        try:
            url = info_path.read_text(encoding="utf-8", errors="strict").strip()
            features = _local_features(site_dir, parse_html)
            record = inert_record(
                sample_id=f"phishintention-{site_dir.name}",
                source="phishintention",
                label=label,
                url=url,
                split=split or deterministic_split(url),
                title=features.title,
                visible_text=features.visible_text,
                inputs=features.inputs,
                forms=features.forms,
                links=features.links,
            )
        # Do not catch OSError/PermissionError: endpoint-protection or filesystem
        # refusal must stop the whole operation instead of being retried/skipped.
        except (UnicodeError, ValueError) as error:
            stats.errors += 1
            stats.messages.append(f"{site_dir.name}: {error}")
            continue
        records.append(record)
        stats.converted += 1
    records = deduplicate(records, stats)
    stats.converted = len(records)
    return AdapterResult(records, stats)
