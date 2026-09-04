# Domestic Page Behavior Baseline

## 평가 목적
등록된 국내 금융·정부기관 범위에서 deterministic rule/fusion의 FP/FN 원인을 측정한다.

## Cohort 구성 및 안전성 원칙
총 80건(공식 정상 20, 브랜드 언급 정상 20, 합성 사칭 30, 수집 불완전 10)이다. 모든 URL은 공식 도메인 또는 `example.com`/`test.invalid`이고, HTML은 script/iframe/object/embed/event handler/javascript URL/base64 blob 없는 비실행 정적 문자열이다.

## 전체 및 cohort별 결과
| Cohort | Total | NORMAL | SUSPICIOUS | PHISHING | UNKNOWN | Exact accuracy | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DOMESTIC_BENIGN_OFFICIAL | 20 | 20 | 0 | 0 | 0 | 1.0000 | 0 | 0 |
| DOMESTIC_BENIGN_BRAND_MENTION | 20 | 20 | 0 | 0 | 0 | 1.0000 | 0 | 0 |
| DOMESTIC_PHISHING_IMPERSONATION | 30 | 0 | 12 | 18 | 0 | 0.6000 | 0 | 12 |
| PARTIAL_UNKNOWN | 10 | 0 | 0 | 0 | 10 | 1.0000 | 0 | 0 |

## Strict metric (PHISHING positive)
`{"tp": 18, "tn": 40, "fp": 0, "fn": 12, "accuracy": 0.8286, "precision": 1.0, "recall": 0.6}`

## Alert metric (SUSPICIOUS + PHISHING positive)
`{"tp": 30, "tn": 40, "fp": 0, "fn": 0, "accuracy": 1.0, "precision": 1.0, "recall": 1.0}`

## Before / After
| View | Before | After |
|---|---|---|
| Exact | 48/80 (0.6000) | 68/80 (0.8500) |
| Strict | TP 18, TN 40, FP 0, FN 12, recall 0.6000 | TP 18, TN 40, FP 0, FN 12, recall 0.6000 |
| Alert | TP 30, TN 20, FP 20, FN 0, recall 1.0000 | TP 30, TN 40, FP 0, FN 0, recall 1.0000 |

## FP 상세
| caseId | cohort | expected | predicted | score | candidate brand | official domain | current domain | signals | rule contribution | synergy | Gemini | final | cause |
|---|---|---|---|---:|---|---|---|---|---|---|---:|---:|---|
| None | | | | | | | | | | | | | |

## FN 상세
| caseId | cohort | expected | predicted | score | candidate brand | official domain | current domain | signals | rule contribution | synergy | Gemini | final | cause |
|---|---|---|---|---:|---|---|---|---|---|---|---:|---:|---|
| phishing-04 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | 하나은행 | kebhana.com | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-05 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | NH농협은행 | nhbank.com | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |
| phishing-09 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | 케이뱅크 | kbanknow.com | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-10 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | KB국민카드 | kbcard.com | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |
| phishing-14 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | 롯데카드 | lottecard.co.kr | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-15 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | 우리카드 | wooricard.com | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |
| phishing-19 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | 금융감독원 | fss.or.kr | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-20 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | 금융위원회 | fsc.go.kr | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |
| phishing-24 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | KB국민은행 | kbstar.com | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-25 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | 신한은행 | shinhan.com | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |
| phishing-29 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 54 | IBK기업은행 | ibk.co.kr | test.invalid | PASSWORD_FIELD, BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"PASSWORD_FIELD": 8, "BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {"MISMATCH_AUTH": 15} | 0 | 54 | SOCIAL_ENGINEERING_NOT_DETECTED |
| phishing-30 | DOMESTIC_PHISHING_IMPERSONATION | PHISHING | SUSPICIOUS | 31 | 카카오뱅크 | kakaobank.com | test.invalid | BRAND_IMPERSONATION, BRAND_DOMAIN_MISMATCH | {"BRAND_IMPERSONATION": 1, "BRAND_DOMAIN_MISMATCH": 30} | {} | 0 | 31 | SENSITIVE_FIELD_NOT_DETECTED |

## FP Top 원인
- 없음

## FN Top 원인
1. `SOCIAL_ENGINEERING_NOT_DETECTED`: 6건
2. `SENSITIVE_FIELD_NOT_DETECTED`: 6건

## 개선 후보
| 원인 | 영향 파일 | 가장 작은 수정 후보 | 예상 효과 | 회귀 위험 | 추가 테스트 |
|---|---|---|---|---|---|
| BRAND_MENTION_FALSE_IMPERSONATION | `brand_reference.py`, `dom_risk_analyzer.py` | 브랜드 후보와 사칭 증거를 분리하고 비공식 도메인만으로 mismatch 위험을 확정하지 않기 | 독립 안내·뉴스 FP 감소 | 텍스트만 있는 사칭 recall 감소 | 필요 |
| SENSITIVE_FIELD_NOT_DETECTED | `dom_risk_analyzer.py` | input label/name 동의어 coverage 보강 | credential 기반 FN 감소 | 일반 폼 오탐 증가 | 필요 |
| SOCIAL_ENGINEERING_NOT_DETECTED | `dom_risk_analyzer.py` | 국내 사기 문구 신호 coverage를 별도 검증 후 보강 | 약한 사칭 FN 감소 | 안내문 FP 증가 | 필요 |
| WEAK_BRAND_EVIDENCE | `dom_risk_analyzer.py`, `risk_fusion.py` | 브랜드 근거 강도를 별도 feature로 모델링 | 단순 언급과 사칭 분리 | 점수 정책 회귀 가능 | 필요 |

## 확인
이번 단계에서는 production scoring weight, threshold, `risk_fusion.py`, 브랜드 데이터, Gemini prompt를 수정하지 않았다. 합성 baseline의 결과이며 실제 운영 성능 추정치는 아니다.
