#!/usr/bin/env bash
# Prueba wakeword: mic → «hey jarvis» → TTS.
#   ./example/run.sh              — demo en vivo
#   ./example/run.sh --test       — solo TTS
#   ./example/mic_test.py         — medidor de mic
#   ./example/wakeword_score.py   — graba y puntúa (sin mic en vivo)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"

[[ -x "$PY" ]] || { echo "Falta .venv — ./scripts/setup/jetson.sh"; exit 1; }
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
else
  echo "AVISO: sin .env — copia .env.example → .env"
fi

if [[ -n "${ROBITA_WAKEWORD_MODEL:-}" && ! -f "${ROBITA_WAKEWORD_MODEL}" ]]; then
  echo "ERROR: no existe ROBITA_WAKEWORD_MODEL=${ROBITA_WAKEWORD_MODEL}"
  exit 1
fi

if command -v pactl >/dev/null; then
  _RS_SRC="${ROBITA_PULSE_SOURCE:-alsa_input.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.multichannel-input}"
  _RS_SNK="${ROBITA_PULSE_SINK:-alsa_output.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.analog-stereo}"
  pactl set-default-source "$_RS_SRC" 2>/dev/null || true
  pactl set-default-sink "$_RS_SNK" 2>/dev/null || true
fi

exec "$PY" "$ROOT/example/wakeword_demo.py" "$@"
