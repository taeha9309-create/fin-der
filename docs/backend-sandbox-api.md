# Backend / Sandbox API

이 문서는 Backend가 Sandbox를 호출해 URL 페이지를 수집하고, 클라이언트에
동기 또는 비동기 분석 결과를 제공하는 현재 API 규격을 설명합니다.

## 서비스 주소

| 서비스 | Docker 내부 주소 | 로컬 접근 주소 |
| --- | --- | --- |
| Backend | `http://backend:8080` | `http://localhost:8080` |
| Sandbox | `http://sandbox:3001` | 외부 포트 미공개 |

클라이언트는 Sandbox를 직접 호출하지 않고 Backend API를 사용합니다.

### 요청 추적 ID

Backend는 모든 HTTP 응답에 `X-Request-Id` 헤더를 반환합니다. 클라이언트가
영문자, 숫자, `.`, `_`, `-`로 구성된 64자 이하의 `X-Request-Id`를 보내면 같은
값을 사용하며, 없거나 형식이 올바르지 않으면 UUID를 새로 생성합니다. 오류
응답 JSON에도 동일한 `requestId`가 포함됩니다.

```json
{
  "code": "INVALID_REQUEST",
  "message": "URL을 입력해주세요.",
  "requestId": "a00b180d-b40f-44d7-91ad-1dddf5f77291"
}
```

접근 로그는 query string을 제외한 HTTP method와 path, 상태 코드, 처리시간만
기록합니다. 오류 문의 시 `requestId`를 전달하면 Backend 로그와 연결할 수 있습니다.

### Backend 상태 확인

`GET /health`는 Backend가 HTTP 요청을 받을 준비가 되었는지 확인합니다.

```json
{
  "status": "UP",
  "service": "backend",
  "timestamp": "2026-09-02T12:00:00Z"
}
```

Docker Compose는 Sandbox, URL AI, 페이지 AI의 Health Check가 성공한 후
Backend를 시작합니다. 컨테이너 실행 상태와 실제 서비스 준비 상태를 구분하여
시작 직후 연결 종료 오류를 방지합니다.

## 동기 분석

### `POST /api/v1/url-analysis`

분석이 끝날 때까지 기다린 후 수집 결과를 반환합니다. 간단한 개발 확인과
기존 연동 호환성을 위해 유지하는 API입니다.

요청:

```json
{
  "url": "https://example.com"
}
```

성공 응답 주요 필드:

```json
{
  "schemaVersion": "1.0",
  "analysisId": "81beec56-edb1-43a2-937a-9f9974f584fd",
  "collectionStatus": "COMPLETED",
  "requestedUrl": "https://example.com/",
  "finalUrl": "https://example.com/",
  "redirectChain": [
    { "url": "https://example.com/", "statusCode": 200 }
  ],
  "statusCode": 200,
  "title": "Example Domain",
  "html": "<!doctype html>...",
  "htmlSizeBytes": 528,
  "text": "Example Domain...",
  "textSizeBytes": 129,
  "screenshotBase64": "iVBORw0KGgo...",
  "screenshotSizeBytes": 17883,
  "htmlPath": "/data/analyses/{analysisId}/page.html",
  "textPath": "/data/analyses/{analysisId}/page.txt",
  "screenshotPath": "/data/analyses/{analysisId}/screenshot.png",
  "inputs": [],
  "forms": [],
  "links": [
    { "text": "Learn more", "href": "https://iana.org/help/example-domains" }
  ],
  "domMetadataTruncated": {
    "inputs": false,
    "forms": false,
    "links": false
  },
  "network": {
    "requests": [
      {
        "url": "https://example.com/",
        "domain": "example.com",
        "method": "GET",
        "resourceType": "document",
        "hasPostData": false
      }
    ],
    "requestsTruncated": false,
    "downloadDetected": false
  },
  "loadTimeMs": 921,
  "error": null
}
```

