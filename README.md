# fin-der

금융 피싱 URL을 단계적으로 분석하는 팀 프로젝트입니다. URL 기반 1차 탐지,
격리 브라우저 수집, 멀티모달 2차 분석, 통합 API와 사용자 화면을 하나의
모노레포에서 관리합니다.

## 분석 흐름

1. `ml-service`가 URL 특징, XGBoost, 금융기관 도메인 규칙으로 1차 위험도를 계산합니다.
2. 추가 분석이 필요한 URL은 `sandbox`의 격리된 Chromium 환경에서 열립니다.
3. `multimodal-service`가 스크린샷과 HTML을 분석합니다.
4. `backend`가 결과를 통합하고 `frontend`에 제공합니다.

## 디렉터리

| 경로 | 역할 |
| --- | --- |
| `frontend/` | React 사용자 화면 |
| `backend/` | Spring Boot 오케스트레이터 (Sandbox 호출) |
| `db-api/` | Spring Boot, MySQL 저장/조회 API (`/api/analyze`, `/api/reports`) — `backend/`와 역할 정리 필요, 논의 중 |
| `sandbox/` | Playwright 및 Chromium 격리 분석 |
| `ml-service/` | XGBoost, SHAP, 금융기관 도메인 규칙 기반 1차 분석 |
| `multimodal-service/` | 스크린샷 및 HTML 기반 2차 분석 |
| `database/` | SQL 스키마와 마이그레이션 |
| `docs/` | 아키텍처와 API 문서 |
| `scripts/` | 실행 및 통합 테스트 스크립트 |

## 시작하기

```bash
cp .env.example .env
docker compose up --build
```

현재는 팀 개발을 위한 기본 골격입니다. 각 서비스가 구현되면
`compose.yaml`에 해당 컨테이너 설정을 추가합니다.

Backend와 Sandbox의 요청·응답 규격은
[Backend / Sandbox API](docs/backend-sandbox-api.md)에서 확인할 수 있습니다.

## Backend/Sandbox smoke test

Docker 서비스가 실행 중인 상태에서 프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

이 스크립트는 동기 분석, HTML·Text·Screenshot 저장, Redirect 결과,
비동기 Job 완료, Job 파일 영속화, 내부 주소 차단 및 404 응답을 자동으로 확인합니다.

## 1차 탐지 코드 이전

기존 XGBoost/SHAP 코드는 `ml-service/` 아래에 배치합니다. 권장 구조는 다음과 같습니다.

```text
ml-service/
├─ src/          # features.py, domain_rules.py 등
├─ data/         # 공개 가능한 기준 데이터
├─ artifacts/    # 학습 모델 및 평가 결과
├─ tests/
├─ train.py
├─ predict.py
├─ stage1.py
└─ requirements.txt
```

대용량 데이터, 학습된 모델, 비밀키와 로컬 환경 파일은 Git에 올리지 않습니다.

## 협업 규칙

- 기능별 브랜치를 만들고 Pull Request로 `main`에 병합합니다.
- 환경 변수는 `.env.example`에 이름과 예시만 기록합니다.
- 서비스 간 요청/응답 형식은 `docs/`에서 함께 관리합니다.

