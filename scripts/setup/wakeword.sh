#!/usr/bin/env bash
# Modelos base openWakeWord (ONNX) + comprobar modelo custom «udito».
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WW="$ROOT/01_SERVICES/wakeword-engine"
MODELS="$WW/models"
PY="${ROOT}/.venv/bin/python"

[[ -x "$PY" ]] || { echo "Falta .venv — ejecuta ./scripts/setup/jetson.sh"; exit 1; }
if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env"; set +a; fi

"$PY" -m pip install -q onnxruntime 'numpy<2.1' 2>/dev/null || \
  "$PY" -m pip install -q onnxruntime 'numpy<2.1'

# openwakeword declara tflite-runtime en Linux; en PC usamos solo ONNX (--no-deps).
"$PY" -m pip install -q --no-deps 'openwakeword>=0.6.0' 2>/dev/null || \
  "$PY" -m pip install -q --no-deps 'openwakeword>=0.6.0'

# onnxruntime puede subir numpy a 2.x — fijar de nuevo (Jetson ARM).
"$PY" -m pip install -q 'numpy>=1.24,<2' 2>/dev/null || true

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
echo "==> Modelos preentrenados OWW (hey_jarvis, alexa, …)"
"$PY" <<PY
from pathlib import Path
from openwakeword.utils import download_models
base = Path("$WW/models/openwakeword")
base.mkdir(parents=True, exist_ok=True)
download_models(model_names=["hey_jarvis"], target_directory=str(base))
print("OK:", base / "hey_jarvis_v0.1.onnx")
PY

echo ""
echo "==> Modelo custom «udito»"
if compgen -G "$MODELS/udito*.onnx" >/dev/null; then
  ls -la "$MODELS"/udito*.onnx 2>/dev/null || true
  echo "Modelo udito encontrado."
elif [[ -n "${ROBITA_WAKEWORD_MODEL:-}" && -f "${ROBITA_WAKEWORD_MODEL}" ]]; then
  echo "Usando ROBITA_WAKEWORD_MODEL=$ROBITA_WAKEWORD_MODEL"
else
  echo "Sin udito.onnx — usa ROBITA_WAKEWORD_MODEL=.../hey_jarvis_v0.1.onnx en .env (demo)"
fi

echo ""
echo "Prueba rápida:"
"$PY" <<PY
import sys
sys.path.insert(0, "$WW")
from engine import load, get_engine
load()
peak = get_engine()._peak_on_audio(__import__("numpy").zeros(get_engine().CHUNK_SAMPLES * 12, dtype="float32"))
model = get_engine()._model_path().name
print(f"openWakeWord cargado ({model}, pico silencio={peak:.4f})")
if model == "udito.onnx" and peak < 0.05:
    print("FALTA un udito.onnx entrenado — ver ww2/train_udito.py")
    sys.exit(1)
PY
