#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"

python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip wheel setuptools

for req in \
  "$ROOT/01_SERVICES/stt-engine/requirements.txt" \
  "$ROOT/01_SERVICES/tts-engine/requirements.txt" \
  "$ROOT/01_SERVICES/wakeword-engine/requirements.txt" \
  "$ROOT/01_SERVICES/rag-engine/requirements.txt" \
  "$ROOT/01_SERVICES/pipeline-orchestrator/requirements.txt"
do
  pip install -r "$req"
done

echo "Entorno listo en $VENV"
