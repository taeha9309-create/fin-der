# fin-der 2차 로컬 인수 테스트 보고서

- 수행일: 2026-08-24 (Asia/Seoul)
- 프로젝트: `C:\codex-work\fin-der-0824`
- 시작 브랜치: `local/integration-validation-20260824`
- 시작 HEAD: `8812e66fe53bdc38fa17de7c90fe2f4b45124c6a`
- 기준 upstream: `origin/feat/wire-orchestration-pipeline`
- 기존 `origin/main --no-commit` 병합은 재수행하지 않았다.
- commit, push, PR 생성, 원격 브랜치 수정, `git add`, `git reset`, `git restore`, `git checkout`, `git clean`은 수행하지 않았다.

## 결론

- Docker Compose 7개 서비스가 재빌드 후 모두 `healthy`이다.
- 국내 금융·공공기관 정상 캡처 16개는 16개 모두 분석 완료, 오탐 0개(0%)였다.
- 기존 합성 fixture 6개는 6개 모두 기대 결과와 일치했다.
- ML, multimodal parser, frontend production build, backend, db-api, Sandbox 보안, 전체 smoke test가 모두 최종 통과했다.
- Docker 내부 `example.com` DNS는 `ENOTFOUND`로 계속 실패한다. Sandbox의 SSRF 차단은 그대로 유지됐고, backend는 ML/XAI fallback 결과를 DB에 저장했다.
- 브라우저 제어 런타임에 연결 가능한 Chrome/Edge/in-app 브라우저가 0개여서 실제 UI 자동화와 자동 스크린샷은 수행하지 못했다. 아래에 정확한 수동 절차를 남겼다.

## Git 상태와 staged 변경 보존

변경 전 기록:

```text
## local/integration-validation-20260824...origin/feat/wire-orchestration-pipeline
55 staged files
git diff --cached --stat: 55 files changed, 1191 insertions(+), 259 deletions(-)
git diff --stat: 출력 없음
```

시작 시 `git status --short --branch`에 표시된 기존 변경은 모두 index에 staged된 상태였다. 이번 작업에서는 index 쓰기 명령을 실행하지 않았으며, 종료 시 cached stat도 시작 시점과 동일하다. 이번 작업의 저장소 파일 두 개는 untracked working tree 파일로 남겼다.

로컬 데이터 보호를 위해 저장소 파일인 `.gitignore`를 추가 변경하지 않고 `.git/info/exclude`에 `local-test-data/`를 추가했다. 확인 결과 평가 JSON은 이 로컬 exclude 규칙에 의해 무시된다. `.env`, 로컬 캡처, 원본 Gemini 응답, 평가 결과, 모델 artifact를 새로 Git 추적하지 않았다. `git ls-files` 확인에서 해당 범위에는 기존 `ml-service/artifacts/.gitkeep`만 있었다.

## 이번 작업에서 수정한 파일

| 파일 | 상태 | 내용 |
| --- | --- | --- |
| `.git/info/exclude` | 로컬 Git 메타데이터, 비추적 | `local-test-data/` 제외 규칙 추가 |
| `scripts/evaluate-domestic-captures.py` | untracked/unstaged | manifest 기반 1회 호출 평가, 원문·CSV·JSON 저장 |
| `docs/domestic-acceptance-report.md` | untracked/unstaged | 이 보고서 |

프로덕션 API 계약, ML 모델, orchestration 결합 규칙, Sandbox SSRF 정책은 변경하지 않았다. 정상/합성 평가에서 오탐·미탐이 없었으므로 prompt_builder, 전처리, Gemini 응답, response_parser, schema 매핑, backend 결합 로직도 수정하지 않았다.

## 로컬 테스트 데이터와 재현 방법

필수 폴더 `local-test-data\fin-der-domestic-captures-20260824`와 `screenshots`, `manifest.csv`, `README.md`를 확인했다. manifest에는 평가 대상 16개 행이 있고 screenshots 폴더에는 추가 캡처를 포함해 총 37개 파일이 있다. 이번 필수 평가는 manifest의 16개만 사용했다.

재현 명령은 다음과 같다. API 키는 Compose 환경을 통해 전달되며 값은 출력하지 않는다. 키가 없으면 스크립트가 모든 행을 `SKIPPED`로 기록한다. 키가 있으면 각 manifest 행에 정확히 한 번만 `generate_content`를 호출한다.

```powershell
$resultDir = 'C:\codex-work\fin-der-0824\local-test-data\fin-der-domestic-captures-20260824\evaluation-results-second-pass'
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
docker compose run --rm --no-deps `
  -v "C:\codex-work\fin-der-0824\local-test-data\fin-der-domestic-captures-20260824:/data:ro" `
  -v "C:\codex-work\fin-der-0824\scripts\evaluate-domestic-captures.py:/tmp/evaluate-domestic-captures.py:ro" `
  -v "${resultDir}:/results" `
  multimodal-service python /tmp/evaluate-domestic-captures.py `
  --manifest /data/manifest.csv --screenshots-dir /data/screenshots --output-dir /results
