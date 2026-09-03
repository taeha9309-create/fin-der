"""Evaluate manifest-listed domestic screenshots with one Gemini call per image.

Run this inside the multimodal-service container so it reuses the production
prompt, preprocessing, response parser, model setting, and dependencies.
Raw model responses and normalized results are written only below the supplied
output directory, which should live under the locally excluded local-test-data/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from google import genai
from PIL import Image


APP_DIR = Path(os.getenv("MULTIMODAL_APP_DIR", "/app/app"))
BASE_DIR = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

from config import Settings  # noqa: E402
from preprocessor import preprocess_input  # noqa: E402
from prompt_builder import build_analysis_prompt  # noqa: E402
from response_parser import parse_multimodal_response  # noqa: E402


FIELDNAMES = [
    "filename",
    "institution",
    "category",
    "status",
    "is_financial_impersonation",
    "impersonated_brand",
    "brand_category",
    "attack_type",
    "multimodal_risk_score",
    "risk_level",
    "confidence",
    "reasons",
    "model_name",
    "prompt_version",
    "latency_seconds",
    "attempts",
    "error",
    "verdict",
    "false_positive",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--screenshots-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--only-new-against",
        type=Path,
        help="Evaluate only filenames absent from this baseline manifest.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        help="JSON result path (default: OUTPUT_DIR/domestic-results.json).",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        help="CSV result path (default: OUTPUT_DIR/domestic-results.csv).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        choices=range(0, 4),
        metavar="0..3",
        help="Bounded retries for provider 429/503 errors (default: 0).",
    )
    parser.add_argument(
        "--merge-results",
        type=Path,
        nargs="+",
        help="Merge existing result JSON files without making Gemini calls.",
    )
    return parser.parse_args()


def empty_result(row: dict[str, str], status: str, error: str = "") -> dict[str, object]:
    result: dict[str, object] = {field: "" for field in FIELDNAMES}
    result.update(
        filename=row.get("filename", ""),
        institution=row.get("institution", ""),
        category=row.get("category", ""),
        status=status,
        error=error,
        verdict="fail",
        false_positive=False,
    )
    return result


def is_retryable(error: Exception) -> bool:
    message = str(error).lower()
    return any(token in message for token in ("429", "resource_exhausted", "503", "unavailable"))


def normalize_merged_result(
    result: dict[str, object], manifest_row: dict[str, str]
) -> dict[str, object]:
    normalized = {field: result.get(field, "") for field in FIELDNAMES}
    normalized["institution"] = manifest_row["institution"]
    normalized["category"] = manifest_row["category"]
    normalized["attempts"] = result.get("attempts", 1)
    normalized["latency_seconds"] = result.get("latency_seconds")
    low_risk = str(normalized["risk_level"]).lower().startswith("low")
    false_positive = (
        normalized["is_financial_impersonation"] is True or not low_risk
    )
    normalized["false_positive"] = false_positive
    normalized["verdict"] = (
        "pass"
        if normalized["status"] == "completed" and not false_positive
        else "fail"
    )
    return normalized


def write_outputs(
    args: argparse.Namespace, results: list[dict[str, object]], settings: Settings
) -> int:
    csv_path = args.summary_csv or (args.output_dir / "domestic-results.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    json_path = args.results_json or (args.output_dir / "domestic-results.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    false_positives = sum(1 for result in results if result["false_positive"] is True)
    errors = sum(1 for result in results if result["status"] in {"ERROR", "SKIPPED"})
    category_summary: dict[str, dict[str, int]] = {}
    institution_summary: dict[str, dict[str, int]] = {}
    for result in results:
        for key, target in (
            (str(result["category"]), category_summary),
            (str(result["institution"]), institution_summary),
        ):
            bucket = target.setdefault(
                key, {"total": 0, "completed": 0, "failed": 0, "false_positives": 0}
            )
            bucket["total"] += 1
            if result["status"] == "completed":
                bucket["completed"] += 1
            else:
                bucket["failed"] += 1
            if result["false_positive"] is True:
                bucket["false_positives"] += 1
    summary = {
        "total": len(results),
        "completed": len(results) - errors,
        "failed": errors,
        "passed_expectation": sum(1 for result in results if result["verdict"] == "pass"),
        "false_positives": false_positives,
        "false_positive_rate": round(false_positives / len(results), 6) if results else 0.0,
        "model": settings.gemini_model,
        "prompt_version": settings.prompt_version,
        "categories": category_summary,
        "institutions": institution_summary,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


def evaluate_one(
    client: genai.Client,
    settings: Settings,
    row: dict[str, str],
    screenshot_path: Path,
    raw_dir: Path,
    max_retries: int,
) -> dict[str, object]:
    evaluation_input = preprocess_input(
        {
            "analysis_id": f"domestic_{screenshot_path.stem}",
            "original_url": row.get("source_url", ""),
            "final_url": row.get("source_url", ""),
            "screenshot_path": str(screenshot_path),
            "page_text": (
                f"기관: {row['institution']}\n"
                f"분류: {row['category']}\n"
                f"캡처 설명: {row.get('notes', '')}"
            ),
            "html": "",
            "forms": [],
        }
    )
    prompt = build_analysis_prompt(evaluation_input)
    system_prompt = (BASE_DIR / "prompts" / "system_v1.txt").read_text(encoding="utf-8")

    attempts = 0
    while True:
        attempts += 1
        try:
            with Image.open(screenshot_path) as image:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=[system_prompt + "\n\n" + prompt, image],
                )
            break
        except Exception as error:
            if attempts > max_retries or not is_retryable(error):
                setattr(error, "evaluation_attempts", attempts)
                raise
            time.sleep(min(2 * attempts, 6))
    response_text = response.text or ""
    (raw_dir / f"{screenshot_path.stem}.txt").write_text(response_text, encoding="utf-8")
    parsed = parse_multimodal_response(response_text)
    mm = parsed["multimodal_result"]
    low_risk = str(mm["risk_level"]).lower().startswith("low")
    false_positive = bool(mm["is_financial_impersonation"]) or not low_risk
    return {
        "filename": row["filename"],
        "institution": row["institution"],
        "category": row.get("category", ""),
        "status": parsed["status"],
        "is_financial_impersonation": mm["is_financial_impersonation"],
        "impersonated_brand": mm["impersonated_brand"],
        "brand_category": mm["brand_category"],
        "attack_type": mm["attack_type"],
        "multimodal_risk_score": mm["multimodal_risk_score"],
        "risk_level": mm["risk_level"],
        "confidence": mm["confidence"],
        "reasons": json.dumps(mm["reasons"], ensure_ascii=False),
        "model_name": parsed["model_name"],
        "prompt_version": parsed["prompt_version"],
        "attempts": attempts,
        "error": "",
        "verdict": "fail" if false_positive else "pass",
        "false_positive": false_positive,
    }


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw-responses"
    raw_dir.mkdir(exist_ok=True)

    with args.manifest.open("r", encoding="utf-8-sig", newline="") as manifest_file:
        rows = list(csv.DictReader(manifest_file))
    settings = Settings.from_env()
    if args.merge_results:
        manifest_by_filename = {row["filename"]: row for row in rows}
        merged_by_filename: dict[str, dict[str, object]] = {}
        for result_path in args.merge_results:
            for result in json.loads(result_path.read_text(encoding="utf-8-sig")):
                filename = result["filename"]
                if filename in merged_by_filename:
                    raise ValueError(f"Duplicate result filename: {filename}")
                if filename not in manifest_by_filename:
                    raise ValueError(f"Result filename is not in manifest: {filename}")
                merged_by_filename[filename] = normalize_merged_result(
                    result, manifest_by_filename[filename]
                )
        if set(merged_by_filename) != set(manifest_by_filename):
            missing = sorted(set(manifest_by_filename) - set(merged_by_filename))
            raise ValueError("Merged results are missing manifest filenames: " + ", ".join(missing))
        results = [merged_by_filename[row["filename"]] for row in rows]
        return write_outputs(args, results, settings)
    if args.only_new_against:
        with args.only_new_against.open("r", encoding="utf-8-sig", newline="") as baseline_file:
            baseline_filenames = {row["filename"] for row in csv.DictReader(baseline_file)}
        rows = [row for row in rows if row["filename"] not in baseline_filenames]

    if not settings.gemini_api_key:
        results = [empty_result(row, "SKIPPED", "GEMINI_API_KEY is not configured") for row in rows]
    else:
        client = genai.Client(api_key=settings.gemini_api_key)
        results = []
        for index, row in enumerate(rows, start=1):
            screenshot_path = args.screenshots_dir / row["filename"]
            started_at = time.perf_counter()
            if not screenshot_path.is_file():
                result = empty_result(row, "ERROR", f"Screenshot not found: {screenshot_path}")
            else:
                try:
                    result = evaluate_one(
                        client, settings, row, screenshot_path, raw_dir, args.max_retries
                    )
                except Exception as error:  # Preserve every row even when the provider/parser fails.
                    result = empty_result(row, "ERROR", f"{type(error).__name__}: {error}")
                    result["attempts"] = getattr(error, "evaluation_attempts", 1)
            result["latency_seconds"] = round(time.perf_counter() - started_at, 3)
            results.append(result)
            print(f"[{index}/{len(rows)}] {row['filename']}: {result['status']}", flush=True)

    return write_outputs(args, results, settings)


if __name__ == "__main__":
    raise SystemExit(main())
