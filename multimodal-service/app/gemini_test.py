import os


def main() -> None:
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    print("키 감지 여부:", bool(api_key))

    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents="연결 테스트입니다. '연결 성공'이라고만 답해주세요.",
    )
    print(response.text)


if __name__ == "__main__":
    main()
