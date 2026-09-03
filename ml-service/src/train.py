"""Train and evaluate the XGBoost stage-1 classifier from a labelled CSV."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from .features import FEATURE_NAMES, feature_vector


def _load_xy(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = pd.read_csv(csv_path)
    if not {"url", "label"}.issubset(data.columns):
        raise ValueError("CSV must contain url and label columns")
    labels = data["label"].astype(int).to_numpy()
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError("label must contain both 0 (normal) and 1 (phishing)")
    features = np.asarray([feature_vector(url) for url in data["url"].astype(str)], dtype=float)
    return features, labels


def train(csv_path: Path, output_path: Path, eval_path: Path | None = None, metrics_path: Path | None = None) -> None:
    features, labels = _load_xy(csv_path)
    if eval_path:
        x_train, y_train = features, labels
        x_test, y_test = _load_xy(eval_path)
    else:
        x_train, x_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.2, random_state=42, stratify=labels
        )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=0,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    report = classification_report(y_test, probabilities >= 0.5, digits=4, output_dict=True)
    auc = roc_auc_score(y_test, probabilities)
    print(classification_report(y_test, probabilities >= 0.5, digits=4))
    print(f"ROC-AUC: {auc:.4f}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    version = datetime.now(timezone.utc).strftime("xgb-%Y%m%d-%H%M%S")
    joblib.dump(
        {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "version": version,
        },
        output_path,
    )
    if metrics_path:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(
            json.dumps(
                {
                    "model_version": version,
                    "train_rows": int(len(y_train)),
                    "eval_rows": int(len(y_test)),
                    "roc_auc": float(auc),
                    "classification_report": report,
                    "feature_names": FEATURE_NAMES,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True, help="CSV with url,label columns")
    parser.add_argument("--eval-data", type=Path, default=None, help="Optional validation/test CSV")
    parser.add_argument("--output", type=Path, default=Path("artifacts/url_xgb.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("artifacts/metrics.json"))
    arguments = parser.parse_args()
    train(arguments.data, arguments.output, arguments.eval_data, arguments.metrics)
