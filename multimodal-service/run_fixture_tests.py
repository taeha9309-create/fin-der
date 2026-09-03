import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
DEFAULT_FIXTURES = (
    "normal_bank",
    "non_financial",
    "fake_bank",
    "card_capital",
    "internet_bank",
    "government_support",
)
REQUIRED_RESULT_FIELDS = (
    "verdict",
    "risk_score",
    "impersonation_type",
    "impersonated_brand",
    "credential_request",
    "financial_action_request",
    "app_install_request",
    "external_contact_request",
    "evidence",
)


sys.path.insert(0, str(APP_DIR))
from analyzer import analyze  # noqa: E402


def load_fixture(fixture_name: str) -> dict:
    input_path = BASE_DIR / "fixtures" / fixture_name / "input.json"
    if not input_path.is_file():
        raise FileNotFoundError(f"fixture 입력 파일이 없습니다: {input_path}")

    with input_path.open("r", encoding="utf-8") as input_file:
        input_data = json.load(input_file)

    screenshot_path = Path(input_data["screenshot_path"])
    if not screenshot_path.is_absolute():
        screenshot_path = input_path.parent / screenshot_path
    elif not screenshot_path.is_file():
        screenshot_path = input_path.parent / screenshot_path.name
    if not screenshot_path.is_file():
        raise FileNotFoundError(
            f"fixture 이미지가 없습니다: {screenshot_path} "
            "(필요한 이미지 내용은 README.md를 확인하세요.)"
        )

    input_data["screenshot_path"] = str(screenshot_path.resolve())
    return input_data


def validate_result(result: dict) -> None:
    missing_fields = [
        field for field in REQUIRED_RESULT_FIELDS if field not in result
    ]
    if missing_fields:
        raise ValueError(
            "분석 결과에 필수 필드가 없습니다: " + ", ".join(missing_fields)
        )


def run_fixture(fixture_name: str, results_dir: Path) -> Path:
    input_data = load_fixture(fixture_name)
    result = analyze(input_data)
    validate_result(result)

    if fixture_name in {"normal_bank", "non_financial"}:
        if result["verdict"] == "PHISHING":
            raise ValueError(f"{fixture_name} fixture was falsely classified as high risk")

    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{fixture_name}.json"
    with result_path.open("w", encoding="utf-8") as result_file:
        json.dump(result, result_file, ensure_ascii=False, indent=2)
        result_file.write("\n")

    return result_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="fixture input.json을 읽어 기존 멀티모달 analyze()를 실행합니다."
    )
    parser.add_argument(
        "fixtures",
        nargs="*",
        default=list(DEFAULT_FIXTURES),
        help="실행할 fixture 이름 (미지정 시 안전한 합성 fixture 6개 실행)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=BASE_DIR / "results",
        help="결과 JSON을 저장할 경로 (기본값: 프로젝트 results 폴더)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = args.results_dir
    failed = False

    for fixture_name in args.fixtures:
        print(f"\n=== fixture 실행: {fixture_name} ===")
        try:
            result_path = run_fixture(fixture_name, results_dir)
        except Exception as error:
            failed = True
            print(f"[실패] {fixture_name}: {error}", file=sys.stderr)
            continue

        print(f"[완료] 결과 저장: {result_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
