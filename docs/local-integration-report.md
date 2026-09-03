# Local integration report — 2026-08-24

## 작업 전 Git 상태

- 새 clone의 `main`은 `origin/main`과 동일한 `0b7b123`이었고 작업 트리는 깨끗했다.
- 통합 기준 브랜치는 `origin/feat/wire-orchestration-pipeline`의 `8812e66`이다.
- 두 브랜치의 merge base는 `a77fcd8`이다.
- 로컬 브랜치 `local/integration-validation-20260824`를 통합 브랜치에서 생성했다.
- `git merge --no-commit --no-ff origin/main`은 충돌 없이 완료됐다. 커밋과 push, PR 생성은 수행하지 않았다.
- `main`에서 새로 추적되던 `ml-service/artifacts/url_xgb.joblib`은 로컬 통합 index에서 제외했다. 모델과 metrics는 `.gitignore` 아래 로컬에서만 생성된다.

## 통합 및 수정 내용

### Main ML 작업 보존

- 금융 브랜드 registry, 공식 URL/공공 사례/외부 검증 seed, dataset 준비 코드와 23개 최신 `FEATURE_NAMES`를 병합했다.
- 소량 `sample_urls.csv`에서도 분할을 학습할 수 있도록 학습 파라미터의 `min_child_weight`와 트리 크기를 조정했다. 피처와 금융 도메인 규칙, SHAP 출력 계약은 유지했다.
- `requires_deep_analysis`는 반올림된 `risk_score >= 40`과 정확히 일치하게 했다.
- `scripts/bootstrap-ml.ps1`과 Docker 이미지 빌드 시 artifact 부재 자동 학습 경로를 추가했다.

### 전체 오케스트레이션 및 Compose

- `database`, `db-api`, `ml-service`, `sandbox`, `multimodal-service`, `backend`, `frontend` 7개 서비스를 루트 `compose.yaml`에 연결했다.
- 내부 URL은 Compose 서비스명을 사용하며 DB와 각 주요 서비스 healthcheck/의존성 대기를 추가했다.
- 로컬 MySQL 3306 충돌을 피하도록 MySQL 호스트 기본 포트는 3307, 컨테이너 포트는 3306으로 분리했다.
- backend는 ML/Sandbox/Multimodal/db-api URL을 환경변수로 받는다.
- frontend용 multi-stage Dockerfile과 Nginx 프록시/SPA 설정을 추가하면서 기존 Vite 개발 프록시는 유지했다.
- Nginx 요청 제한은 25MB, Sandbox JSON 1MB/HTML 2MB/screenshot 10MB, backend WebClient buffer는 25MB다. 기존 단계별 timeout과 fallback 경로를 유지했다.

### 멀티모달 안정화

- 환경 기반 설정과 Pydantic 입력/출력 모델을 구현했다.
- 순수 JSON, 공백 포함 JSON, `json` 코드블록 응답을 파싱하고 잘못된 JSON/필수 필드 누락을 명확히 거부한다.
- 6개 fixture의 Windows 절대경로를 프로젝트 상대경로로 바꿨다.
- 실제 fixture 결과를 저장소 밖 임시 디렉터리에 쓸 수 있도록 `--results-dir`을 추가했다.
- `normal_bank`와 `non_financial`이 금융 사칭 또는 high-risk로 오탐되면 fixture 실행이 실패하도록 했다.
- 테스트 중 발견된 기존 Git 추적 `__pycache__/*.pyc` 6개를 제거했다. 소스에는 영향이 없고 Git 이력에서 복구 가능하다.

### 프론트/API/스모크

- XAI 문자열 배열과 `{feature, reason, direction, contribution}` 객체 배열을 모두 React에서 렌더링하며 contribution을 표시한다.
- backend/db-api health endpoint를 추가했다.
- smoke test는 7개 컨테이너/health 대기, frontend HTTP, 정상·합성 URL 분석, DB 조회, 내부 주소 차단, Gemini 설정/fallback 상태, 제보 API를 검증한다.
- README와 `.env.example`을 실제 포트 및 Windows 재실행 절차에 맞췄다. `.env.example`에는 실제 비밀값이 없다.

## 서비스별 실행 결과

| 서비스 | 결과 | 확인 내용 |
| --- | --- | --- |
| database | 성공 | MySQL 8.0, host 3307 → container 3306, healthy |
| db-api | 성공 | MySQL 연결/JPA 초기화, 저장·조회·제보, healthy |
| ml-service | 성공 | `model_loaded=true`, 23개 피처 schema 일치, healthy |
| sandbox | 부분 성공 | API/health/내부 주소 차단 성공. 이 PC의 Docker 외부 DNS 장애로 `example.com` 수집은 fallback |
| multimodal-service | 성공 | health와 실제 Gemini fixture 6개 성공 |
| backend | 성공 | ML 결과, 조건부 Sandbox, fallback, db-api 저장, healthy |
| frontend | 성공 | Nginx HTTP/프록시와 Vite production build 성공, healthy |

