# syntax=docker/dockerfile:1

# --- Stage 1: Build dependencies ---
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user and required dirs
RUN adduser --disabled-password --no-create-home appuser && \
    mkdir -p /app/uploads /app/vector_store /app/.cache/hf && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Production entrypoint
CMD ["gunicorn", "main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "4", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-"]
