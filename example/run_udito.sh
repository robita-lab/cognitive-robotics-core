#!/usr/bin/env bash
# Prueba wakeword «udito» — mismo flujo que run.sh pero con modelo udito.onnx
#   ./example/run_udito.sh
#   ROBITA_DEMO_WW_THRESHOLD=0.35 ./example/run_udito.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"

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
b = eng.CHUNK_SAMPLES
import numpy as np
peak = eng._peak_on_audio(np.random.default_rng(0).standard_normal(b * 20).astype(np.float32) * 0.2)
print(f"auto-test pico={peak:.5f}")
if peak < 0.05:
    raise SystemExit(1)
PY
then
  echo ""
  echo "ERROR: udito.onnx no responde (pico < 0.05) — el modelo actual está roto."
  echo "Hay que reentrenar antes de probar:"
  echo "  cd /opt/robita-lab/ww2 && ./setup_train_env.sh && python train_udito.py"
  echo ""
  echo "Mientras tanto sigue con hey jarvis:"
  echo "  ROBITA_DEMO_WW_THRESHOLD=0.04 ./example/run.sh"
  exit 1
fi

echo "Modelo OK. Di «udito»."
exec "${ROOT}/example/run.sh" "$@"
