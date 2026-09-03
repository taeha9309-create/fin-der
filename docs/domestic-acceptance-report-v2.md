# fin-der 국내 정상 화면 2차 평가 보고서

- 수행일: 2026-08-24 (Asia/Seoul)
- 프로젝트: `C:\codex-work\fin-der-0824`
- 시작 브랜치: `local/integration-validation-20260824`
- 시작 HEAD: `8812e66fe53bdc38fa17de7c90fe2f4b45124c6a`
- 실제 이미지 폴더: `C:\codex-work\fin-der-0824\local-test-data\fin-der-domestic-captures-20260824\screenshots`
- Gemini 모델: `gemini-3.1-flash-lite-preview`
- prompt version: `mm_prompt_v1`

## 요약

- 실제 이미지: 37개
- `manifest-combined.csv`: 37행, filename 중복 0, 이미지/manifest 누락 0
- 신규 21장: completed 21, 실패 0, 오탐 0, 기대 판정 PASS 21
- 통합 37장: completed 37, 실패 0, 오탐 0, 오탐률 0.00%, 기대 판정 PASS 37
- 기존 fixture: 6/6 PASS
- parser: 4/4 PASS
- smoke: PASS
- Compose: 7/7 healthy
- DNS: Windows 호스트와 7개 컨테이너가 모두 실패. Sandbox 단독 또는 애플리케이션 코드 문제가 아니라 호스트/Docker Desktop 상위 DNS 환경 문제로 분류했다.

## 시작 상태와 index 보존

작업 시작 시 branch/HEAD는 위와 같았으며 기존 index는 다음 통계를 유지하고 있었다.

```text
git diff --cached --stat
55 files changed, 1191 insertions(+), 259 deletions(-)

git diff --stat
(출력 없음)
```

기존 staged 55개 파일은 변경하지 않았다. 이번 작업에서는 `git add`, commit, push, PR, merge, reset, restore, checkout, clean을 실행하지 않았다. 평가 이미지, combined manifest, 결과 JSON/CSV, Gemini 원문 응답은 기존 `.git/info/exclude`의 `local-test-data/` 규칙 아래에만 저장했다. `.env`와 API 키 값은 읽거나 출력하거나 Git에 추가하지 않았다.

## 이미지 및 manifest 검증

지정된 screenshots 폴더만 입력 경로로 사용했다. 별도 수동 캡처 폴더는 찾지 않았다.

| 검사 | 결과 |
| --- | --- |
| JPG/PNG 수 | 37 |
| 기존 manifest 행 | 16 |
| 폴더에만 있던 신규 이미지 | 21 |
| manifest에만 있는 파일 | 0 |
| 중복 filename(대소문자 무시) | 0 |
| 0바이트 파일 | 0 |
| 읽을 수 없는 이미지 | 0 |
| 1348×926이 아닌 전체 이미지 | 0 |
| 1348×926이 아닌 신규 이미지 | 0 |

기존 `manifest.csv`는 수정하지 않았다. 새 파일 `local-test-data/fin-der-domestic-captures-20260824/manifest-combined.csv`를 만들었다. 기존 16행의 값을 재사용했고 신규 21행에는 요청된 기관명·category 및 공통 필드 `captured_at=2026-08-24`, `width=1348`, `height=926`, `expected_impersonation=false`, `expected_risk=low_risk`, `capture_type=official_normal_homepage`를 넣었다. 신규 대응표에 source URL이 없었으므로 이를 임의로 만들지 않고 신규 21행의 `source_url`은 비워 두었다.

combined manifest 재검증 결과:

- 데이터 행 37
- 고유 filename 37
- 모든 filename이 screenshots에 존재
- screenshots의 모든 이미지가 manifest에 존재
- 빈 기관명 0
- `expected_impersonation=false` 37/37

## 기존 16장 결과 재사용 검증

