#!/usr/bin/env bash
# Ventana que simula la pantalla de ojos de UDITO (lee emociones del pipeline).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
ADAPTER="${ROOT}/03_ADAPTERS/robot-udit-physical"

[[ -x "$PY" ]] || { echo "Falta .venv — ejecuta ./scripts/setup/jetson.sh"; exit 1; }

"$PY" -c "import pygame" 2>/dev/null || {
  echo "==> Instalando pygame (solo para simulación de pantalla)..."
  "$PY" -m pip install pygame
}

export DISPLAY="${DISPLAY:-:0}"
export ROBITA_SPEECH_EVENT_FILE="${ROBITA_SPEECH_EVENT_FILE:-/tmp/udito_speech_out.json}"
export ROBITA_FACE_BACKEND="${ROBITA_FACE_BACKEND:-sim}"

exec "$PY" "$ADAPTER/udito_face.py"