```

결과 경로:

- 정규화 CSV: `local-test-data/fin-der-domestic-captures-20260824/evaluation-results-second-pass/domestic-results.csv`
- 정규화 JSON: `local-test-data/fin-der-domestic-captures-20260824/evaluation-results-second-pass/domestic-results.json`
- 요약: `local-test-data/fin-der-domestic-captures-20260824/evaluation-results-second-pass/summary.json`
- 원본 응답 16개: `local-test-data/fin-der-domestic-captures-20260824/evaluation-results-second-pass/raw-responses/`

## 정상 캡처 16개 평가

공통 모델은 `gemini-3.1-flash-lite-preview`, prompt version은 `mm_prompt_v1`이며 모든 오류 필드는 비어 있다. `low`는 요구사항의 low-risk 계열로 판정했다. 공식 기관/브랜드 인식 자체는 허용하고, `is_financial_impersonation=true` 또는 low 계열이 아닌 위험도만 오탐으로 계산했다.

| filename | institution | status | impersonation | brand | category | attack | score | risk | confidence | reasons | model | prompt | error |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| kb_normal_home_official_20260824.jpg | KB국민은행 | completed | false | KB국민은행 | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| woori_normal_home_official_20260824.jpg | 우리은행 | completed | false | 우리은행 | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| hana_normal_home_official_20260824.jpg | 하나은행 | completed | false | 하나은행 | bank | unknown | 0 | low | 1.00 | OFFICIAL_URL_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| nh_normal_home_official_20260824.jpg | NH농협은행 | completed | false | NH농협은행 | bank | unknown | 5 | low | 0.95 | OFFICIAL_URL_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| ibk_normal_home_official_20260824.jpg | IBK기업은행 | completed | false | IBK기업은행 | bank | unknown | 0 | low | 1.00 | OFFICIAL_URL_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| kakaobank_normal_home_official_20260824.jpg | 카카오뱅크 | completed | false | kakaobank | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| kbank_normal_home_official_20260824.jpg | 케이뱅크 | completed | false | kbank | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| tossbank_normal_home_official_20260824.jpg | 토스뱅크 | completed | false | tossbank | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| citibank_normal_home_official_20260824.jpg | 한국씨티은행 | completed | false | 한국씨티은행 | bank | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH; LEGITIMATE_CONTENT_STRUCTURE | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| fsc_normal_home_official_20260824.jpg | 금융위원회 | completed | false |  | government | unknown | 0 | low | 1.00 | OFFICIAL_GOVERNMENT_SITE | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| fss_normal_home_official_20260824.jpg | 금융감독원 | completed | false | 금융감독원 | government | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH; LEGITIMATE_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| kisa_normal_home_official_20260824.jpg | 한국인터넷진흥원 | completed | false |  | unknown | unknown | 0 | low | 1.00 | OFFICIAL_GOVERNMENT_WEBSITE | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| nps_normal_home_official_20260824.jpg | 국민연금공단 | completed | false |  | government | unknown | 0 | low | 1.00 | OFFICIAL_GOVERNMENT_SITE | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| nts_normal_home_official_20260824.jpg | 국세청 | completed | false | 국세청 | government | unknown | 0 | low | 1.00 | OFFICIAL_GOVERNMENT_URL; AUTHENTIC_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| korea_normal_home_official_20260824.jpg | 대한민국 정책브리핑 | completed | false |  | government | unknown | 5 | low | 1.00 | OFFICIAL_GOVERNMENT_WEBSITE | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |
| bok_normal_home_official_20260824.jpg | 한국은행 | completed | false | 한국은행 | government | unknown | 0 | low | 1.00 | OFFICIAL_DOMAIN_MATCH; AUTHENTIC_CONTENT | gemini-3.1-flash-lite-preview | mm_prompt_v1 |  |

- 성공: 16/16
- 오탐: 0/16
- 오탐률: 0.00%
- API/파서 오류 또는 SKIPPED: 0

## 기존 합성 fixture 재검증

실제 피싱 URL에는 접속하지 않았고 기존 로컬 이미지와 `.example` URL만 사용했다. 결과는 `local-test-data/fin-der-domestic-captures-20260824/fixture-results-second-pass/`에 저장했다.

| fixture | 기대 | impersonation | score | risk | brand | category | attack | confidence | 결과 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| normal_bank | 정상 금융 | false | 0 | low | KB국민은행 | bank | unknown | 1.00 | PASS |
| non_financial | 정상 비금융 | false | 10 | low | 빈 값 | unknown | unknown | 0.95 | PASS |
| fake_bank | 금융 사칭 | true | 85 | high_risk_suspected | KB국민은행 | bank | credential_theft | 0.95 | PASS |
| card_capital | 금융 사칭 | true | 95 | high_risk_suspected | KB캐피탈 | capital | loan_scam | 0.95 | PASS |
| internet_bank | 금융 사칭 | true | 95 | high_risk_suspected | kakaobank | bank | credential_theft | 0.98 | PASS |
| government_support | 정부 사칭 | true | 95 | high_risk_suspected | 정부24 | government | government_support_scam | 0.98 | PASS |

- 성공: 6/6
- 실패: 0/6

## 서비스별 및 회귀 테스트 결과

| 대상 | 명령/검증 | 최종 결과 |
| --- | --- | --- |
| Compose | `docker compose up --build -d`, `docker compose ps` | PASS, 7/7 healthy |
| database | healthcheck 및 smoke 저장/조회 | PASS |
| db-api | Maven `mvn -q test`, 분석 ID 조회, 제보 API | PASS |
| ml-service | `.venv\Scripts\python.exe -m pytest` | PASS, 5 passed |
| multimodal-service | `pytest -q tests` | PASS, 4 passed; read-only mount 때문에 pytest cache 경고 2개만 발생 |
| frontend | `npm.cmd run build`, frontend HTTP 200 | PASS, Vite production build 성공 |
| backend | `gradlew.bat test --no-daemon` | PASS, BUILD SUCCESSFUL |
| sandbox | `node --check` 2개, loopback 400 `PRIVATE_ADDRESS_BLOCKED` | PASS |
| 전체 smoke | `scripts/smoke-test.ps1` | PASS, 정상 id 7/risk 8/NORMAL, 합성 id 8/risk 90/PHISHING, DB 조회와 제보 API 포함 |

최종 Compose 상태는 database, db-api, ml-service, sandbox, multimodal-service, backend, frontend 모두 `healthy`였다.

## 외부 DNS와 fallback

Docker 내부에서 다음 명령으로 재확인했다.

```powershell
docker compose exec -T sandbox node -e "require('dns').lookup('example.com', ...)"
```

- 결과: `ENOTFOUND: getaddrinfo ENOTFOUND example.com`, exit code 2
- Sandbox `POST /analyze` 결과: HTTP 400, `DNS_RESOLUTION_FAILED`
- 내부 주소 `http://127.0.0.1:3001` 결과: HTTP 400, `PRIVATE_ADDRESS_BLOCKED`
- 임의 DNS 서버 하드코딩, 내부 주소 차단 해제, SSRF 완화는 하지 않았다.