기존 결과는 `evaluation-results-second-pass/domestic-results.json`, CSV, summary 및 원문 응답 16개가 실제로 존재했다. 결과 filename 16개가 기존 manifest와 정확히 일치했고 상태는 모두 completed, 오류는 0이었다. 결과의 모델과 prompt version이 현재 컨테이너 설정과 일치했다. 원문 응답 16개를 현재 `response_parser`와 Pydantic schema로 다시 파싱하고 저장된 핵심 판정과 일치함을 검증했다. 따라서 임의 작성 결과가 아닌 실제 응답으로 재현 가능하다고 판단해 기존 16장은 재호출하지 않았다.

| 기관 | category | status | impersonation | score | risk | 결과 |
| --- | --- | --- | --- | ---: | --- | --- |
| KB국민은행 | bank | completed | false | 0 | low | PASS |
| 우리은행 | bank | completed | false | 0 | low | PASS |
| 하나은행 | bank | completed | false | 0 | low | PASS |
| NH농협은행 | bank | completed | false | 5 | low | PASS |
| IBK기업은행 | bank | completed | false | 0 | low | PASS |
| 카카오뱅크 | internet_bank | completed | false | 0 | low | PASS |
| 케이뱅크 | internet_bank | completed | false | 0 | low | PASS |
| 토스뱅크 | internet_bank | completed | false | 0 | low | PASS |
| 한국씨티은행 | bank | completed | false | 0 | low | PASS |
| 금융위원회 | government_finance | completed | false | 0 | low | PASS |
| 금융감독원 | government_finance | completed | false | 0 | low | PASS |
| 한국인터넷진흥원 | public_security | completed | false | 0 | low | PASS |
| 국민연금공단 | public_welfare | completed | false | 0 | low | PASS |
| 국세청 | government_tax | completed | false | 0 | low | PASS |
| 대한민국 정책브리핑 | government | completed | false | 5 | low | PASS |
| 한국은행 | central_bank | completed | false | 0 | low | PASS |

## 신규 21장 실제 Gemini 결과

`scripts/evaluate-domestic-captures.py`에 기존 CLI를 유지하면서 `--only-new-against`, 출력 파일명 지정, bounded retry, category/latency/attempts/verdict/false-positive 기록 및 결과 병합 기능을 추가했다. 실행 시 `--max-retries 0`을 사용했다. 총 API attempts는 21이며 각 이미지가 정확히 1회 호출됐다. API 오류와 재시도는 0건이고 총 측정 latency는 96.921초였다.

