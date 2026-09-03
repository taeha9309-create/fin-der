import json
from pathlib import Path

from PIL import Image

try:
    from .config import Settings
    from .preprocessor import preprocess_input
    from .prompt_builder import build_analysis_prompt
    from .response_parser import parse_multimodal_response
except ImportError:  # Direct script/fixture execution from app/.
    from config import Settings
    from preprocessor import preprocess_input
    from prompt_builder import build_analysis_prompt
    from response_parser import parse_multimodal_response


BASE_DIR = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system_v1.txt"


def analyze(input_data: dict) -> dict:
    # 1. 입력 전처리
    processed_input = preprocess_input(input_data)

    # 2. 분석 프롬프트 생성
    prompt = build_analysis_prompt(processed_input)

    # 2. system prompt 읽기
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    # 3. Gemini API 키 가져오기
    current_settings = Settings.from_env()
    api_key = current_settings.gemini_api_key

    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    # 4. Gemini 클라이언트 생성 (API 모듈은 키/SDK 없이도 health가 뜰 수 있다.)
    from google import genai

    client = genai.Client(api_key=api_key)

    # 5. fixture의 screenshot_path는 유지하고, HTML-only 요청도 허용한다.
    contents = [system_prompt + "\n\n" + prompt]
    screenshot_path = processed_input.get("screenshot_path")
    if screenshot_path:
        with Image.open(screenshot_path) as source_image:
            source_image.load()
            contents.append(source_image.copy())

    # 6. Gemini에 텍스트 + 이미지 함께 전달
    response = client.models.generate_content(
        model=current_settings.gemini_model,
        contents=contents,
    )

    # 7. Gemini 응답 가져오기
    response_text = response.text

    # 8. JSON 응답 파싱
    result = parse_multimodal_response(response_text)

    return result


if __name__ == "__main__":
    input_path = BASE_DIR / "fixtures" / "normal_bank" / "input.json"

    with open(input_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    result = analyze(input_data)

    print("\n=== 분석 결과 ===")
    print(result)