`htmlPath`, `textPath`, `screenshotPath`는 Sandbox 컨테이너 내부 경로입니다.
Frontend가 이 경로로 직접 파일을 조회해서는 안 됩니다.

`inputs`, `forms`, `links`는 각 최대 200개, `network.requests`는 최대 500개를
수집합니다. 제한을 넘으면 대응하는 `truncated` 필드가 `true`가 됩니다.
Network URL에서는 사용자 정보, query string, fragment를 제거합니다. 입력값,
POST 본문, Cookie, Authorization 헤더는 수집하지 않습니다.

## 분석 결과 파일 조회

Sandbox가 저장한 파일은 Backend를 통해서만 조회합니다. Backend에는
`analysis_data` 볼륨이 읽기 전용으로 연결됩니다.

| Method | 경로 | Content-Type |
| --- | --- | --- |
| GET | `/api/analyses/{analysisId}/html` | `text/plain` |
| GET | `/api/analyses/{analysisId}/text` | `text/plain` |
| GET | `/api/analyses/{analysisId}/screenshot` | `image/png` |
| GET | `/api/analyses/{analysisId}/metadata` | `application/json` |

`analysisId`는 UUID 형식만 허용하며, 고정된 네 파일 외의 경로는 조회할 수
없습니다. 응답에는 `no-store`와 `nosniff` 보안 헤더가 적용됩니다.
수집된 HTML은 Backend 출처에서 스크립트로 실행되는 것을 막기 위해
`text/html`이 아닌 `text/plain`으로 제공합니다.

## 비동기 분석

### `POST /api/analyze`

분석 Job을 생성하고 HTTP `202 Accepted`로 작업 ID를 즉시 반환합니다.

요청:

```json
{
  "url": "https://example.com"
}
```

응답:

```json
{
  "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
  "status": "PENDING",
  "result": null,
  "errorCode": null,
  "errorMessage": null,
  "createdAt": "2026-08-23T01:00:00Z",
  "updatedAt": "2026-08-23T01:00:00Z"
}
```

### `GET /api/analyze/{analysisId}`

Job 상태를 조회합니다.

| 상태 | 의미 |
| --- | --- |
| `PENDING` | 대기열에서 실행을 기다리는 상태 |
| `RUNNING` | 이전 버전 호환용 실행 상태 |
| `URL_ANALYZING` | 1차 URL AI 분석 중 |
| `SANDBOX_COLLECTING` | Sandbox에서 페이지 자료 수집 중 |
| `PAGE_ANALYZING` | 2차 페이지·행동 AI 분석 중 |
| `FINALIZING` | 최종 위험 점수와 판정 생성 중 |
| `COMPLETED` | 분석 성공, `result`에 수집 결과 포함 |
| `FAILED` | 분석 실패, `errorCode`와 `errorMessage` 포함 |

후속 단계가 실패해도 이전 단계에서 성공한 결과는 유지됩니다. 예를 들어 페이지
AI 호출이 실패하면 다음과 같이 URL 분석과 Sandbox 수집 결과를 조회할 수 있습니다.

```json
{
  "status": "FAILED",
  "failedStage": "PAGE_ANALYZING",
  "urlAnalysis": { "riskScore": 42 },
  "result": { "collectionStatus": "COMPLETED" },
  "pageAnalysis": null,
  "finalAnalysis": null,
  "errorCode": "PAGE_ANALYSIS_FAILED",
  "errorMessage": "페이지 분석 AI가 요청을 처리하지 못했습니다."
}
```

Backend가 분석 중 재시작된 경우에도 저장된 중간 결과를 유지하고
`errorCode`를 `ANALYSIS_INTERRUPTED`로 기록합니다.

개발 환경의 `page-ai-mock`은 실패 흐름을 자동 검증하기 위한 테스트 전용 기능을
제공합니다. `ENABLE_TEST_FAILURES=true`일 때 요청 URL에
`finder_page_ai_fail=1`이 포함되면 HTTP 503을 반환합니다. 이 설정과 URL 표식은
통합 테스트에서만 사용하며 실제 운영 환경에서는 활성화하지 않습니다.

