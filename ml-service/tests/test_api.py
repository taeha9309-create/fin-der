from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api import app


class FakeModel:
    def __init__(self, probability: float, label: str):
        self.result = SimpleNamespace(
            probability=probability,
            label=label,
            reasons=[],
            features={},
            model_version="test",
        )

    def predict(self, url: str):
        return self.result


@pytest.mark.parametrize(
    ("probability", "label", "expected"),
    [
        (0.10, "NORMAL", False),
        (0.20, "NORMAL", False),
        (0.21, "NORMAL", True),
        (0.55, "SUSPICIOUS", True),
        (0.85, "PHISHING", True),
    ],
)
def test_deep_analysis_required_above_safe_cutoff(
    probability: float, label: str, expected: bool
):
    with TestClient(app) as client:
        app.state.model = FakeModel(probability, label)

        response = client.post("/v1/analyze", json={"url": "https://example.com"})

    assert response.status_code == 200
    assert response.json()["requires_deep_analysis"] is expected
