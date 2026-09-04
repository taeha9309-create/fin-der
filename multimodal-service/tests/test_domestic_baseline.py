import json, sys
from pathlib import Path
SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE / "evaluation"))
from build_domestic_baseline import build_rows

def test_domestic_baseline_shape_balance_and_safety():
    rows = build_rows()
    counts = {}
    forbidden = ("<script", "<iframe", "<object", "<embed", "javascript:", "onerror=", "onclick=")
    for row in rows:
        counts[row["cohort"]] = counts.get(row["cohort"], 0) + 1
        assert {"caseId", "cohort", "expectedLabel", "requestedUrl", "finalUrl", "sourceType", "brand", "note", "input"} <= row.keys()
        html = row["input"]["page"]["html"].lower()
        assert not any(token in html for token in forbidden)
        assert row["sourceType"] == "SAFE_SYNTHETIC_INERT"
    assert counts == {"DOMESTIC_BENIGN_OFFICIAL":20, "DOMESTIC_BENIGN_BRAND_MENTION":20,
                      "DOMESTIC_PHISHING_IMPERSONATION":30, "PARTIAL_UNKNOWN":10}
    assert len({row["caseId"] for row in rows}) == 80