이는 Sandbox 애플리케이션의 검증 실패가 아니라 Docker/호스트 외부 DNS 환경 제한이다. Sandbox는 DNS 실패를 명시적인 안전 오류로 반환한다.

fallback 검증에서는 안전한 `https://example.com/dns-second-pass-safe`를 backend에 제출했다. backend 분석 ID 9는 ML 위험도 90/`PHISHING`과 XAI를 반환했고, `multimodalResult`에는 `collected:false` 및 Sandbox HTTP 400 note가 저장됐다. db-api에서 동일 ID와 URL을 조회해 `dbStored:true`를 확인했다. 따라서 외부 DNS 실패 중에도 ML fallback, XAI, backend 응답, DB 저장은 유지된다. 이 URL의 높은 점수는 ML이 긴 경로/하이픈 특성을 평가한 결과이며 실제 피싱 접속을 의미하지 않는다.

## 실제 브라우저 UI E2E

- 수행 여부: 자동화 미수행
- 원인: 브라우저 제어 런타임의 사용 가능 목록이 빈 배열이어서 설치된 Chrome/Edge에 안전하게 연결할 수 없었다.
- 별도 브라우저, 확장 프로그램, Playwright를 설치하거나 다른 자동화 표면으로 우회하지 않았다.
- 자동 스크린샷 경로: 없음

수동 테스트 절차:

