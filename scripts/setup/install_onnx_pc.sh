#!/usr/bin/env bash
# Instala onnxruntime en PC de desarrollo (x86_64).
# NO usar en Jetson — ahí va install_onnx_jetson.sh
#
# Uso:
#   ./scripts/setup/install_onnx_pc.sh          # CPU (PyPI, suficiente para dev)
#   ./scripts/setup/install_onnx_pc.sh --gpu    # onnxruntime-gpu (NVIDIA x86_64)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${1:-$ROOT/.venv}"
USE_GPU=0

if [[ "${1:-}" == "--gpu" ]]; then
  USE_GPU=1
  VENV="$ROOT/.venv"
elif [[ "${2:-}" == "--gpu" ]]; then
  USE_GPU=1
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
ARCH="$(uname -m)"

if [[ "$ARCH" == "aarch64" ]]; then
  echo "ERROR: estás en ARM64 (Jetson). Usa:"
  echo "  ./scripts/setup/install_onnx_jetson.sh"
  exit 1
fi

if [[ ! -x "$PY" ]]; then
  echo "ERROR: no existe venv en $VENV — ejecuta ./scripts/setup/venv.sh"
  exit 1
fi

echo "==> install_onnx_pc.sh (desarrollo x86_64)"
echo "    venv: $VENV"
echo "    python: $($PY --version)"
echo "    arquitectura: $ARCH"

"$PIP" uninstall -y onnxruntime onnxruntime-gpu 2>/dev/null || true

if [[ "$USE_GPU" -eq 1 ]]; then
  echo "==> Instalando onnxruntime-gpu (PyPI x86_64)…"
  if ! "$PIP" install onnxruntime-gpu; then
    echo "AVISO: onnxruntime-gpu falló — instalando CPU"
    "$PIP" install 'onnxruntime>=1.16'
  fi
else
  echo "==> Instalando onnxruntime CPU (PyPI)…"
  "$PIP" install 'onnxruntime>=1.16'
fi

echo "==> openwakeword (solo ONNX, sin tflite)…"
"$PIP" install -q --no-deps 'openwakeword>=0.6.0' 2>/dev/null || true

echo "==> Verificación…"
"$PY" - <<'PY'
import onnxruntime as ort
providers = ort.get_available_providers()
print("onnxruntime:", ort.__version__)
print("providers:", providers)
cuda = "CUDAExecutionProvider" in providers
print("CUDA:", "OK" if cuda else "no (usa wake_provider=cpu en wakeword.pc.json)")
PY

echo ""
echo "=========================================="
echo "  PC listo para desarrollo wakeword"
echo "  Config recomendada: config/wakeword.pc.json"
echo "  export ROBITA_WAKEWORD_CONFIG=config/wakeword.pc.json"
echo "  Diagnóstico: .venv/bin/python 01_SERVICES/wakeword-engine/check_env.py"
echo "=========================================="