완료 응답:

```json
{
  "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
  "status": "COMPLETED",
  "urlAnalysis": {
    "serviceMode": "MOCK",
    "riskScore": 0,
    "label": "NORMAL",
    "requiresDeepAnalysis": true,
    "xaiReasons": [],
    "modelVersion": "mock-1.0"
  },
  "result": {
    "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
    "title": "Example Domain",
    "finalUrl": "https://example.com/",
    "text": "Example Domain...",
    "htmlSizeBytes": 559,
    "screenshotSizeBytes": 17883,
    "artifacts": {
      "html": "/api/analyses/{analysisId}/html",
      "text": "/api/analyses/{analysisId}/text",
      "screenshot": "/api/analyses/{analysisId}/screenshot",
      "metadata": "/api/analyses/{analysisId}/metadata"
    }
  },
  "pageAnalysis": {
    "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
    "serviceMode": "MOCK",
    "pageRiskScore": 0,
    "verdict": "UNKNOWN",
    "credentialIntent": false,
    "detectedSignals": [],
    "reasons": [],
    "confidence": 0.2
  },
  "finalAnalysis": {
    "policyMode": "TEMPORARY",
    "policyVersion": "temporary-weighted-v1",
    "riskScore": 0,
    "verdict": "NORMAL",
    "urlRiskScore": 0,
    "pageRiskScore": 0,
    "reasons": []
  },
  "errorCode": null,
  "errorMessage": null
}
```

비동기 Job의 `result`에는 원본 `html`, `screenshotBase64` 및 컨테이너 내부
파일 경로를 포함하지 않습니다. 원본 자료가 필요하면 `artifacts`의 Backend
조회 URL을 사용합니다. 이를 통해 Job 영속 파일과 API 응답 크기를 제한합니다.

현재 `pageAnalysis`는 실제 AI가 아닌 `page-ai-mock`의 연동 검증 결과입니다.
`serviceMode`가 `MOCK`이면 실제 피싱 판정으로 사용하면 안 됩니다. 실제 페이지
AI가 준비되면 `PAGE_ANALYSIS_BASE_URL`만 실제 서비스 주소로 교체합니다.
동일하게 `urlAnalysis.serviceMode`가 `MOCK`이면 연동 검증용 결과이며,
학습 모델이 준비되면 `URL_ANALYSIS_BASE_URL`을 `ml-service` 주소로 교체합니다.

`finalAnalysis`는 현재 URL 점수 40%, 페이지 점수 60%를 사용하는 임시 결합
정책입니다. `policyMode`가 `TEMPORARY`인 결과는 운영 판정 기준으로 사용하지
않으며, 1번 담당자가 검증한 정책이 확정되면 `FinalRiskPolicy` 구현을 교체합니다.

## 오류 응답

Sandbox에서 발생한 오류에는 요청 추적용 `analysisId`가 포함됩니다.

```json
{
  "analysisId": "41bd2e48-6725-4e07-8540-a0bb94ebdb6b",
  "code": "PRIVATE_ADDRESS_BLOCKED",
  "message": "내부 또는 비공개 IP 주소에는 접속할 수 없습니다.",
  "requestId": "a00b180d-b40f-44d7-91ad-1dddf5f77291"
}
```

주요 오류 코드:

| HTTP | 코드 | 의미 |
| --- | --- | --- |
| 400 | `URL_REQUIRED` | URL 누락 |
| 400 | `INVALID_URL` | URL 형식 오류 |
| 400 | `UNSUPPORTED_PROTOCOL` | HTTP·HTTPS 외 프로토콜 |
| 400 | `PRIVATE_ADDRESS_BLOCKED` | localhost·사설·내부 IP 차단 |
| 400 | `DNS_RESOLUTION_FAILED` | 도메인 조회 실패 |
| 404 | `ANALYSIS_NOT_FOUND` | 존재하지 않는 비동기 Job |
| 413 | `HTML_TOO_LARGE` | HTML 2MB 초과 |
| 413 | `TEXT_TOO_LARGE` | Text 1MB 초과 |
| 413 | `SCREENSHOT_TOO_LARGE` | Screenshot 10MB 초과 |
| 429 | `ANALYSIS_QUEUE_FULL` | 비동기 분석 대기열 초과 |
| 504 | `PAGE_LOAD_TIMEOUT` | 페이지 로딩 15초 초과 |
| 504 | `ANALYSIS_TIMEOUT` | 비동기 분석 파이프라인 전체 제한시간 초과 |
| 502 | `SANDBOX_UNAVAILABLE` | Backend에서 Sandbox 연결 실패 |

