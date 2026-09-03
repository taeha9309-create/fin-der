import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE_DIR / "prompts" / "analysis_v1.txt"


def build_analysis_prompt(input_data: dict) -> str:
    # 프롬프트 템플릿 읽기
    template = PROMPT_PATH.read_text(encoding="utf-8")

    # forms는 JSON 문자열로 변환
    forms_text = json.dumps(
        input_data.get("forms", []),
        ensure_ascii=False,
        indent=2
    )
    dom_signals_text = json.dumps(
        input_data.get("dom_signals", {}),
        ensure_ascii=False,
        indent=2
    )

    # 템플릿의 값을 실제 입력값으로 변경
    prompt = template.format(
        analysis_id=input_data.get("analysis_id", ""),
        original_url=input_data.get("original_url", ""),
        final_url=input_data.get("final_url", ""),
        title=input_data.get("title", ""),
        page_text=input_data.get("page_text", ""),
        html=input_data.get("html", ""),
        forms=forms_text,
        dom_signals=dom_signals_text,
    )

    return prompt

if __name__ == "__main__":
    input_path = BASE_DIR / "schemas" / "input_schema.json"

    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    result = build_analysis_prompt(input_data)

    print(result)
