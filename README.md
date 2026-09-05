# fin-der

금융기관·정부기관 사칭 가능성이 있는 URL을 단계적으로 분석하는 로컬 통합 프로젝트입니다.

`frontend → backend → ml-service → (riskScore >= 40) sandbox → multimodal-service → db-api → MySQL`

Gemini가 설정되지 않았거나 일시적으로 실패해도 backend는 Sandbox/ML 결과를 DB에 저장합니다. ML과 멀티모달 결과를 결합하는 현재 OR 규칙은 임시 통합 규칙이며 최종 정책이 아닙니다.

## 프로젝트 구성

### 디렉터리 구성

| 경로 | 역할 |
| --- | --- |
| `frontend/` | React 사용자 화면 |
| `backend/` | Spring Boot 오케스트레이터 (Sandbox 호출) |
| `db-api/` | Spring Boot, MySQL 저장/조회 API (`/api/analyze`, `/api/reports`) — `backend/`와 역할 정리 필요, 논의 중 |
| `sandbox/` | Playwright 및 Chromium 격리 분석 |
| `ml-service/` | XGBoost, SHAP, 금융기관 도메인 규칙 기반 1차 분석 |
| `multimodal-service/` | 스크린샷 및 HTML 기반 2차 분석 |
| `page-ai-mock/` | Backend와 2차 페이지 AI 사이의 연동 검증용 모의 서비스 |
| `url-ai-mock/` | Backend와 1차 URL AI 사이의 연동 검증용 모의 서비스 |
| `database/` | SQL 스키마와 마이그레이션 |
| `docs/` | 아키텍처와 API 문서 |
| `scripts/` | 실행 및 통합 테스트 스크립트 |

### 기본 포트

| 서비스 | 호스트 포트 | 컨테이너 포트 |
| --- | ---: | ---: |
| frontend | 3000 | 80 |
| backend | 8080 | 8080 |
| db-api | 8081 | 8081 |
| ml-service | 8001 | 8001 |
| multimodal-service | 8002 | 8002 |
| sandbox | 8003 | 3001 |
| MySQL | 3307 | 3306 |

포트는 `.env`에서 변경할 수 있습니다. 컨테이너 간 통신은 Compose 서비스명과 컨테이너 포트를 사용합니다.

## Windows에서 전체 실행

필수 도구는 Docker Desktop(Docker Compose 포함)입니다. 저장소 루트의 PowerShell에서 실행합니다.

```powershell
Copy-Item .env.example .env
# 선택: .env의 GEMINI_API_KEY= 뒤에 실제 키를 로컬에서만 입력
docker compose config
docker compose up --build -d
docker compose ps
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

`.env`와 모델 artifact는 `.gitignore` 대상입니다. 키가 없으면 멀티모달 서비스는 DOM 규칙 기반 대체 분석을 사용합니다.

Backend와 Sandbox의 요청·응답 규격은
[Backend / Sandbox API](docs/backend-sandbox-api.md)에서 확인할 수 있습니다.

## Backend/Sandbox smoke test

Docker 서비스가 실행 중인 상태에서 프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

이 스크립트는 실제 ML·Sandbox·멀티모달·DB 통합 분석, HTML·Text·Screenshot
저장과 조회, 비동기 Job 완료와 영속화, 페이지 AI 실패 시 중간 결과 보존,
내부 주소 차단, Gemini 미설정 대체 응답, 사용자 제보 및 404 응답을 자동으로 확인합니다.

종료:

```powershell
docker compose down
```

DB 데이터를 함께 지우려는 경우에만 명시적으로 `docker compose down --volumes`를 사용하십시오.

## ML 모델 재현

Docker 이미지는 `ml-service/artifacts/url_xgb.joblib`이 없으면 최신 `FEATURE_NAMES`와 `data/sample_urls.csv`로 통합 테스트용 모델을 빌드 중 생성합니다. 바이너리는 Git에 추가하지 않습니다.

호스트에서 모델과 가상환경을 준비하려면 다음을 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-ml.ps1 -Force
```

이미 의존성이 설치된 `.venv`를 재사용하려면 `-SkipInstall`을 추가할 수 있습니다.

## 서비스별 로컬 테스트

```powershell
cd .\ml-service
.\.venv\Scripts\python.exe -m pytest
cd ..\multimodal-service
python -m pytest
cd ..\frontend
npm.cmd ci
npm.cmd run build
cd ..\sandbox
npm.cmd ci
node --check server.js
node --check urlValidator.js
cd ..\backend
.\gradlew.bat test
cd ..\db-api
mvn.cmd test
```

Vite 개발 서버도 유지됩니다. 루트의 `.env` 값을 현재 PowerShell 환경에 적용하거나 기본 포트를 사용한 뒤 `frontend`에서 `npm.cmd run dev`를 실행하십시오. Vite 프록시는 backend 분석 API와 db-api 조회/제보 API를 각각 연결합니다.

## 멀티모달 fixture

fixture는 실제 피싱 사이트에 접근하지 않는 합성 이미지와 `.example` URL만 사용합니다. `GEMINI_API_KEY`가 현재 환경에 있을 때만 실제 Gemini 호출을 실행합니다.

```powershell
cd .\multimodal-service
python .\run_fixture_tests.py normal_bank non_financial fake_bank card_capital internet_bank government_support
```

키가 없으면 위 fixture 실행을 건너뛰고 DOM 규칙 기반 대체 분석을 smoke test로 검증합니다. 키 값 자체를 로그나 결과 파일에 기록하지 마십시오.

## 멀티모달 HTTP 계약

Backend가 호출할 컨테이너 URL은 `http://multimodal-service:8002/v1/analyze`, 호스트에서 직접 확인할 URL은 `http://localhost:8002/v1/analyze`입니다. API는 Sandbox의 `requestedUrl`, `finalUrl`, `statusCode`, `title`, `html`, `screenshotBase64`, `error`를 그대로 받을 수 있으며 HTML에서 visible text, forms, buttons, links와 download 신호를 안전하게 추출합니다.

응답은 `verdict`, `risk_score`, `impersonation_type`, `impersonated_brand`, 네 가지 요청 여부 boolean, 한국어 `evidence` 배열로 구성됩니다. Screenshot과 HTML/Text가 모두 없거나 Sandbox 수집 실패만 전달되면 `NORMAL`이 아닌 `UNKNOWN`을 반환합니다. 세부 요청·응답과 오류 코드는 [multimodal-service/README.md](multimodal-service/README.md)를 확인하십시오.

## 안전 원칙

- 실제 피싱 URL에는 접속하지 않습니다.
- `.env`, API 키, 비밀번호, 학습 모델은 커밋하지 않습니다.
- Sandbox는 loopback/private/link-local/reserved 주소와 내부 DNS 결과를 차단합니다.
- 로컬 통합 결과는 [docs/local-integration-report.md](docs/local-integration-report.md)에 기록합니다.
