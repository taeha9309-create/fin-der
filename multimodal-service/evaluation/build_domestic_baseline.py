"""Build and evaluate the safe, synthetic domestic baseline without network access."""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE / "app"))
sys.path.insert(0, str(SERVICE / "evaluation"))
from brand_reference import load_brand_reference
from dom_risk_analyzer import analyze_dom_risk
from risk_fusion import SIGNAL_WEIGHTS, SYNERGY_WEIGHTS, fuse_analysis
from run_evaluation import _pipeline_input

MANIFEST = SERVICE / "evaluation/datasets/domestic_baseline_manifest.jsonl"
RESULTS = SERVICE / "evaluation/results/domestic-baseline-rule-only-after-mention-fix"
REPORT = SERVICE / "evaluation/domestic_baseline_report.md"
VERDICTS = ("NORMAL", "SUSPICIOUS", "PHISHING", "UNKNOWN")

def row(case_id, cohort, expected, brand, requested, final, note, **input_fields):
    page = input_fields.pop("page", {"title": "", "visibleText": "", "html": ""})
    payload = {"analysisId": case_id, "requestedUrl": requested, "finalUrl": final,
               "statusCode": input_fields.pop("statusCode", 200), "page": page,
               "inputs": input_fields.pop("inputs", []), "forms": input_fields.pop("forms", []),
               "links": input_fields.pop("links", []), "network": input_fields.pop("network", {"downloadDetected": False}),
               "redirectChain": input_fields.pop("redirectChain", []),
               "screenshot": {"available": False, "url": None}, "error": input_fields.pop("error", None)}
    return {"caseId": case_id, "sampleId": case_id, "cohort": cohort, "expectedLabel": expected,
            "requestedUrl": requested, "finalUrl": final, "sourceType": "SAFE_SYNTHETIC_INERT",
            "brand": brand, "note": note, "source": "domestic_synthetic", "split": "test",
            "label": "BENIGN" if expected == "NORMAL" else expected, "input": payload}

def build_rows():
    brands = list(load_brand_reference())
    rows = []
    for i, b in enumerate(brands[:20]):
        alias, domain = b["aliases"][0], b["officialDomains"][0]
        inputs = [{"type": "password", "name": "password"}] if i % 2 == 0 else [{"name": "otp", "label": "OTP"}]
        forms = [{"method": "POST", "action": f"https://login.{domain}/session", "inputs": []}]
        rows.append(row(f"official-{i+1:02d}", "DOMESTIC_BENIGN_OFFICIAL", "NORMAL", b["brand"],
                        f"https://www.{domain}/", f"https://login.{domain}/", "Official domain authentication page",
                        page={"title": alias, "visibleText": f"{alias} login authentication", "html": "<main>Official service login</main>"},
                        inputs=inputs, forms=forms, network={"requestDomains": [domain], "downloadDetected": False}))
    for i, b in enumerate(brands[:20]):
        alias = b["aliases"][0]
        host = f"guide-{i+1}.example.com"
        rows.append(row(f"mention-{i+1:02d}", "DOMESTIC_BENIGN_BRAND_MENTION", "NORMAL", b["brand"],
                        f"https://{host}/article", f"https://{host}/article", "Independent informational brand mention",
                        page={"title": "Financial service guide", "visibleText": f"{alias} product and service information comparison article", "html": "<article>Independent informational comparison</article>"}))
    for i in range(30):
        b, variant = brands[i % len(brands)], i % 5
        alias = b["aliases"][0]
        host = f"synthetic-{i+1}.test.invalid"
        inputs, forms, links, text = [], [], [], f"{alias} security verification"
        if variant == 0:
            inputs = [{"type": "password"}, {"name": "otp", "label": "OTP"}]
            text += " immediate account suspension"
        elif variant == 1:
            inputs = [{"name": "account_number", "label": "account number"}]
            forms = [{"method": "POST", "action": "https://collector.test.invalid/submit", "inputs": []}]
        elif variant == 2:
            inputs = [{"name": "resident_number", "label": "resident number"}, {"type": "password"}]
        elif variant == 3:
            inputs = [{"type": "password"}]
            links = [{"text": "kakao external consultation", "href": "https://consultation.test.invalid/synthetic"}]
        else:
            text += " verification required"
        rows.append(row(f"phishing-{i+1:02d}", "DOMESTIC_PHISHING_IMPERSONATION", "PHISHING", b["brand"],
                        f"https://{host}/", f"https://{host}/verify", "Synthetic impersonation feature fixture",
                        page={"title": alias, "visibleText": text, "html": "<main>Static synthetic verification notice</main>"},
                        inputs=inputs, forms=forms, links=links))
    for i in range(10):
        rows.append(row(f"unknown-{i+1:02d}", "PARTIAL_UNKNOWN", "UNKNOWN", None,
                        "https://collection-failed.example.com/", None, "Collection failed with no analyzable page facts",
                        statusCode=None, error="TIMEOUT" if i % 2 == 0 else "REDIRECT_FAILED"))
    return rows

