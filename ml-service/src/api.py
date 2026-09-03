"""FastAPI boundary for Spring Boot integration."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .model import UrlRiskModel


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=4, max_length=4096)


@asynccontextmanager
async def lifespan(app: FastAPI):
    artifact = Path(os.getenv("MODEL_PATH", "artifacts/url_xgb.joblib"))
    app.state.model = UrlRiskModel(artifact) if artifact.exists() else None
    yield


app = FastAPI(title="fin-der ML Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health(request: Request) -> dict[str, object]:
    return {"status": "ok", "model_loaded": request.app.state.model is not None}


@app.post("/v1/analyze")
def analyze(payload: AnalyzeRequest, request: Request) -> dict[str, object]:
    model: UrlRiskModel | None = request.app.state.model
    if model is None:
        raise HTTPException(status_code=503, detail="Model artifact is not loaded; train the model first")
    try:
        result = model.predict(payload.url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    risk_score = round(result.probability * 100)
    return {
        "url": payload.url,
        "stage": "URL_XGBOOST",
        "risk_probability": round(result.probability, 6),
        "risk_score": risk_score,
        "label": result.label,
        "requires_deep_analysis": risk_score >= 40,
        "xai_reasons": result.reasons,
        "features": result.features,
        "model_version": result.model_version,
    }