| 기관 | category | status | impersonation | 감지 brand | brand category | attack | score | risk | conf. | latency(s) | 근거 code | 결과/오탐 |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |
| 신한은행 | bank | completed | false | shinhan_bank | bank | unknown | 0 | low | 1.00 | 3.709 | LEGITIMATE_CONTENT_IDENTIFIED | PASS/no |
| 한국산업은행 | bank | completed | false | 한국산업은행 | bank | unknown | 0 | low | 1.00 | 9.331 | OFFICIAL_BANK_WEBSITE | PASS/no |
| Sh수협은행 | bank | completed | false | Sh수협은행 | bank | unknown | 0 | low | 1.00 | 3.528 | LEGITIMATE_FINANCIAL_INSTITUTION_WEBSITE | PASS/no |
| SC제일은행 | bank | completed | false | SC제일은행 | bank | unknown | 0 | low | 1.00 | 6.650 | LEGITIMATE_CONTENT_IDENTIFIED | PASS/no |
| iM뱅크 | bank | completed | false | iM뱅크 | bank | unknown | 0 | low | 1.00 | 7.768 | LEGITIMATE_SITE_STRUCTURE; VERIFIED_CONTENT | PASS/no |
| BNK부산은행 | bank | completed | false | BNK부산은행 | bank | unknown | 0 | low | 1.00 | 7.573 | LEGITIMATE_SITE_IDENTIFIED | PASS/no |
| BNK경남은행 | bank | completed | false | BNK경남은행 | bank | unknown | 0 | low | 1.00 | 4.217 | NORMAL_BANK_HOMEPAGE | PASS/no |
| 광주은행 | bank | completed | false | 광주은행 | bank | unknown | 0 | low | 1.00 | 6.148 | LEGITIMATE_BANK_HOMEPAGE | PASS/no |
| 전북은행 | bank | completed | false | 전북은행 | bank | unknown | 5 | low | 0.98 | 3.369 | NORMAL_FINANCIAL_HOMEPAGE | PASS/no |
| 제주은행 | bank | completed | false | 제주은행 | bank | unknown | 0 | low | 1.00 | 4.516 | LEGITIMATE_PAGE_STRUCTURE | PASS/no |
| 정부24 | government | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 2.965 | OFFICIAL_GOVERNMENT_WEBSITE | PASS/no |
| 국세청 홈택스 | government_tax | completed | false | 국세청 홈택스 | government | unknown | 0 | low | 1.00 | 4.357 | LEGITIMATE_GOVERNMENT_WEBSITE | PASS/no |
| 복지로 | public_welfare | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 4.386 | OFFICIAL_GOVERNMENT_WEBSITE | PASS/no |
| 국민건강보험공단 | public_welfare | completed | false | 국민건강보험공단 | government | unknown | 0 | low | 1.00 | 2.591 | LEGITIMATE_GOVERNMENT_PAGE | PASS/no |
| 고용24 | government_employment | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 2.502 | OFFICIAL_GOVERNMENT_WEBSITE | PASS/no |
| 행정안전부 | government | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 4.473 | OFFICIAL_GOVERNMENT_PAGE | PASS/no |
| 경찰청 | government | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 2.947 | LEGITIMATE_GOVERNMENT_PAGE | PASS/no |
| 예금보험공사 | government_finance | completed | false | 빈 값 | government | unknown | 0 | low | 1.00 | 5.041 | OFFICIAL_GOVERNMENT_PAGE | PASS/no |
| 서민금융진흥원 | government_finance | completed | false | 서민금융진흥원 | government | unknown | 5 | low | 1.00 | 4.552 | OFFICIAL_PUBLIC_INSTITUTION_WEBSITE | PASS/no |
| 금융결제원 | financial_infrastructure | completed | false | 금융결제원 | government | unknown | 0 | low | 1.00 | 3.271 | LEGITIMATE_GOVERNMENT_INSTITUTION_WEBSITE | PASS/no |
| 한국자산관리공사 | government_finance | completed | false | 한국자산관리공사 | government | unknown | 0 | low | 1.00 | 3.027 | LEGITIMATE_GOVERNMENT_WEBSITE | PASS/no |

결과 파일:

- `local-test-data/fin-der-domestic-captures-20260824/results/new-21-results.json`
- `local-test-data/fin-der-domestic-captures-20260824/results/new-21-summary.csv`
- 원문 21개: `local-test-data/fin-der-domestic-captures-20260824/results/raw-responses/`

## 통합 37장 기관별 결과

