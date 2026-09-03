FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY data ./data
COPY artifacts ./artifacts

# A fresh clone contains only artifacts/.gitkeep. Build a schema-compatible
# integration model in the image without adding the binary artifact to Git.
RUN if [ ! -f artifacts/url_xgb.joblib ]; then \
      python -m src.train --data data/sample_urls.csv --output artifacts/url_xgb.joblib --metrics artifacts/metrics.json; \
    fi

ENV MODEL_PATH=/app/artifacts/url_xgb.joblib
EXPOSE 8001
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8001"]

