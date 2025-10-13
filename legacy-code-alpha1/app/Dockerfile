# Verwende ein offizielles Python-Basisimage.
# Wähle eine Version, die mit deinen Abhängigkeiten kompatibel ist (z.B., 3.10 oder 3.11).
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis im Container auf /app
WORKDIR /app

# Kopiere die Datei mit den Abhängigkeiten in das Arbeitsverzeichnis
COPY requirements.txt requirements.txt

# Installiere die Python-Abhängigkeiten
# --no-cache-dir spart Speicherplatz im Image
# --upgrade pip stellt sicher, dass wir die neueste Pip-Version haben
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kopiere den gesamten Inhalt des lokalen 'app'-Verzeichnisses in das Arbeitsverzeichnis /app im Container
COPY . .

# Gib den Port an, auf dem Streamlit im Container laufen wird (zur Dokumentation)
EXPOSE 8501

# Definiere Healthcheck (optional, aber gut für depends_on in docker-compose)
# Prüft, ob der Streamlit-Server auf Port 8501 antwortet.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s \
  CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Der Standardbefehl, der beim Starten des Containers ausgeführt wird
# Wird durch den 'command' in docker-compose.yml überschrieben, aber gut als Fallback
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]