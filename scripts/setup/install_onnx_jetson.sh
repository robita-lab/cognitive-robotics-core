#!/usr/bin/env bash
# Instala onnxruntime-gpu oficial de NVIDIA para Jetson (ARM64 + CUDA).
# Reemplaza el wheel genérico de PyPI (solo CPU) que rompe scores inestables.
#
# Uso:
#   ./scripts/setup/install_onnx_jetson.sh
#   ./scripts/setup/install_onnx_jetson.sh /opt/robita-lab/.venv
#
# JetPack 6.x + cuDNN 9 → onnxruntime-gpu 1.23 (cp310, libcudnn.so.9)
# JetPack 6.x + cuDNN 8 → onnxruntime-gpu 1.18 (wheel NVIDIA box.com)
# JetPack 5.x → onnxruntime-gpu 1.16 (cp38/cp310 según Python del venv)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${1:-$ROOT/.venv}"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: no existe venv en $VENV — ejecuta primero ./scripts/setup/venv.sh"
  exit 1
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" ]]; then
  echo "ERROR: install_onnx_jetson.sh es SOLO para Jetson (aarch64)."
  echo "       Esta máquina es: $ARCH"
  echo "       En PC de desarrollo usa: ./scripts/setup/install_onnx_pc.sh"
  exit 1
fi

if [[ ! -f /etc/nv_tegra_release ]]; then
  echo "ERROR: no se encuentra /etc/nv_tegra_release — ¿es una Jetson con JetPack?"
  exit 1
fi

echo "==> install_onnx_jetson.sh"
echo "    venv: $VENV"
echo "    python: $($PY --version)"

detect_jetpack_major() {
  if [[ ! -f /etc/nv_tegra_release ]]; then
    echo "0"
    return
  fi
  local line
  line="$(head -1 /etc/nv_tegra_release)"
  if [[ "$line" =~ Jetpack[[:space:]]+([0-9]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "$line" =~ R([0-9]+) ]]; then
    local r="${BASH_REMATCH[1]}"
    if (( r >= 36 )); then
      echo "6"
    elif (( r >= 32 )); then
      echo "5"
    else
      echo "0"
    fi
    return
  fi
  echo "0"
}

JP_MAJOR="$(detect_jetpack_major)"
PY_TAG="$("$PY" -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}")')"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "    JetPack major: ${JP_MAJOR:-?}"
echo "    Python tag: $PY_TAG"

# Wheels ARM64
JP6_CUDNN9_URL="https://github.com/ultralytics/assets/releases/download/v0.0.0/onnxruntime_gpu-1.23.0-${PY_TAG}-${PY_TAG}-linux_aarch64.whl"
JP6_CUDNN8_URL="https://nvidia.box.com/shared/static/48dtuob7meiw6ebgfsfqakc9vse62sg4.whl"
JP6_CUDNN8_WHL="onnxruntime_gpu-1.18.0-${PY_TAG}-${PY_TAG}-linux_aarch64.whl"

JP5_URL="https://nvidia.box.com/shared/static/iizg3ggrtdkqawkmebbfixo7sce6j365.whl"
JP5_WHL="onnxruntime_gpu-1.16.0-${PY_TAG}-${PY_TAG}-linux_aarch64.whl"

has_cudnn9() {
  ldconfig -p 2>/dev/null | grep -q 'libcudnn\.so\.9' \
    || [[ -f /usr/lib/aarch64-linux-gnu/libcudnn.so.9 ]]
}

case "$JP_MAJOR" in
  6)
    if has_cudnn9; then
      ORT_URL="$JP6_CUDNN9_URL"
      ORT_WHL="onnxruntime_gpu-1.23.0-${PY_TAG}-${PY_TAG}-linux_aarch64.whl"
      ORT_VER="1.23.0 (cuDNN 9 / JetPack 6)"
    else
      ORT_URL="$JP6_CUDNN8_URL"
      ORT_WHL="$JP6_CUDNN8_WHL"
      ORT_VER="1.18.0 (cuDNN 8)"
    fi
    ;;
  5)
    ORT_URL="$JP5_URL"
    ORT_WHL="$JP5_WHL"
    ORT_VER="1.16.0"
    ;;
  *)
    echo "ERROR: JetPack no reconocido (major=$JP_MAJOR). Revisa /etc/nv_tegra_release"
    exit 1
    ;;
