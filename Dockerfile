# Basis-Image: Python 3.11 (slim für kleinere Größe)
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# System-Dependencies (falls später benötigt)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies installieren
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY app/ .

# Port freigeben
EXPOSE 8000

# Entwicklungs-Server starten mit Live-Reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]