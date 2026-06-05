#!/usr/bin/env bash
# Prueba wakeword «udito» — mismo flujo que run.sh pero con modelo udito.onnx
#   ./example/run_udito.sh
#   ROBITA_DEMO_WW_THRESHOLD=0.35 ./example/run_udito.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
SELFTEST="${ROOT}/01_SERVICES/wakeword-engine/models/udito_selftest.wav"

export ROBITA_WAKEWORD=udito
export ROBITA_WAKEWORD_MODEL="${ROOT}/01_SERVICES/wakeword-engine/models/udito.onnx"
export ROBITA_DEMO_WW_THRESHOLD="${ROBITA_DEMO_WW_THRESHOLD:-0.35}"

if [[ ! -f "$ROBITA_WAKEWORD_MODEL" ]]; then
  echo "ERROR: falta $ROBITA_WAKEWORD_MODEL"
  echo "Entrena: cd ww2 && python train_udito.py"
  exit 1
fi

echo "==> Comprobando udito.onnx…"
if ! "$PY" <<PY
import sys
from pathlib import Path
ROOT = Path("${ROOT}")
sys.path.insert(0, str(ROOT / "01_SERVICES/wakeword-engine"))
import engine
engine._engine = None
engine._model_verified = False
eng = engine.get_engine()
eng.load()
ref = Path("${SELFTEST}")
if ref.is_file():
    peak = eng._peak_on_audio(engine._load_selftest_wav(ref))
    print(f"auto-test referencia pico={peak:.5f}")
    if peak < 0.35:
        raise SystemExit(1)
else:
    print("auto-test: sin udito_selftest.wav — solo carga del modelo")
PY
then
  echo ""
  echo "ERROR: udito.onnx no detecta la referencia (pico < 0.35)."
  echo "Reentrena o copia el modelo:"
  echo "  cd /opt/robita-lab/ww2 && python train_udito.py"
  echo "  cp ww2/models/udito.onnx 01_SERVICES/wakeword-engine/models/"
  echo ""
  echo "Mientras tanto sigue con hey jarvis:"
  echo "  ROBITA_DEMO_WW_THRESHOLD=0.04 ./example/run.sh"
  exit 1
fi

echo "Modelo OK. Di «udito»."
exec "${ROOT}/example/run.sh" "$@"
