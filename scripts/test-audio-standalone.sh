#!/usr/bin/env bash
# Prueba TTS Piper local (sin servicios en :8002).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || ./scripts/setup-venv.sh
if [[ -f .env ]]; then set -a; source .env; set +a; fi

bash "$ROOT/scripts/install-piper-aarch64.sh"

TEXT="Hola, esta es una prueba de audio de UDITO en la Jetson."
OUT="/tmp/udito-jetson-tts-test.wav"

.venv/bin/python <<PY
import sys
from pathlib import Path
sys.path.insert(0, str(Path("$ROOT/01_SERVICES/tts-engine")))
from piper_tts_real import PiperTTS
tts = PiperTTS(config_path="$ROOT/01_SERVICES/tts-engine/config/tts_config.json")
wav = tts.synthesize_to_bytes("$TEXT")
Path("$OUT").write_bytes(wav)
print("WAV:", "$OUT", len(wav), "bytes")
PY

file "$OUT"

OUT_DEV="${ROBITA_AUDIO_OUTPUT:-pulse}"
if [[ "${OUT_DEV,,}" == "pulse" || "${OUT_DEV,,}" == "paplay" ]]; then
  echo ""
  echo ">>> PulseAudio (altavoz de la placa)"
  paplay "$OUT" && echo "Si lo oíste, pon en .env: ROBITA_AUDIO_OUTPUT=pulse" && exit 0
fi

for DEV in "$OUT_DEV" default plughw:1,3 plughw:0,0; do
  echo ""
  echo ">>> Reproduciendo en: $DEV"
  aplay -D "$DEV" "$OUT" && echo "Si lo oíste, pon en .env: ROBITA_AUDIO_OUTPUT=$DEV" && exit 0
done

echo "Prueba: ./scripts/find-speaker.sh"
