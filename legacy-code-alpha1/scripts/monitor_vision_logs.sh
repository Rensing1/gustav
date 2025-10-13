#!/bin/bash
# Vision Processing Log Monitor
# Überwacht alle relevanten Container-Logs während Upload-Tests

echo "🔍 GUSTAV Vision Processing Log Monitor"
echo "📊 Überwacht: feedback_worker, ollama, app logs"
echo "⚡ Filtert auf: VISION, GPU, API, ERROR, TIMEOUT"
echo "🔥 Drücke Ctrl+C zum Beenden"
echo "============================================================"

# Parallel log monitoring mit farbiger Ausgabe
docker compose logs -f --tail=20 feedback_worker | sed 's/^/[WORKER] /' &
WORKER_PID=$!

docker compose logs -f --tail=20 ollama | sed 's/^/[OLLAMA] /' &
OLLAMA_PID=$!

docker compose logs -f --tail=10 app | grep -i 'vision\|upload\|error' | sed 's/^/[APP] /' &
APP_PID=$!

# GPU Monitor parallel starten (falls verfügbar)
if command -v python3 &> /dev/null; then
    python3 /home/felix/gustav/scripts/monitor_amd_gpu.py &
    GPU_PID=$!
fi

# Warten und cleanup bei Ctrl+C
trap "echo '🛑 Stopping monitors...'; kill $WORKER_PID $OLLAMA_PID $APP_PID $GPU_PID 2>/dev/null; exit 0" INT

echo "✅ Alle Monitore gestartet. Führe jetzt einen Upload-Test durch..."

# Keep script running
wait