| 기관 | category | status | impersonation | score | risk | 결과/오탐 |
| --- | --- | --- | --- | ---: | --- | --- |
| KB국민은행 | bank | completed | false | 0 | low | PASS/no |
| 우리은행 | bank | completed | false | 0 | low | PASS/no |
| 하나은행 | bank | completed | false | 0 | low | PASS/no |
| NH농협은행 | bank | completed | false | 5 | low | PASS/no |
| IBK기업은행 | bank | completed | false | 0 | low | PASS/no |
| 카카오뱅크 | internet_bank | completed | false | 0 | low | PASS/no |
| 케이뱅크 | internet_bank | completed | false | 0 | low | PASS/no |
| 토스뱅크 | internet_bank | completed | false | 0 | low | PASS/no |
| 한국씨티은행 | bank | completed | false | 0 | low | PASS/no |
| 금융위원회 | government_finance | completed | false | 0 | low | PASS/no |
| 금융감독원 | government_finance | completed | false | 0 | low | PASS/no |
| 한국인터넷진흥원 | public_security | completed | false | 0 | low | PASS/no |
| 국민연금공단 | public_welfare | completed | false | 0 | low | PASS/no |
| 국세청 | government_tax | completed | false | 0 | low | PASS/no |
| 대한민국 정책브리핑 | government | completed | false | 5 | low | PASS/no |
| 한국은행 | central_bank | completed | false | 0 | low | PASS/no |
| 신한은행 | bank | completed | false | 0 | low | PASS/no |
| 한국산업은행 | bank | completed | false | 0 | low | PASS/no |
| Sh수협은행 | bank | completed | false | 0 | low | PASS/no |
| SC제일은행 | bank | completed | false | 0 | low | PASS/no |
| iM뱅크 | bank | completed | false | 0 | low | PASS/no |
| BNK부산은행 | bank | completed | false | 0 | low | PASS/no |
| BNK경남은행 | bank | completed | false | 0 | low | PASS/no |
| 광주은행 | bank | completed | false | 0 | low | PASS/no |
| 전북은행 | bank | completed | false | 5 | low | PASS/no |
| 제주은행 | bank | completed | false | 0 | low | PASS/no |
| 정부24 | government | completed | false | 0 | low | PASS/no |
| 국세청 홈택스 | government_tax | completed | false | 0 | low | PASS/no |
| 복지로 | public_welfare | completed | false | 0 | low | PASS/no |
| 국민건강보험공단 | public_welfare | completed | false | 0 | low | PASS/no |
| 고용24 | government_employment | completed | false | 0 | low | PASS/no |
| 행정안전부 | government | completed | false | 0 | low | PASS/no |
| 경찰청 | government | completed | false | 0 | low | PASS/no |
| 예금보험공사 | government_finance | completed | false | 0 | low | PASS/no |
| 서민금융진흥원 | government_finance | completed | false | 5 | low | PASS/no |
| 금융결제원 | financial_infrastructure | completed | false | 0 | low | PASS/no |
| 한국자산관리공사 | government_finance | completed | false | 0 | low | PASS/no |

통합 파일:

- `local-test-data/fin-der-domestic-captures-20260824/results/combined-37-results.json`
- `local-test-data/fin-der-domestic-captures-20260824/results/combined-37-summary.csv`

카테고리별 completed/실패/오탐:

| category | total | completed | failed | false positives |
| --- | ---: | ---: | ---: | ---: |
| bank | 16 | 16 | 0 | 0 |
| internet_bank | 3 | 3 | 0 | 0 |
| central_bank | 1 | 1 | 0 | 0 |
| government | 4 | 4 | 0 | 0 |
| government_finance | 5 | 5 | 0 | 0 |
| government_tax | 2 | 2 | 0 | 0 |
| government_employment | 1 | 1 | 0 | 0 |
| public_welfare | 3 | 3 | 0 | 0 |
| public_security | 1 | 1 | 0 | 0 |
| financial_infrastructure | 1 | 1 | 0 | 0 |

직접 `bank` category는 16/16이며 internet/central bank까지 포함한 은행 계열은 20/20이다. government 접두 category는 12/12이고, public 및 financial infrastructure까지 포함한 공공 관련 그룹은 17/17이다. 기관별로는 37개 기관이 각각 1개 completed/PASS, 0개 오탐이다.

## 오탐 분석 및 코드 수정 판단

오탐이 0건이므로 정상 보안 경고, 로그인 버튼, 기관 로고, 금융상품 광고, 정부지원·세금·환급 문구에 따른 실패 사례가 없다. 이미지 전처리, prompt_builder, Gemini 응답, response_parser, schema 매핑에서도 오류가 없었다. 따라서 프롬프트·파서·전처리·프로덕션 API를 수정하지 않았다. 변경은 평가 스크립트의 실행/기록 기능에만 한정했다.

## fixture 6개 회귀

실제 피싱 URL에는 접속하지 않고 기존 로컬 fixture와 `.example` URL만 사용했다.

| fixture | impersonation | score | risk | brand | attack | 결과 |
| --- | --- | ---: | --- | --- | --- | --- |
| normal_bank | false | 0 | low | KB국민은행 | unknown | PASS |
| non_financial | false | 10 | low | 빈 값 | unknown | PASS |
| fake_bank | true | 90 | high_risk_suspected | KB국민은행 | credential_theft | PASS |
| card_capital | true | 95 | high_risk_suspected | KB캐피탈 | loan_scam | PASS |
| internet_bank | true | 95 | high_risk_suspected | kakaobank | credential_theft | PASS |
| government_support | true | 95 | high_risk_suspected | 정부24 | government_support_scam | PASS |

