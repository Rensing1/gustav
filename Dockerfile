# Base image: Python 3.11-slim keeps the runtime lean
FROM python:3.11-slim

# Set container working directory
WORKDIR /app

# System build dependencies (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
  && apt-get purge -y --auto-remove gcc || true

# Copy the backend as a Python package. The runtime entry point is
# `backend.web.main:app`, so the image must preserve the repository package
# layout instead of flattening `backend/web` into `/app`.
COPY backend ./backend

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Security: run as non-root user (least privilege)
RUN useradd -m -u 10001 app && chown -R app:app /app
USER app

# Expose FastAPI port
EXPOSE 8000

# Start server (no reload to keep in-memory state stable during E2E tests)
CMD ["uvicorn", "backend.web.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Lightweight healthcheck hitting the app's health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); print('ok')" || exit 1
