# ML Service: XGBoost URL Risk + SHAP

금융 피싱 URL을 빠르게 1차 선별하는 ML 파트입니다. URL 문자열, 도메인 구조, 금융기관 사칭 신호를 정량 피처로 바꾼 뒤 XGBoost로 위험도를 계산하고, SHAP으로 판단 근거를 설명합니다.

이 서비스는 실제 의심 사이트에 접속하지 않습니다. 위험도가 높은 URL만 2차 `sandbox`/`multimodal-service`로 넘기는 앞단 필터 역할입니다.

## 핵심 포인트

- URL 길이, entropy, punycode, IP host, 의심 TLD, 단축 URL 등 보안적 의미가 있는 피처를 사용합니다.
- 국내 금융기관 브랜드 레지스트리를 기반으로 공식 도메인 여부와 브랜드-도메인 불일치를 탐지합니다.
- XGBoost 결과에 SHAP 설명을 붙여 “왜 위험하다고 봤는지”를 사용자와 발표 자료에 보여줄 수 있습니다.
- 대량 피싱 원본 URL은 public 저장소에 직접 넣지 않고, 출처 기반으로 재현 가능한 가공 파이프라인을 제공합니다.

## 구조

```text
ml-service/
  data/
    financial_brands.csv          # 금융기관 브랜드/공식 도메인/키워드 레지스트리
    financial_official_urls.csv   # 정상 금융 URL 예시
    korean_public_cases.csv       # 국내 금융 피싱 유형 메모
    sample_urls.csv               # 동작 확인용 소형 샘플
    raw/                          # 원본 대량 데이터, git 제외
    processed/                    # train/validation/test 결과, git 제외
  src/
    features.py                   # URL 정적 피처 추출
    domain_rules.py               # 금융기관 사칭 도메인 규칙
    prepare_dataset.py            # PhishTank/Tranco 데이터 정규화 및 분리
    train.py                      # XGBoost 학습, 평가, artifact 저장
    model.py                      # 예측 및 SHAP 설명
    api.py                        # FastAPI 분석 API
```

## 데이터 전략

저장소에는 작은 기준 데이터만 올립니다. 실제 학습에는 `data/raw/`에 외부 데이터를 내려받아 넣고, `prepare_dataset.py`로 `data/processed/`를 생성합니다.

권장 조합:

- phishing: PhishTank verified online feed
- benign: Tranco top list
- domestic context: 금융감독원, 금융보안원, KISA, 경찰청 공개 보도자료 기반 키워드/사례 보강

대량 원본을 그대로 커밋하지 않는 이유는 악성 URL 노출, 재배포 조건, 데이터 최신성 때문입니다. 대신 `manifest.json`에 행 수와 SHA-256을 남겨 재현성을 확보합니다.

## 실행

```bash
cd ml-service
python -m venv .venv
pip install -r requirements.txt
python -m src.train --data data/sample_urls.csv --output artifacts/url_xgb.joblib
uvicorn src.api:app --host 0.0.0.0 --port 8001
pytest
```

대량 데이터 사용 예시:

```bash
python -m src.prepare_dataset --phishtank data/raw/phishtank.csv.bz2 --tranco data/raw/tranco.csv.zip --output data/processed
python -m src.train --data data/processed/train.csv --eval-data data/processed/validation.csv --output artifacts/url_xgb.joblib --metrics artifacts/metrics.json
```

## API 응답

`POST /v1/analyze`는 위험 확률, 라벨, 2차 분석 필요 여부, SHAP 판단 근거, 피처값, 모델 버전을 반환합니다.

기본 라벨:

- `NORMAL`: 위험도 40% 미만
- `SUSPICIOUS`: 위험도 40% 이상
- `PHISHING`: 위험도 70% 이상

운영 단계에서는 검증 데이터 성능과 오탐 비용을 기준으로 임계값을 다시 조정해야 합니다.

## 외부 검증 시드셋

`data/external_test_seed.csv`는 학습에 사용하지 않는 검증용 시드셋입니다. 공식 정상 URL과 `example.com` 기반 합성 금융·정책자금 사칭 URL을 포함하며, 실제 피싱 사이트에 접속하지 않고 1차 라우팅을 검증할 때 사용합니다. 실제 대량 원본은 `data/raw/`에 별도로 수집하고 Git에는 커밋하지 않습니다.
