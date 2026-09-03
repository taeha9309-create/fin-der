# 통합 작업 정리 (2026-08-15)

팀원 4명이 각자 올린 코드를 실제로 연결해서 URL 입력부터 결과 저장까지
한 번에 동작하는지 확인하는 과정에서 수정한 내용을 정리한다.

## 1. `backend/` 충돌 해결 → `db-api/` 신설

`feat/sandbox-backend` PR이 `backend/` 폴더 안에 완전히 다른 백엔드
(Gradle, Spring Boot 4.1, Java 21, `com.phishing.backend`)를 기존 백엔드
(Maven, Spring Boot 2.7, Java 17, `com.leveragy`, MySQL 저장 담당)와
같은 경로에 얹으면서 생긴 문제.

- 파일명이 겹치지 않아 Git이 충돌 없이 자동 병합했지만, 실제로는 빌드
  도구 2개(`pom.xml` + `build.gradle`)와 서로 다른 Spring Boot 애플리케이션
  2개가 한 폴더에 공존하는 상태가 됨
- `application.yml`이 파일 하나뿐이라 한쪽 내용(MySQL 접속 정보, CORS 설정)이
  통째로 사라짐

**조치**: MySQL/JPA 저장 담당 코드를 `backend/` → `db-api/`로 이동 (포트 8081).
`backend/`는 이제 오케스트레이터(민성이 담당) 전용.

## 2. 오케스트레이션 배관 연결

기존에는 `frontend`가 `db-api`를 직접 호출해서 목업 점수만 저장했음.
이제 실제 파이프라인으로 연결:

```
frontend → backend(오케스트레이터) → ml-service(XGBoost)
                                    → sandbox(Playwright, 필요시)
                                    → multimodal-service(Gemini, 필요시)
                                    → db-api(MySQL 저장)
```

- `backend`에 `AnalysisOrchestrator` 추가: ml-service 호출 → `requires_deep_analysis`가
  true일 때만 sandbox 호출 → sandbox 성공 시에만 multimodal-service 호출 → db-api에 저장
- sandbox·multimodal 실패는 전체 요청을 막지 않고 저장되는 결과에 사유만 기록
  (`onErrorResume`) — 서비스 하나가 죽어도 나머지 파이프라인은 계속 동작
- `db-api`의 `AnalyzeRequest`에 `riskScore`/`mlResult`/`multimodalResult`/`xaiResult`/`finalResult`를
  선택 필드로 추가. 오케스트레이터가 계산한 값을 보내면 그대로 저장하고,
  비어 있으면 기존 키워드 기반 목업으로 동작 (단독 테스트 호환성 유지)
- `frontend`의 `/api` 프록시를 분리: `POST /api/v1/url-analysis`는 backend로,
  `GET /api/analyze/{id}`·`POST /api/reports`는 db-api로 직접

## 3. `multimodal-service` API 서버 신규 작성

기존엔 분석 로직(`analyzer.py` 등)만 있고 HTTP로 호출할 방법이 없었음.
`requirements.txt`와 `config.py`도 비어 있었음.

- `app/main.py` (FastAPI) 추가: `POST /v1/analyze`
  - sandbox가 base64로 주는 스크린샷을 `analyzer.py`가 요구하는 파일 경로로
    변환하는 어댑터 포함 (임시 파일 생성 후 분석, 끝나면 삭제)
  - `html`에서 `page_text`를 BeautifulSoup으로 추출
  - `GEMINI_API_KEY`가 없으면 가짜 결과를 만들지 않고 **503**을 반환
    (ml-service의 `model_loaded` 체크와 동일한 패턴)
- `requirements.txt` 채움, `ml-service`와 같은 스타일의 `Dockerfile` 추가
- backend 쪽 최종 판정 결합 로직은 임시로 "ml 또는 multimodal 중 하나라도
  고위험이면 PHISHING" (OR 방식). 정식 가중치 로직은 이후 XAI 담당이 정할 부분.

## 4. 프론트엔드 버그 수정

`ResultPage.jsx`가 `xaiResult`를 문자열 배열로만 가정하고 있었는데,
실제 ml-service는 `{feature, reason, direction, contribution}` 객체 배열을
반환해서 화면이 하얗게 깨지는(React 렌더링 에러) 문제가 있었음. 두 형태를
모두 처리하도록 수정.

## 5. 로컬에서 검증한 것

- MySQL(`finder` DB) + `db-api` + `ml-service`(합성 데이터로 임시 학습한
  XGBoost 모델) + `sandbox`(Playwright Chromium) + `backend` + `frontend`
  까지 전부 로컬에서 동시 실행
- 브라우저에서 실제 URL 입력 → 결과 화면 → 제보까지 end-to-end 확인
- `multimodal-service`는 `GEMINI_API_KEY` 미설정 상태에서 503을 정상 반환하고,
  파이프라인 전체는 계속 완료되는 것까지 확인 (진짜 Gemini 응답은 미검증)

## 6. 아직 남은 것

- `GEMINI_API_KEY` 설정 후 실제 Gemini 분석 결과 검증 (팀원 C)
- ml/multimodal 최종 결합 로직을 OR 방식에서 정식 가중치 로직으로 교체
- 이 브랜치(`feat/wire-orchestration-pipeline`)는 아직 `main`에 병합 전 —
  민성이 쪽 리뷰 후 병합 필요
- `sandbox`는 로컬 실행 시 Playwright Chromium 브라우저를 별도로 설치해야 함
  (`npx playwright install chromium`)
