# Basis-Image: Python 3.11 (slim für kleinere Größe)
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# System-Dependencies (falls später benötigt)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies installieren
COPY backend/web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Web-App-Code kopieren (SSR/HTMX)
# Copy web layer first so reload still works as expected
COPY backend/web/ .
# Identity Access domain layer is located outside web package; copy it explicitly
COPY backend/identity_access ./identity_access
COPY backend/teaching ./teaching
COPY backend/learning ./backend/learning
COPY backend/__init__.py ./backend/__init__.py

ENV PYTHONPATH=/app:/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Security: run as non-root user (least privilege)
RUN useradd -m -u 10001 app && chown -R app:app /app
USER app

# Port freigeben
EXPOSE 8000

# Server starten (ohne Reload für stabile In-Memory-State während E2E)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
