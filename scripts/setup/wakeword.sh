#!/usr/bin/env bash
# Modelos base openWakeWord (ONNX) + comprobar modelo custom «udito».
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WW="$ROOT/01_SERVICES/wakeword-engine"
MODELS="$WW/models"
PY="${ROOT}/.venv/bin/python"

[[ -x "$PY" ]] || { echo "Falta .venv — ejecuta ./scripts/setup/jetson.sh"; exit 1; }

"$PY" -m pip install -q onnxruntime 'numpy<2.1' 2>/dev/null || \
  "$PY" -m pip install -q onnxruntime 'numpy<2.1'

# openwakeword declara tflite-runtime en Linux; en PC usamos solo ONNX (--no-deps).
"$PY" -m pip install -q --no-deps 'openwakeword>=0.6.0' 2>/dev/null || \
  "$PY" -m pip install -q --no-deps 'openwakeword>=0.6.0'

mkdir -p "$MODELS"

echo "==> Descargando melspectrogram + embedding (ONNX)…"
"$PY" <<PY
from pathlib import Path
import sys
sys.path.insert(0, "$WW")
from engine import get_engine
get_engine().ensure_base_models()
print("OK:", Path("$WW/models/openwakeword").resolve())
PY

echo ""
echo "==> Modelo custom «udito»"
if compgen -G "$MODELS/udito*.onnx" >/dev/null; then
  ls -la "$MODELS"/udito*.onnx 2>/dev/null || true
  echo "Modelo udito encontrado."
else
  echo "FALTA el modelo entrenado. Copia tu export de openWakeWord, por ejemplo:"
  echo "  cp /ruta/donde/entrenaste/udito.onnx $MODELS/udito.onnx"
  echo "o: export ROBITA_WAKEWORD_MODEL=/ruta/udito.onnx"
  exit 1
fi

echo ""
echo "Prueba rápida:"
"$PY" -c "import sys; sys.path.insert(0,'$WW'); from engine import load; load(); print('openWakeWord cargado.')"