정상 금융/비금융 오탐 없음, 금융 사칭 3종과 정부지원 사칭 1종 탐지, parser 오류 없음이다. 결과는 Git 비추적 `results/fixture-v2/`에 저장했다.

## DNS 진단과 fallback

| 위치 | `example.com` DNS |
| --- | --- |
| Windows 호스트 | FAIL, `No such host is known` |
| database | FAIL, exit 2 |
| db-api | FAIL, exit 2 |
| ml-service | FAIL, temporary failure |
| sandbox | FAIL, `ENOTFOUND` |
| multimodal-service | FAIL, temporary failure |
| backend | FAIL, exit 2 |
| frontend | FAIL, exit 2 |

Compose network `fin-der_default`은 bridge, subnet `172.18.0.0/16`, gateway `172.18.0.1`, 연결 컨테이너 7개로 정상이다. 7개 컨테이너의 `/etc/resolv.conf`는 모두 Docker 내장 resolver `127.0.0.11`, `ndots:0`, host upstream `192.168.65.7`로 동일했다. 호스트부터 실패하고 모든 컨테이너가 동일하게 실패하므로 Sandbox 코드·SSRF 방어·개별 컨테이너 문제가 아니라 Windows/네트워크 또는 Docker Desktop 상위 DNS 환경 문제다.

Sandbox 보안 정책과 내부 주소 차단을 변경하지 않았고 공용 DNS를 코드에 하드코딩하지 않았다. smoke는 DNS 실패를 fallback으로 처리해 정상 URL id 10/risk 8/NORMAL, 안전한 합성 의심 URL id 11/risk 90/PHISHING을 저장했다. 추가 fallback id 12는 risk 91/PHISHING, ML 및 XAI 존재, `sandboxCollected=false`, Sandbox 400 note, DB 저장 true였다.

사용자가 직접 수행할 DNS 복구 확인 절차:

```powershell
Resolve-DnsName example.com
Get-DnsClientServerAddress
ipconfig /flushdns
Resolve-DnsName example.com
```

두 번째 조회도 실패하면 VPN/보안 에이전트/프록시/사내 DNS 상태를 확인하거나 네트워크 관리자에게 문의한다. Windows DNS 서버를 임의 공용 DNS로 바꾸지 않는다. 호스트 조회가 성공한 뒤 Docker Desktop의 **Troubleshoot → Restart Docker Desktop**을 사용자가 직접 실행하고 다음을 재검증한다.

```powershell
docker compose ps
docker compose exec -T sandbox node -e "require('dns').lookup('example.com',(e,a)=>{if(e)throw e;console.log(a)})"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

## 회귀 테스트

| 검사 | 결과 |
| --- | --- |
| multimodal parser | PASS, 4 passed |
| 실제 Gemini fixture | PASS, 6/6 |
| `scripts/smoke-test.ps1` | PASS |
| frontend HTTP/분석/DB 조회/제보 | smoke에서 PASS |
| Sandbox 내부 주소 차단 | smoke에서 PASS |
| Docker Compose | 7/7 healthy |
| DNS fallback/ML/XAI/DB | PASS |

평가 스크립트만 변경됐으므로 다른 서비스 소스 테스트나 Docker 재빌드는 필요하지 않았다. 스크립트의 신규 평가/병합 경로는 실제 21장 호출과 37장 통합 생성으로 검증했다.

## UI E2E 수동 절차

이전 확인에서 브라우저 제어 런타임에 연결 가능한 Chrome/Edge/in-app 브라우저가 0개였고, 이번 요청에 따라 자동화를 재시도하거나 새 프로그램을 설치하지 않았다.

1. Chrome 또는 Edge에서 `http://localhost:3000`을 연다.
2. `의심스러운 URL을 검사해보세요`, URL 입력칸, `검사하기` 버튼을 확인한다.
3. `https://example.com`을 입력하고 검사한다. 버튼이 비활성화되고 `분석 중...`이 보이는지 확인한다.
4. `/result/<id>` 이동 후 URL, NORMAL badge, 위험도, XAI 근거가 표시되는지 확인한다. 현재 smoke 참고값은 risk 8/NORMAL이다.
5. `http://localhost:8081/api/analyze/<id>`에서 동일 ID/URL의 DB 저장을 확인한다.
6. 초기 화면으로 돌아가 실제 피싱 URL 대신 `https://example.com/secure-bank-login?verify=account`를 입력한다.
7. 현재 DNS 장애 상태에서는 ML 기반 PHISHING/위험도/XAI가 표시되고 DB의 `multimodalResult`에는 `collected:false`와 Sandbox 400 fallback note가 있는지 확인한다.
8. 경고 modal이 나타나면 위험도와 차단 안내를 확인하되 실제 외부 위험 사이트로 진행하지 않는다.

