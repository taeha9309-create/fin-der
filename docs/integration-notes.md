# 통합 작업 정리 (feat/week4-ux-polish PR)

이 브랜치 하나에 최근 작업이 전부 쌓여 있습니다. 무엇이 바뀌었는지, 팀원별로 뭘
확인/추가해야 하는지 정리합니다.

## 한 줄 요약

각자 올린 코드가 실제로 서로 호출하도록 연결했고, MVP 필수 화면(로딩·위험도
시각화·이력·관리자·Threat Intelligence)을 만들었습니다. `multimodal-service`만
API 키가 없어서 실제 AI 응답 확인이 안 된 상태이고, 나머지는 로컬에서 브라우저로
전부 실제 동작 확인했습니다.

## 1. `backend/` 충돌 해결 → `db-api/` 신설

`feat/sandbox-backend` PR이 `backend/`에 완전히 다른 백엔드(Gradle, Spring Boot
4.1, Java 21, `com.phishing.backend`)를 기존 백엔드(Maven, Spring Boot 2.7,
Java 17, `com.leveragy`, MySQL 저장 담당)와 같은 경로에 얹으면서 생긴 충돌입니다.
Git이 파일명이 안 겹쳐서 자동 병합했지만 `application.yml` 하나뿐이라 DB 설정이
날아가는 등 실제로는 둘 다 안 돌아가는 상태였습니다.

**조치**: MySQL/JPA 저장 담당 코드를 `backend/` → `db-api/`로 이동(포트 8081).
`backend/`는 이제 오케스트레이터(민성이 담당) 전용입니다.

## 2. 오케스트레이션 연결

```
frontend → backend(오케스트레이터, 8080)
              → ml-service(8001)         1차 XGBoost 위험도
              → sandbox(3001, 필요시만)   Screenshot/HTML 수집
              → multimodal-service(8002, sandbox 성공시만)  Gemini 판정
              → db-api(8081)             최종 결과 저장
```

- `backend`의 `AnalysisOrchestrator`가 위 순서로 호출합니다. `ml-service`가
  `requires_deep_analysis=true`를 줄 때만 `sandbox`를 부르고, `sandbox`가 성공해
  스크린샷을 받았을 때만 `multimodal-service`를 부릅니다.
- 중간에 하나가 실패해도(타임아웃, 503 등) 전체 요청이 죽지 않고, 실패 사유만
  기록한 채로 나머지 결과를 `db-api`에 저장합니다(`onErrorResume`).
- 최종 판정 결합은 지금 **임시로 OR 방식**입니다: ml 또는 multimodal 둘 중
  하나라도 고위험이면 `PHISHING`. 정식 가중치 로직은 김태하님이 3주차 항목으로
  정하기로 되어 있던 부분이라 비워뒀습니다 (`AnalysisOrchestrator.combineFinalResult`).

## 3. `multimodal-service` API 서버 신규 작성

기존엔 분석 로직(`analyzer.py` 등)만 있고 HTTP로 호출할 방법이 없었고,
`requirements.txt`/`config.py`도 빈 파일이었습니다.

- `app/main.py` (FastAPI) 추가: `POST /v1/analyze`
  - sandbox가 base64로 주는 스크린샷을 `analyzer.py`가 요구하는 파일 경로로
    바꿔주는 어댑터 포함
  - `html`에서 `page_text`를 BeautifulSoup으로 추출해서 채움
  - **`GEMINI_API_KEY`가 없으면 가짜 결과를 만들지 않고 503을 반환**합니다
    (ml-service의 `model_loaded` 체크와 같은 패턴). 팀원 C가 키를 `.env`에
    넣으면 코드 수정 없이 바로 동작합니다.
- `requirements.txt` 채움, `ml-service`와 같은 스타일의 `Dockerfile` 추가

## 4. db-api: 저장 API 확장

- `POST /api/analyze`: 오케스트레이터가 계산한 값(`riskScore`, `mlResult` 등)을
  이미 채워서 보내면 그대로 저장하고, 비어 있으면 기존 키워드 목업으로 동작
  (단독 테스트 호환성 유지)