def contributions(signals):
    signal_set = set(signals)
    rule = {s: SIGNAL_WEIGHTS.get(s, 0) for s in signals}
    synergy = {}
    if "BRAND_DOMAIN_MISMATCH" in signal_set and signal_set & {"PASSWORD_FIELD", "OTP_FIELD"}: synergy["MISMATCH_AUTH"] = SYNERGY_WEIGHTS["MISMATCH_AUTH"]
    if "BRAND_DOMAIN_MISMATCH" in signal_set and signal_set & {"RESIDENT_NUMBER_FIELD", "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD"}: synergy["MISMATCH_SENSITIVE"] = SYNERGY_WEIGHTS["MISMATCH_SENSITIVE"]
    if {"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE"} <= signal_set: synergy["URGENCY_SUSPENSION"] = SYNERGY_WEIGHTS["URGENCY_SUSPENSION"]
    if {"BRAND_DOMAIN_MISMATCH", "EXTERNAL_CONTACT"} <= signal_set: synergy["MISMATCH_CONTACT"] = SYNERGY_WEIGHTS["MISMATCH_CONTACT"]
    if {"BENEFIT_LURE", "FINANCIAL_ACTION_REQUEST"} <= signal_set: synergy["BENEFIT_FINANCIAL"] = SYNERGY_WEIGHTS["BENEFIT_FINANCIAL"]
    if "EXTERNAL_FORM_ACTION" in signal_set and signal_set & {k for k in SIGNAL_WEIGHTS if k.endswith("_FIELD")}: synergy["EXTERNAL_FORM_CREDENTIAL"] = SYNERGY_WEIGHTS["EXTERNAL_FORM_CREDENTIAL"]
    if {"DOWNLOAD_REQUEST", "BRAND_IMPERSONATION"} <= signal_set: synergy["DOWNLOAD_INSTITUTION"] = SYNERGY_WEIGHTS["DOWNLOAD_INSTITUTION"]
    return rule, synergy

def cause(item):
    signals = set(item["detectedSignals"])
    if item["expected"] == "NORMAL":
        if "BRAND_DOMAIN_MISMATCH" in signals: return "BRAND_MENTION_FALSE_IMPERSONATION"
        if signals & {"PASSWORD_FIELD", "OTP_FIELD", "POST_FORM"}: return "LOGIN_FORM_OVERWEIGHT"
        return "EXPECTED_LABEL_REVIEW_NEEDED"
    if item["expected"] == "PHISHING":
        if "BRAND_IMPERSONATION" not in signals: return "BRAND_NOT_DETECTED"
        if not signals & {"PASSWORD_FIELD", "OTP_FIELD", "RESIDENT_NUMBER_FIELD", "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD"}: return "SENSITIVE_FIELD_NOT_DETECTED"
        if not signals & {"URGENCY_MESSAGE", "ACCOUNT_SUSPENSION_MESSAGE", "BENEFIT_LURE", "EXTERNAL_CONTACT", "EXTERNAL_FORM_ACTION"}: return "SOCIAL_ENGINEERING_NOT_DETECTED"
        return "WEAK_BRAND_EVIDENCE"
    return "COLLECTION_INCOMPLETE"