Git 비추적 스크린샷 저장 경로:

- `local-test-data/fin-der-domestic-captures-20260824/ui-e2e-v2/01-input.png`
- `local-test-data/fin-der-domestic-captures-20260824/ui-e2e-v2/02-loading.png`
- `local-test-data/fin-der-domestic-captures-20260824/ui-e2e-v2/03-normal-result.png`
- `local-test-data/fin-der-domestic-captures-20260824/ui-e2e-v2/04-risk-or-fallback-result.png`

## 이번 작업에서 수정·생성한 파일

| 경로 | Git 상태 | 내용 |
| --- | --- | --- |
| `scripts/evaluate-domestic-captures.py` | untracked/unstaged | 신규 필터, 기록 필드, bounded retry, 결과 병합 |
| `docs/domestic-acceptance-report-v2.md` | untracked/unstaged | 이 보고서 |
| `local-test-data/.../manifest-combined.csv` | ignored | 37장 combined manifest |
| `local-test-data/.../results/new-21-results.json` | ignored | 신규 21장 상세 결과 |
| `local-test-data/.../results/new-21-summary.csv` | ignored | 신규 21장 CSV |
| `local-test-data/.../results/combined-37-results.json` | ignored | 통합 37장 상세 결과 |
| `local-test-data/.../results/combined-37-summary.csv` | ignored | 통합 37장 CSV |
| `local-test-data/.../results/raw-responses/` | ignored | 신규 원문 응답 21개 |
| `local-test-data/.../results/fixture-v2/` | ignored | fixture 결과 6개 |

## 실행한 주요 명령

```text
git status --short --branch
git diff --cached --stat
git diff --stat
docker compose ps
PowerShell manifest/image count, duplicate, zero-byte, System.Drawing readability/dimension checks
docker compose exec multimodal-service <current model/prompt/key-present check>
docker compose run multimodal-service <old raw response current-parser validation>
docker compose run multimodal-service evaluate-domestic-captures.py --only-new-against ... --max-retries 0
docker compose run multimodal-service evaluate-domestic-captures.py --merge-results ...
docker compose run multimodal-service pytest -q -p no:cacheprovider tests
docker compose run multimodal-service run_fixture_tests.py <6 fixtures>
[System.Net.Dns]::GetHostAddresses('example.com')
docker network inspect fin-der_default
docker compose exec <7 services> cat /etc/resolv.conf
docker compose exec <7 services> <example.com DNS lookup>
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
Invoke-RestMethod backend/db-api fallback 저장 확인
```

## 최종 Git 상태

최종 확인 기준 기존 staged index 통계는 시작과 동일하다.

```text
## local/integration-validation-20260824...origin/feat/wire-orchestration-pipeline
(기존 staged 55개 파일 그대로 유지)
?? docs/domestic-acceptance-report.md
?? docs/domestic-acceptance-report-v2.md
?? scripts/evaluate-domestic-captures.py
```

```text
git diff --cached --stat
55 files changed, 1191 insertions(+), 259 deletions(-)
```

```text
git diff --stat
(출력 없음: 이번 저장소 파일은 untracked/unstaged이며 local-test-data는 ignored)
```

commit, push, PR, `git add`는 수행하지 않았다.
