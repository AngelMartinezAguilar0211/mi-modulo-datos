# ==========================================
# Stage 1: Build Dependencies
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv for extremely fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv venv /opt/venv

# Install only the packages required by the FastAPI app and pipeline
# python-multipart is required for UploadFile (CSV ingestion endpoint)
RUN . /opt/venv/bin/activate && \
    uv pip install --no-cache fastapi uvicorn duckdb pydantic pydantic-core python-multipart

# ==========================================
# Stage 2: Final Minimal Runtime Image
# ==========================================
FROM python:3.11-slim

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Ensure paths inside the virtual environment are used by default
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy the FastAPI app and pipeline source code
COPY app/ app/
COPY pipeline/ pipeline/

# Expose port 8000
EXPOSE 8000

# Docker Healthcheck calling GET /health every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start uvicorn server binding to 0.0.0.0 (inside container)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
