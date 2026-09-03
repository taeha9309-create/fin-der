# Multimodal Service

Sandbox가 수집한 실제 페이지의 Screenshot, HTML, URL과 DOM 신호를 기존 Gemini 분석기에 전달하는 FastAPI 서비스입니다. 1차 XGBoost/SHAP 판단은 다루지 않으며 Gemini 모델은 `gemini-3.1-flash-lite-preview`를 그대로 사용합니다.

## 실행

```powershell
cd .\multimodal-service
python -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "로컬_API_키"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Docker Compose에서는 저장소 루트의 `.env`에 `GEMINI_API_KEY`를 설정하고 `docker compose up --build multimodal-service`를 실행합니다. 키는 파일에 커밋하지 않습니다.

## HTTP API

`GET /health`는 프로세스 상태, 모델명, API 키 설정 여부를 반환합니다. 키가 없어도 health는 200입니다.

`POST /v1/analyze`는 Sandbox의 camelCase 응답을 그대로 받을 수 있습니다. 기존 Backend가 보내던 `url`, `final_url`, `screenshot_base64`도 하위 호환됩니다. `htmlSizeBytes`, `screenshotSizeBytes`, `loadTimeMs`처럼 분석에 사용하지 않는 Sandbox 메타데이터는 안전하게 무시됩니다.

```json
{
  "requestedUrl": "https://fake-support.example/apply",
  "finalUrl": "https://fake-support.example/form",
  "statusCode": 200,
  "title": "정책자금 신청",
  "html": "<form><input name=\"resident_number\"><button>신청</button></form>",
  "screenshotBase64": "iVBORw0KGgoAAA...",
  "error": null
}
```

성공 응답은 항상 최신 평면 계약입니다.

```json
{
  "verdict": "PHISHING",
  "risk_score": 92,
  "impersonation_type": "POLICY_FUND",
  "impersonated_brand": "서민금융진흥원",
  "credential_request": true,
  "financial_action_request": true,
  "app_install_request": false,
  "external_contact_request": true,
  "evidence": ["비공식 도메인에서 주민등록번호 입력과 외부 상담을 유도합니다."]
}
```

Screenshot과 HTML/Text가 모두 없으면 Gemini를 호출하지 않고 `UNKNOWN`을 반환합니다. 분석 자료가 있지만 API 키가 없으면 503, Base64가 잘못되면 422, Gemini 호출 또는 응답 검증 실패는 502입니다. 요청별 오류는 격리되어 서버 프로세스를 종료하지 않습니다.

HTML에서는 script를 실행하지 않고 다음 정보만 추출합니다.

- visible text
- form action/method와 input type/name/autocomplete/placeholder
- button text
- link text와 destination
- download 속성 또는 APK/실행·압축 파일 확장자 링크

## 테스트

```powershell
python -m pytest -q -p no:cacheprovider
python .\run_fixture_tests.py normal_bank non_financial fake_bank card_capital internet_bank government_support
```

fixture 실행은 기존 `screenshot_path`를 계속 지원하며 실제 Gemini 호출이므로 `GEMINI_API_KEY`와 네트워크가 필요합니다. API/파서/fixture 경로 회귀 테스트는 키 없이 실행됩니다. 자세한 합성 fixture 설명은 `FIXTURE_TESTS.md`를 참고하십시오.