esac

echo "==> Desinstalando onnxruntime genérico (PyPI CPU)…"
"$PIP" uninstall -y onnxruntime onnxruntime-gpu 2>/dev/null || true

echo "==> Descargando onnxruntime-gpu $ORT_VER ($ORT_WHL)…"
download_wheel() {
  local url="$1" dest="$2"
  if command -v wget >/dev/null; then
    wget -q "$url" -O "$dest"
  elif command -v curl >/dev/null; then
    curl -fsSL "$url" -o "$dest"
  else
    echo "ERROR: instala wget o curl"
    exit 1
  fi
}
download_wheel "$ORT_URL" "$TMPDIR/$ORT_WHL"

install_wheel() {
  local whl="$1"
  if "$PIP" install "$whl"; then
    return 0
  fi
  # JP5: algunos wheels vienen con tag cp38m; renombrar a cp38-cp38
  local alt
  alt="$(echo "$whl" | sed 's/cp38m/cp38/g')"
  if [[ "$alt" != "$whl" && -f "$whl" ]]; then
    cp "$whl" "$TMPDIR/$alt"
    "$PIP" install "$TMPDIR/$alt"
    return $?
  fi
  return 1
}

echo "==> Instalando wheel NVIDIA…"
if ! install_wheel "$TMPDIR/$ORT_WHL"; then
  if [[ "$JP_MAJOR" == "6" ]] && has_cudnn9; then
    echo "AVISO: wheel 1.23 falló — probando 1.18 + cuDNN 8…"
    download_wheel "$JP6_CUDNN8_URL" "$TMPDIR/$JP6_CUDNN8_WHL"
    install_wheel "$TMPDIR/$JP6_CUDNN8_WHL" || true
  fi
  if ! "$PY" -c "import onnxruntime" 2>/dev/null; then
    echo "ERROR: no se pudo instalar onnxruntime-gpu para $PY_TAG"
    exit 1
  fi
fi

echo "==> Ajustando numpy (compatibilidad Jetson)…"
if [[ "$JP_MAJOR" == "6" ]] && has_cudnn9; then
  # ORT 1.23 + resto del stack (scipy, openwakeword, edge)
  "$PIP" install -q 'numpy>=1.26,<2.1'
else
  "$PIP" install -q 'numpy==1.23.5' 2>/dev/null || "$PIP" install -q 'numpy>=1.23,<2.1'
fi

echo "==> Verificación…"
"$PY" - <<'PY'
import onnxruntime as ort
providers = ort.get_available_providers()
print("onnxruntime:", ort.__version__)
print("providers:", providers)
if "CUDAExecutionProvider" not in providers:
    raise SystemExit(
        "CUDAExecutionProvider no disponible — revisa JetPack/CUDA o el wheel instalado."
    )
# Comprobar que CUDA carga en runtime (no solo en la lista)
import tempfile, os
from pathlib import Path
test_model = Path("01_SERVICES/wakeword-engine/models/udito.onnx")
if test_model.is_file():
    sess = ort.InferenceSession(
        str(test_model),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    active = sess.get_providers()[0]
    print("sesión activa:", active)
    if active != "CUDAExecutionProvider":
        print(
            "AVISO: CUDA no cargó en runtime (¿libcudnn.so.8?). "
            "Wakeword usará CPU hasta instalar cuDNN compatible."
        )
    else:
        print("CUDA: OK")
else:
    print("CUDA: OK (providers); sin modelo para prueba de sesión")
PY

echo ""
echo "=========================================="
echo "  onnxruntime-gpu NVIDIA instalado"
echo "  Siguiente: python 01_SERVICES/wakeword-engine/check_env.py"
echo "=========================================="
