#!/usr/bin/env bash
# Arquitectura 3T - UDITO · Pantalla de audio: elegir micrófono/altavoz, probar y guardar en .env
# Ejecutar como el usuario de escritorio (udito), no como root: el audio es de ese usuario.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "Falta .venv — ejecuta ./scripts/setup/jetson.sh"; exit 1; }
[[ "$(id -u)" == "0" ]] && echo "Aviso: estás como root; PulseAudio (micro/altavoz del escritorio) puede no verse."
"$PY" -c "import pygame" 2>/dev/null || "$PY" -m pip install -q pygame
export DISPLAY="${DISPLAY:-:0}"
exec "$PY" "$ROOT/03_ADAPTERS/robot-udit-physical/udito_audio.py"