## 실행 제한 및 보관 정책

| 환경변수 | 기본값 | 설명 |
| --- | ---: | --- |
| `MAX_CONCURRENT_ANALYSES` | 2 | 동시에 실행하는 분석 수 |
| `MAX_QUEUED_ANALYSES` | 20 | 대기 가능한 Job 수 |
| `SANDBOX_RETRY_COUNT` | 1 | 연결 실패·timeout·5xx 재시도 횟수 |
| `ANALYSIS_TIMEOUT_SECONDS` | 90 | URL AI부터 최종 판정까지 전체 실행 제한시간 |
| `ANALYSIS_JOB_RETENTION_HOURS` | 24 | 완료·실패 Job 파일 보관 시간 |
| `ANALYSIS_JOB_CLEANUP_INTERVAL_MS` | 3600000 | 만료 Job 검사 주기(밀리초) |
| `LOG_MAX_SIZE` | 10m | Docker 로그 파일 하나의 최대 크기 |
| `LOG_MAX_FILES` | 3 | 서비스별 Docker 로그 파일 보관 개수 |
| `ANALYSIS_RETENTION_HOURS` | 24 | Sandbox 결과 파일 보관 시간 |
| `CLEANUP_INTERVAL_MINUTES` | 60 | 만료 파일 정리 주기 |

Job 상태는 Backend의 `analysis_job_data` Docker 볼륨에 저장됩니다. 현재 저장소는
독립 개발용 파일 구현이며, 팀의 DB API 규격이 확정되면 `AnalysisJobStore` 구현을
MySQL 방식으로 교체할 수 있습니다.

전체 분석 제한시간은 Job이 대기열에 머무는 시간에는 적용되지 않고 실제 분석이
시작된 뒤부터 적용됩니다. 제한시간이 지나면 진행 중인 호출을 취소하고 Job을
`FAILED`로 변경하며, `errorCode`는 `ANALYSIS_TIMEOUT`으로 기록합니다. 제한시간 전에
완료된 중간 단계 결과는 그대로 유지됩니다.

Backend는 정리 주기마다 저장된 Job 파일을 확인하여 보관기간이 지난
`COMPLETED`, `FAILED` Job을 메모리와 `analysis_job_data` 볼륨에서 삭제합니다.
`PENDING` 또는 분석 진행 중인 Job은 생성 시각과 관계없이 자동 삭제하지 않습니다.

Compose의 모든 서비스는 `json-file` 로그 드라이버를 사용하며 기본적으로 10MB
로그 파일을 서비스별 최대 3개까지 보관합니다. Backend 분석 로그에는 URL 원문,
HTML, 사용자 입력값을 기록하지 않고 `analysisId`, 처리 단계, 처리시간, 오류 코드만
남깁니다. 특정 분석 문제는 다음과 같이 ID로 검색할 수 있습니다.

```powershell
docker compose logs backend | Select-String "analysisId=분석-ID"
```

## PowerShell 사용 예시

```powershell
$body = @{ url = "https://example.com" } | ConvertTo-Json
$job = Invoke-RestMethod -Uri "http://localhost:8080/api/analyze" -Method Post -ContentType "application/json" -Body $body
$result = Invoke-RestMethod -Uri ("http://localhost:8080/api/analyze/" + $job.analysisId)
$result.status
```

전체 smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```