def evaluate(rows):
    results = []
    for sample in rows:
        data, status = _pipeline_input(sample["input"])
        rule = analyze_dom_risk(data)
        fused = fuse_analysis(rule, None, status)
        rc, sc = contributions(fused["detectedSignals"])
        item = {"caseId": sample["caseId"], "cohort": sample["cohort"], "expected": sample["expectedLabel"],
                "predicted": fused["verdict"], "pageRiskScore": fused["pageRiskScore"],
                "candidateBrand": rule["impersonation"].get("brand"),
                "officialDomains": rule["domainAnalysis"].get("officialDomains"),
                "currentDomain": rule["domainAnalysis"].get("currentDomain"),
                "detectedSignals": fused["detectedSignals"], "ruleScoreContribution": rc,
                "synergyContribution": sc, "geminiAdjustment": 0, "finalScore": fused["pageRiskScore"]}
        item["errorCause"] = cause(item) if item["expected"] != item["predicted"] else None
        results.append(item)
    return results

def metric(results, alert):
    rows = [r for r in results if r["expected"] in {"NORMAL", "PHISHING"}]
    tp=tn=fp=fn=0
    for r in rows:
        actual = r["expected"] == "PHISHING"
        predicted = r["predicted"] in ({"SUSPICIOUS", "PHISHING"} if alert else {"PHISHING"})
        if actual and predicted: tp += 1
        elif not actual and not predicted: tn += 1
        elif predicted: fp += 1
        else: fn += 1
    return {"tp":tp,"tn":tn,"fp":fp,"fn":fn,"accuracy":round((tp+tn)/len(rows),4),
            "precision":round(tp/(tp+fp),4) if tp+fp else 0,"recall":round(tp/(tp+fn),4) if tp+fn else 0}