## 테스트 결과

성공:

- `docker compose config --quiet`
- ML: 시스템 Python `5 passed`, 독립 `.venv` `5 passed`
- ML bootstrap 재학습: 23개 피처 schema 일치, 샘플 평가 ROC-AUC 1.0
- ML 안전 입력: `https://example.com` 8/NORMAL, 합성 의심 URL 90/PHISHING
- Multimodal parser: `4 passed`
- Frontend: `npm ci`, `npm run build`
- Sandbox: `npm ci`, `node --check server.js`, `node --check urlValidator.js`, 내부 URL 400 차단
- Backend: Gradle `BUILD SUCCESSFUL`
- db-api: 호스트 Maven 부재 대신 Docker Maven build stage에서 `mvn -q test` 성공
- Docker: 전체 이미지 build 성공, 7개 컨테이너 healthy
- 전체 `scripts/smoke-test.ps1` 성공
- frontend Nginx 프록시를 통한 분석/저장/조회 성공: 정상 id 3, 합성 의심 id 4
- 저장 필드 `riskScore`, `finalResult`, `mlResult`, `multimodalResult`, `xaiResult` 및 XAI 배열 확인
- 제보 API 성공

초기 실패 후 수정:

- Docker Desktop 엔진 미기동 → 로컬 엔진 시작 후 재실행.
- 호스트 3306 사용 중 → DB host 포트를 3307로 분리.
- ML Docker context에서 `data/` 제외 → raw/processed만 제외하도록 수정.
- Nginx health의 IPv6 localhost 및 SPA 문서 root 누락 → IPv4 health와 명시적 root 추가.
- PowerShell 5 `Invoke-WebRequest` 파서 오류 → `-UseBasicParsing` 적용.
- npm 사용자 캐시 쓰기/네트워크 제한 → 저장소 내부 ignore 캐시와 승인된 네트워크 실행으로 완료.

## Gemini 실제 실행 여부

- 실행됨. 키 값은 출력·파일 기록하지 않았다.
- `normal_bank`, `non_financial`, `fake_bank`, `card_capital`, `internet_bank`, `government_support` 6개 실제 fixture가 모두 성공했다.
- `normal_bank`와 `non_financial` 오탐 방지 검증도 성공했다.
- 결과는 일회성 컨테이너의 `/tmp/results`에만 기록됐고 저장소에는 쓰지 않았다.

## 남은 문제와 환경 제한

- Docker 런타임의 외부 DNS가 `example.com`에 대해 `ENOTFOUND/EAI_AGAIN`을 반환했다. 8.8.8.8을 명시한 임시 컨테이너도 실패해 이 PC/네트워크의 Docker DNS 제한으로 판단한다. Sandbox 보안 검사를 우회하거나 외부 IP를 하드코딩하지 않았다. 따라서 합성 의심 E2E는 Sandbox 오류를 기록하고 ML 결과를 정상 저장하는 fallback 경로로 완료됐다.
- 인앱 브라우저 런타임에 사용 가능한 브라우저 인스턴스가 없어 실제 클릭/화면 캡처 검증은 수행하지 못했다. frontend production build, HTTP, Nginx 프록시와 결과 JSON/XAI 계약은 통과했다.
- frontend `npm audit`은 기존 잠금파일에서 moderate 3건/high 2건을 보고했다. 강제 major upgrade는 통합 범위를 벗어나 적용하지 않았다.
- 샘플 7행으로 만든 모델은 통합 테스트 전용이며 운영 품질 모델이 아니다.
- ML/멀티모달 결합 OR 규칙은 기존 주석대로 임시 상태이며 최종 정책으로 확정하지 않았다.
- PowerShell profile 실행 정책 경고가 외부 명령마다 출력됐지만 모든 명령의 실제 종료 코드와는 무관했다.

## Windows 재실행 명령

저장소 루트 PowerShell:

```powershell
Copy-Item .env.example .env
# 필요한 경우 .env에 GEMINI_API_KEY를 로컬에서만 입력
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-ml.ps1 -Force
docker compose config
docker compose up --build -d
docker compose ps
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

Docker DNS가 복구된 뒤 Sandbox 포함 E2E를 다시 확인하려면 마지막 smoke 명령을 재실행한다. GitHub 원격에는 아무 변경도 전송하지 않았다.
