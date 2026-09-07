#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.venv"
PIP="$VENV/bin/pip"

_ensure_venv() {
  if [[ -x "$PIP" ]]; then
    return 0
  fi
  rm -rf "$VENV"
  if python3 -m venv "$VENV" 2>/dev/null; then
    return 0
  fi
  echo "==> python3-venv no disponible; creando .venv con get-pip..."
  python3 -m venv --without-pip "$VENV"
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/robita-get-pip.py
  "$VENV/bin/python" /tmp/robita-get-pip.py
}

_ensure_venv
source "$VENV/bin/activate"
"$PIP" install --upgrade pip wheel setuptools

ARCH="$(uname -m)"
RAG_REQ="$ROOT/01_SERVICES/rag-engine/requirements.txt"
if [[ "$ARCH" == "aarch64" && -f "$ROOT/01_SERVICES/rag-engine/requirements-jetson.txt" ]]; then
  RAG_REQ="$ROOT/01_SERVICES/rag-engine/requirements-jetson.txt"
  echo "==> Jetson ($ARCH): PyTorch CPU (sin CUDA pip)"
  "$PIP" install torch --index-url https://download.pytorch.org/whl/cpu
fi

for req in \
  "$ROOT/01_SERVICES/stt-engine/requirements.txt" \
  "$ROOT/01_SERVICES/tts-engine/requirements.txt" \
  "$ROOT/01_SERVICES/wakeword-engine/requirements.txt" \
  "$RAG_REQ" \
  "$ROOT/03_ADAPTERS/robot-udit-physical/requirements-edge.txt"
do
  echo "==> pip install -r $req"
  "$PIP" install -r "$req"
done

echo "Entorno listo en $VENV"
