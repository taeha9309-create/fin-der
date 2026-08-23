# Backend / Sandbox API

이 문서는 Backend가 Sandbox를 호출해 URL 페이지를 수집하고, 클라이언트에
동기 또는 비동기 분석 결과를 제공하는 현재 API 규격을 설명합니다.

## 서비스 주소

| 서비스 | Docker 내부 주소 | 로컬 접근 주소 |
| --- | --- | --- |
| Backend | `http://backend:8080` | `http://localhost:8080` |
| Sandbox | `http://sandbox:3001` | 외부 포트 미공개 |

클라이언트는 Sandbox를 직접 호출하지 않고 Backend API를 사용합니다.

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
  "analysisId": "81beec56-edb1-43a2-937a-9f9974f584fd",
  "requestedUrl": "https://example.com/",
  "finalUrl": "https://example.com/",
  "redirectChain": ["https://example.com/"],
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
  "loadTimeMs": 921,
  "error": null
}
```

`htmlPath`, `textPath`, `screenshotPath`는 Sandbox 컨테이너 내부 경로입니다.
Frontend가 이 경로로 직접 파일을 조회해서는 안 됩니다.

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
| `RUNNING` | Sandbox 분석 실행 중 |
| `COMPLETED` | 분석 성공, `result`에 수집 결과 포함 |
| `FAILED` | 분석 실패, `errorCode`와 `errorMessage` 포함 |

완료 응답:

```json
{
  "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
  "status": "COMPLETED",
  "result": {
    "analysisId": "5735712f-f13b-41fe-afe6-2b1ffb6b6423",
    "title": "Example Domain",
    "finalUrl": "https://example.com/",
    "text": "Example Domain..."
  },
  "errorCode": null,
  "errorMessage": null
}
```

## 오류 응답

Sandbox에서 발생한 오류에는 요청 추적용 `analysisId`가 포함됩니다.

```json
{
  "analysisId": "41bd2e48-6725-4e07-8540-a0bb94ebdb6b",
  "code": "PRIVATE_ADDRESS_BLOCKED",
  "message": "내부 또는 비공개 IP 주소에는 접속할 수 없습니다."
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
| 504 | `ANALYSIS_TIMEOUT` | 전체 Sandbox 처리 30초 초과 |
| 502 | `SANDBOX_UNAVAILABLE` | Backend에서 Sandbox 연결 실패 |

## 실행 제한 및 보관 정책

| 환경변수 | 기본값 | 설명 |
| --- | ---: | --- |
| `MAX_CONCURRENT_ANALYSES` | 2 | 동시에 실행하는 분석 수 |
| `MAX_QUEUED_ANALYSES` | 20 | 대기 가능한 Job 수 |
| `SANDBOX_RETRY_COUNT` | 1 | 연결 실패·timeout·5xx 재시도 횟수 |
| `ANALYSIS_RETENTION_HOURS` | 24 | Sandbox 결과 파일 보관 시간 |
| `CLEANUP_INTERVAL_MINUTES` | 60 | 만료 파일 정리 주기 |

Job 상태는 Backend의 `analysis_job_data` Docker 볼륨에 저장됩니다. 현재 저장소는
독립 개발용 파일 구현이며, 팀의 DB API 규격이 확정되면 `AnalysisJobStore` 구현을
MySQL 방식으로 교체할 수 있습니다.

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
