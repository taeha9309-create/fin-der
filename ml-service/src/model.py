"""Model loading, risk prediction, and SHAP explanation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from .features import FEATURE_NAMES, extract_features

REASON_LABELS = {
    "url_length": "비정상적으로 긴 URL",
    "hostname_length": "긴 호스트 이름",
    "path_length": "복잡한 경로 구조",
    "query_length": "긴 쿼리 문자열",
    "dot_count": "과도한 점(.) 사용",
    "hyphen_count": "과도한 하이픈 사용",
    "digit_ratio": "높은 숫자 비율",
    "special_char_ratio": "높은 특수문자 비율",
    "url_entropy": "무작위성이 높은 URL 문자열",
    "subdomain_depth": "과도한 서브도메인 깊이",
    "query_param_count": "다수의 쿼리 파라미터",
    "percent_encoding_count": "반복적인 URL 인코딩",
    "has_ip_host": "도메인 대신 IP 주소 사용",
    "has_punycode": "유사문자 공격에 쓰일 수 있는 Punycode",
    "has_at_symbol": "URL 내 @ 기호 사용",
    "uses_https": "HTTPS 사용 여부",
    "uses_nonstandard_port": "비표준 포트 사용",
    "has_suspicious_tld": "피싱에 자주 쓰이는 최상위 도메인",
    "has_financial_term": "금융기관 관련 키워드 포함",
    "uses_shortener": "단축 URL 서비스 사용",
    "official_financial_domain": "등록된 금융기관 공식 도메인 여부",
    "brand_domain_mismatch": "금융 브랜드명과 공식 도메인의 불일치",
    "brand_domain_similarity": "공식 도메인과 유사한 철자 구조",
}


@dataclass
class Prediction:
    probability: float
    label: str
    reasons: list[dict[str, object]]
    features: dict[str, float]
    model_version: str


class UrlRiskModel:
    def __init__(self, artifact_path: str | Path):
        artifact = joblib.load(artifact_path)
        if artifact["feature_names"] != FEATURE_NAMES:
            raise ValueError("Model feature schema does not match service feature schema")
        self.model = artifact["model"]
        self.version = artifact.get("version", "unknown")

    def predict(self, url: str) -> Prediction:
        values = extract_features(url)
        matrix = np.asarray([[values[name] for name in FEATURE_NAMES]], dtype=float)
        probability = float(self.model.predict_proba(matrix)[0, 1])
        if values["official_financial_domain"] == 1.0:
            probability = min(probability, 0.05)
        reasons = self._explain(matrix)
        label = "PHISHING" if probability >= 0.70 else "SUSPICIOUS" if probability >= 0.40 else "NORMAL"
        return Prediction(probability, label, reasons, values, self.version)

    def _explain(self, matrix: np.ndarray) -> list[dict[str, object]]:
        import shap

        explanation = shap.TreeExplainer(self.model)(matrix)
        contributions = np.asarray(explanation.values)
        if contributions.ndim == 3:
            contributions = contributions[:, :, -1]
        row = contributions[0]
        ranked = sorted(enumerate(row), key=lambda item: abs(float(item[1])), reverse=True)
        return [
            {
                "feature": FEATURE_NAMES[index],
                "reason": REASON_LABELS[FEATURE_NAMES[index]],
                "contribution": round(float(value), 6),
                "direction": "RISK_UP" if value > 0 else "RISK_DOWN",
            }
            for index, value in ranked[:5]
        ]
