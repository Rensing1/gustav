#!/bin/bash
set -euo pipefail

# ── Einstellungen ──────────────────────────────────────────────────────────────
RUNTIME=21600          # 6 Stunden = 21.600 s
INTERVAL=30            # Aufzeichnungsintervall in Sekunden

TS="$(date +%Y%m%d_%H%M%S)"
ATOP_LOG="/var/log/atop/atop_30s_${TS}.log"
ROCM_LOG="/var/log/atop/rocm_30s_${TS}.log"

# ── Checks ─────────────────────────────────────────────────────────────────────
if ! command -v atop >/dev/null 2>&1; then
  echo "Fehler: 'atop' ist nicht installiert." >&2; exit 1
fi
if ! command -v rocm-smi >/dev/null 2>&1; then
  echo "Fehler: 'rocm-smi' ist nicht installiert / nicht im PATH." >&2
  echo "Bitte ROCm-Tools installieren (Paket: rocm-smi) und erneut versuchen." >&2
  exit 1
fi

sudo -v  # sudo-Credential vorab anfordern

echo "Starte Aufzeichnung: ${RUNTIME}s (=$((RUNTIME/3600))h) im ${INTERVAL}s-Intervall"
echo "atop-Log:  $ATOP_LOG"
echo "ROCm-Log:  $ROCM_LOG"

# ── GPU-Sampler (rocm-smi) als Funktion ───────────────────────────────────────
gpu_sampler() {
  # Header
  {
    echo "# ROCm GPU Log"
    echo "# start: $(date -Is)"
    echo "# interval_s: ${INTERVAL}"
    echo "# columns vary by driver version; raw rocm-smi output with timestamps"
    echo
  } | sudo tee -a "$ROCM_LOG" >/dev/null

  # Endzeit berechnen
  end=$(( $(date +%s) + RUNTIME ))

  # Sampling-Schleife
  while [ "$(date +%s)" -lt "$end" ]; do
    {
      echo "===== $(date -Is) ====="
      # Auslastung, VRAM, Temperatur, Power (je nach ROCm-Version verfügbar)
      rocm-smi --showuse --showmemuse --showtemp --showpower || true
      echo
    } | sudo tee -a "$ROCM_LOG" >/dev/null
    sleep "$INTERVAL"
  done

  echo "# end: $(date -Is)" | sudo tee -a "$ROCM_LOG" >/dev/null
}

# ── Prozesse sauber beenden bei Ctrl+C ────────────────────────────────────────
cleanup() {
  pkill -P $$ || true
}
trap cleanup INT TERM

# ── Start: GPU-Sampler im Hintergrund, atop im Vordergrund mit Timeout ────────
gpu_sampler &

# Hinweis: -g aktiviert GPU-Sammeln in atop (falls unterstützt/kompiliert)
sudo timeout "$RUNTIME" atop -g -w "$ATOP_LOG" "$INTERVAL"

wait || true
echo "Fertig! Logs gespeichert:"
echo "  - $ATOP_LOG"
echo "  - $ROCM_LOG"
