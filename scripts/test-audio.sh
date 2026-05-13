#!/usr/bin/env bash
# Prueba por qué altavoz oyes. Di cuál suena.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || ./scripts/setup-venv.sh

TEXT="Hola, esta es una prueba de audio de UDITO."
echo "Generando voz..."
curl -sf -X POST http://127.0.0.1:8002/synthesize \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"$TEXT\"}" -o /tmp/udito-audio-test.wav
file /tmp/udito-audio-test.wav

for DEV in default plughw:0,0 plughw:3,0; do
  echo ""
  echo ">>> Reproduciendo en: $DEV"
  aplay -D "$DEV" /tmp/udito-audio-test.wav || echo "   (falló)"
  read -r -p "¿Lo oíste en $DEV? (s/n): " ok
  [[ "$ok" == "s" || "$ok" == "S" ]] && echo "Pon en .env: ROBITA_AUDIO_OUTPUT=$DEV" && exit 0
done

echo "Ninguno audible. Revisa volumen del sistema (alsamixer)."
