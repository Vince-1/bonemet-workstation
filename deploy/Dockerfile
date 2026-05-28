# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages packages
COPY apps/api apps/api
COPY config config
COPY schemas schemas
ENV PYTHONPATH=/app/packages

FROM base AS api
COPY apps/api apps/api
EXPOSE 8080
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM base AS worker
COPY apps/worker apps/worker
CMD ["python", "-m", "apps.worker.main"]