1. Chrome 또는 Edge에서 `http://localhost:3000`을 연다.
2. 입력 화면 제목 `의심스러운 URL을 검사해보세요`와 `검사하기` 버튼을 확인한다.
3. 실제 피싱 URL 대신 `https://example.com`을 입력하고 `검사하기`를 한 번 클릭한다.
4. 요청 중 버튼이 비활성화되고 문구가 `분석 중...`으로 바뀌는지 확인한다.
5. 완료 후 `/result/<id>`로 이동하는지 확인한다. 이번 smoke 기준 정상 URL의 참고값은 risk 8, `NORMAL`이지만 재학습 artifact가 달라지면 점수는 달라질 수 있다.
6. 결과 화면에서 URL, `NORMAL`/`PHISHING` badge, `위험도 <score> / 100`, `판단 근거 (XAI)` 목록을 확인한다. XAI 객체는 설명, 위험 방향 화살표, contribution으로 표시돼야 한다.
7. 주소 표시줄의 `<id>`를 기록하고 `http://localhost:8081/api/analyze/<id>`를 열어 동일 ID와 URL이 DB에 저장됐는지 확인한다.
8. Docker DNS가 계속 실패하면 결과 DB의 `multimodalResult`에서 `collected:false`와 Sandbox 400 note가 보이고, 동시에 ML/XAI 및 최종 판정은 유지되는지 확인한다.
9. 실패 경로 확인이 필요하면 잘못된 형식의 안전한 입력을 사용하고, 실제 피싱/의심 URL은 입력하지 않는다. UI 요청 실패 시 `분석 요청에 실패했습니다. 백엔드 서버 상태를 확인해주세요.`가 표시되는지 확인한다.
10. 증빙 스크린샷은 Git 비추적 경로 `local-test-data/fin-der-domestic-captures-20260824/ui-e2e-second-pass/` 아래 `01-input.png`, `02-loading.png`, `03-result.png`, `04-db-record.png`로 저장한다.

## 실행한 명령

주요 명령은 다음과 같다. API 키 값이나 Gemini 원문 응답을 출력하는 명령은 실행하지 않았다.

```text
git status --short --branch
git diff --cached --stat
git diff --stat
git rev-parse HEAD
git branch --show-current
docker compose ps
docker compose up --build -d
git check-ignore -v <local result path>
git ls-files -- .env local-test-data/** ml-service/artifacts/**
docker compose run ... evaluate-domestic-captures.py ...
docker compose run ... run_fixture_tests.py normal_bank non_financial fake_bank card_capital internet_bank government_support ...
ml-service\.venv\Scripts\python.exe -m pytest
frontend: npm.cmd run build
backend: gradlew.bat test --no-daemon
docker compose run ... multimodal-service pytest -q tests
docker run ... maven:3.9-eclipse-temurin-17 mvn -q test
node --check sandbox/server.js
node --check sandbox/urlValidator.js
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
docker compose exec -T sandbox node -e <example.com DNS lookup>
Invoke-RestMethod sandbox/backend/db-api 안전 URL 및 loopback 검증
```

## 실패한 테스트와 원인

최종 제품 회귀 실패는 없다. 최초 실행 환경 문제는 다음과 같다.

1. ML pytest를 저장소 루트에서 실행해 `src` import가 실패했다. 원인은 코드가 아니라 working directory였으며 `ml-service`에서 재실행해 5 passed였다.
2. 일반 권한 frontend build가 기존 `dist` asset을 unlink하지 못해 `EPERM`이었다. 승인된 동일 workspace 권한으로 재실행해 성공했다.
3. Gradle wrapper가 기본 `C:\.gradle` lock 디렉터리를 만들지 못했다. `GRADLE_USER_HOME`을 저장소 내 ignored `backend/.gradle-user-home`으로 지정해 성공했다.
4. multimodal parser test의 pytest cache가 read-only bind mount에 기록되지 못해 경고 2개가 발생했지만 4개 테스트는 모두 통과했다.
5. 외부 DNS는 `ENOTFOUND`로 실패했다. 애플리케이션 코드 문제와 구분했으며 보안 정책을 변경하지 않았다.
6. UI 자동화는 연결 가능한 브라우저 인스턴스가 없어 미수행했다. 위 수동 절차가 남은 작업이다.

## 남은 사용자 수동 작업

1. Chrome 또는 Edge를 브라우저 제어 기능에 연결하거나 직접 열어 위 UI 절차 1~10을 수행한다.
2. 스크린샷 4개를 지정한 `local-test-data/.../ui-e2e-second-pass/` 경로에 저장한다.
3. Docker Desktop/호스트 네트워크에서 외부 DNS가 복구된 뒤 `example.com` Sandbox 수집과 전체 smoke를 다시 실행한다. SSRF 정책이나 DNS 코드는 변경하지 않는다.
4. 검토 후 필요할 때만 사용자가 직접 untracked 평가 스크립트와 보고서의 추적 여부를 결정한다. 이 작업에서는 `git add`, commit, push, PR을 수행하지 않았다.

## 최종 Git 상태

보고서 작성 직후 기록:

```text
## local/integration-validation-20260824...origin/feat/wire-orchestration-pipeline
(기존 staged 55개 파일 유지)
?? docs/domestic-acceptance-report.md
?? scripts/evaluate-domestic-captures.py
```

```text
git diff --cached --stat
55 files changed, 1191 insertions(+), 259 deletions(-)
```

```text
git diff --stat
(출력 없음: 이번 두 저장소 파일은 untracked/unstaged이므로 diff stat에 포함되지 않음)
```

commit, push, PR 생성은 하지 않았다.