def render(results):
    cohorts = defaultdict(list)
    for r in results: cohorts[r["cohort"]].append(r)
    strict, alert = metric(results, False), metric(results, True)
    errors = [r for r in results if r["expected"] != r["predicted"]]
    fp = [r for r in errors if r["expected"] == "NORMAL"]
    fn = [r for r in errors if r["expected"] == "PHISHING"]
    table = lambda xs: "\n".join(f"| {r['caseId']} | {r['cohort']} | {r['expected']} | {r['predicted']} | {r['pageRiskScore']} | {r['candidateBrand']} | {', '.join(r['officialDomains'] or [])} | {r['currentDomain']} | {', '.join(r['detectedSignals'])} | {json.dumps(r['ruleScoreContribution'], ensure_ascii=False)} | {json.dumps(r['synergyContribution'], ensure_ascii=False)} | 0 | {r['finalScore']} | {r['errorCause']} |" for r in xs) or "| None | | | | | | | | | | | | | |"
    counts = lambda xs: Counter(r["errorCause"] for r in xs)
    top = lambda xs: "\n".join(f"{i}. `{cause}`: {count}건" for i,(cause,count) in enumerate(counts(xs).most_common(),1)) or "- 없음"
    cohort_lines=[]
    for name, xs in cohorts.items():
        c=Counter(r["predicted"] for r in xs); correct=sum(r["expected"]==r["predicted"] for r in xs)
        cohort_lines.append(f"| {name} | {len(xs)} | {c['NORMAL']} | {c['SUSPICIOUS']} | {c['PHISHING']} | {c['UNKNOWN']} | {correct/len(xs):.4f} | {sum(r['expected']=='NORMAL' and r['predicted']!='NORMAL' for r in xs)} | {sum(r['expected']=='PHISHING' and r['predicted']!='PHISHING' for r in xs)} |")
    header="| caseId | cohort | expected | predicted | score | candidate brand | official domain | current domain | signals | rule contribution | synergy | Gemini | final | cause |\n|---|---|---|---|---:|---|---|---|---|---|---|---:|---:|---|"
    return f"""# Domestic Page Behavior Baseline

## 평가 목적
등록된 국내 금융·정부기관 범위에서 deterministic rule/fusion의 FP/FN 원인을 측정한다.

## Cohort 구성 및 안전성 원칙
총 80건(공식 정상 20, 브랜드 언급 정상 20, 합성 사칭 30, 수집 불완전 10)이다. 모든 URL은 공식 도메인 또는 `example.com`/`test.invalid`이고, HTML은 script/iframe/object/embed/event handler/javascript URL/base64 blob 없는 비실행 정적 문자열이다.

## 전체 및 cohort별 결과
| Cohort | Total | NORMAL | SUSPICIOUS | PHISHING | UNKNOWN | Exact accuracy | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(cohort_lines)}

## Strict metric (PHISHING positive)
`{json.dumps(strict, ensure_ascii=False)}`

## Alert metric (SUSPICIOUS + PHISHING positive)
`{json.dumps(alert, ensure_ascii=False)}`

## Before / After
| View | Before | After |
|---|---|---|
| Exact | 48/80 (0.6000) | {sum(r['expected'] == r['predicted'] for r in results)}/80 ({sum(r['expected'] == r['predicted'] for r in results)/80:.4f}) |
| Strict | TP 18, TN 40, FP 0, FN 12, recall 0.6000 | TP {strict['tp']}, TN {strict['tn']}, FP {strict['fp']}, FN {strict['fn']}, recall {strict['recall']:.4f} |
| Alert | TP 30, TN 20, FP 20, FN 0, recall 1.0000 | TP {alert['tp']}, TN {alert['tn']}, FP {alert['fp']}, FN {alert['fn']}, recall {alert['recall']:.4f} |

## FP 상세
{header}
{table(fp)}

## FN 상세
{header}
{table(fn)}

## FP Top 원인
{top(fp)}

## FN Top 원인
{top(fn)}

## 개선 후보
| 원인 | 영향 파일 | 가장 작은 수정 후보 | 예상 효과 | 회귀 위험 | 추가 테스트 |
|---|---|---|---|---|---|
| BRAND_MENTION_FALSE_IMPERSONATION | `brand_reference.py`, `dom_risk_analyzer.py` | 브랜드 후보와 사칭 증거를 분리하고 비공식 도메인만으로 mismatch 위험을 확정하지 않기 | 독립 안내·뉴스 FP 감소 | 텍스트만 있는 사칭 recall 감소 | 필요 |
| SENSITIVE_FIELD_NOT_DETECTED | `dom_risk_analyzer.py` | input label/name 동의어 coverage 보강 | credential 기반 FN 감소 | 일반 폼 오탐 증가 | 필요 |
| SOCIAL_ENGINEERING_NOT_DETECTED | `dom_risk_analyzer.py` | 국내 사기 문구 신호 coverage를 별도 검증 후 보강 | 약한 사칭 FN 감소 | 안내문 FP 증가 | 필요 |
| WEAK_BRAND_EVIDENCE | `dom_risk_analyzer.py`, `risk_fusion.py` | 브랜드 근거 강도를 별도 feature로 모델링 | 단순 언급과 사칭 분리 | 점수 정책 회귀 가능 | 필요 |

## 확인
이번 단계에서는 production scoring weight, threshold, `risk_fusion.py`, 브랜드 데이터, Gemini prompt를 수정하지 않았다. 합성 baseline의 결과이며 실제 운영 성능 추정치는 아니다.
"""

def main():
    rows=build_rows(); MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in rows), encoding="utf-8")
    results=evaluate(rows); RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/"predictions.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in results),encoding="utf-8")
    summary={"sampleCount":len(results),"strict":metric(results,False),"alert":metric(results,True),
             "cohorts":{k:dict(Counter(r["predicted"] for r in results if r["cohort"]==k)) for k in sorted({r["cohort"] for r in results})}}
    (RESULTS/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text(render(results),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__ == "__main__": main()