- `GET /api/analyze`: 전체 분석 이력 조회 (최신순) — History 화면용
- `GET /api/reports?status=`: 상태별 제보 필터
- `PATCH /api/reports/{id}`: 제보 상태 변경 (`PENDING` / `CONFIRMED_PHISHING` /
  `FALSE_POSITIVE`)
- `CorsConfig`에 `PATCH`가 빠져 있던 버그 수정 (관리자 페이지 상태변경 버튼이
  403으로 막혔던 원인)

## 5. 프론트엔드 새 화면 / 개선

- **로딩 화면**: 분석 중 스피너 + 파이프라인 단계별 안내 문구
- **위험도 게이지**: 숫자 대신 원형 SVG 게이지, PHISHING/SUSPICIOUS/NORMAL
  기준(70/40)과 동일한 색상
- **분석 이력** (`/history`): 지금까지 검사한 URL 전체 목록
- **관리자 Dashboard** (`/admin`): 제보 확인, 피싱 확정/오탐 처리, 상태 필터
  + URL 검색. **로그인 없음** — URL만 알면 누구나 접근 가능한 상태
- **Threat Intelligence** (`/threat-intel`): 피싱 확정된 URL만 공개 목록
- **모바일 반응형 버그 수정**: 좁은 화면에서 버튼 글자가 중간에 잘리던 문제
- **에러 화면**: 공통 에러 컴포넌트(재시도 버튼) + 404 페이지 + 렌더링 크래시
  방지용 ErrorBoundary
- **신고 UX**: 사유 빠른 선택 칩 4개, 제출 실패 시 에러 표시

## 로컬 실행 순서

```
1. MySQL: finder DB/계정 준비 후 database/schema.sql 적용
2. db-api:  cd db-api  && mvn spring-boot:run           (8081)
3. ml-service: 학습된 모델(artifacts/url_xgb.joblib) 필요.
   python -m src.train --data <csv> --output artifacts/url_xgb.joblib
   후 uvicorn src.api:app --port 8001
4. sandbox: npm install && npx playwright install chromium 후
   node server.js                                        (3001)
5. multimodal-service: pip install -r requirements.txt,
   GEMINI_API_KEY 설정 후 (app 폴더 안에서) uvicorn main:app --port 8002
6. backend: ./gradlew bootRun                             (8080, JDK 21 필요)
7. frontend: npm install && npm run dev                   (3000)
```

서비스 하나가 없어도 나머지는 동작합니다 (없는 서비스 호출만 실패로 기록됨).

## 팀원별로 확인/해야 할 일

| 담당 | 할 일 |
|---|---|
| **민성이** | `backend/AnalysisOrchestrator`에 제가 추가한 로직 리뷰 (원래 담당 영역). Docker Compose로 전체 스택 한 번에 띄우는 것 아직 안 해봄. 관리자 로그인(인증) 필요 |
| **김태하** | `AnalysisOrchestrator.combineFinalResult`의 임시 OR 방식을 정식 가중치 로직으로 교체. 실데이터셋으로 재학습 필요(지금 모델은 제가 커넥션 테스트용으로 만든 소규모 합성 데이터로 학습한 것) |
| **팀원 C** | `GEMINI_API_KEY`를 `.env`에 추가하면 바로 실제 Gemini 응답 테스트 가능. 실제 샘플로 프롬프트/스키마 검증 필요 |
| **팀원 D (나)** | Threat Intelligence/관리자 로그인 연동, 신고 유형 세분화 등 3~4주차 잔여 항목 |

## 아직 남은 것

- `GEMINI_API_KEY` 설정 후 실제 Gemini 분석 결과 검증
- ml/multimodal 최종 결합 로직 정식화
- 관리자 로그인(인증)
- Docker Compose로 전체 스택 통합 실행 검증
- 이 브랜치는 아직 `main`에 병합 전 — 민성이 리뷰 후 병합 필요
