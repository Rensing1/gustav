#!/bin/bash
# Script zum Erstellen eines optimierten Ollama-Modells mit erhöhter Kontextlänge

echo "Erstelle optimiertes Gemma3-Modell mit 32k Kontext..."

# Modelfile-Inhalt
cat <<EOF > /tmp/gemma3-optimized.modelfile
FROM gemma3:12b

# Erhöhe Kontextlänge auf 32768 Token (32k)
PARAMETER num_ctx 32768
PARAMETER num_batch 512
PARAMETER num_gpu -1
PARAMETER temperature 0.7
PARAMETER repeat_penalty 1.1

SYSTEM """Du bist ein erfahrener Pädagoge, der konstruktives und ermutigendes Feedback gibt. 
Deine Antworten sind klar strukturiert, präzise und auf die Zielgruppe angepasst."""
EOF

# Kopiere Modelfile in Container und erstelle Modell
docker cp /tmp/gemma3-optimized.modelfile gustav_ollama:/tmp/
docker-compose exec -T ollama ollama create gemma3-optimized -f /tmp/gemma3-optimized.modelfile

# Aufräumen
rm /tmp/gemma3-optimized.modelfile

echo "Optimiertes Modell 'gemma3-optimized' wurde erstellt!"
echo "Kontextlänge: 32768 Token"