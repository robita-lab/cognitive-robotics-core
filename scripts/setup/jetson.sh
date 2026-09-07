#!/usr/bin/env bash
# Prepara Jetson Orin para UDITO standalone offline.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "==> Robita-Lab — setup Jetson offline"
echo "    Ruta: $ROOT"

if ! command -v python3 >/dev/null; then
  echo "ERROR: instala python3 (apt install python3-venv python3-pip)"
  exit 1
fi

echo "==> Entorno virtual Python..."
bash "$ROOT/scripts/setup/venv.sh"

echo "==> Piper (aarch64 en Jetson)..."
bash "$ROOT/scripts/setup/piper-jetson.sh"

echo "==> Wakeword openWakeWord (base ONNX)..."
if bash "$ROOT/scripts/setup/wakeword.sh" 2>/dev/null; then
  echo "    Wakeword OK"
else
  echo "    AVISO: falta models/udito.onnx — copia tu modelo entrenado y vuelve a ejecutar wakeword.sh"
fi

echo "==> onnxruntime-gpu NVIDIA (Jetson ARM64)..."
if bash "$ROOT/scripts/setup/install_onnx_jetson.sh"; then
  echo "    ONNX CUDA OK"
else
  echo "    AVISO: falló install_onnx_jetson.sh — revisa JetPack y red"
fi

mkdir -p "$ROOT/data/huggingface" "$ROOT/logs" \
  "$ROOT/01_SERVICES/rag-engine/data/rag_cache"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "==> Creando .env desde .env.example..."
  cp "$ROOT/.env.example" "$ROOT/.env"
  {
    echo ""
    echo "# --- Jetson offline (generado por setup-jetson-offline.sh) ---"
    echo "ROBITA_RAG_CONFIG=$ROOT/01_SERVICES/rag-engine/config/rag_config.jetson.json"
    echo "HF_HOME=$ROOT/data/huggingface"
    echo "CUDA_VISIBLE_DEVICES="
  } >> "$ROOT/.env"
else
  echo "==> .env ya existe (no se sobrescribe)"
fi

find "$ROOT/scripts" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true

echo ""
echo "=========================================="
echo "  Setup base completado"
echo "=========================================="
echo "Siguiente (con internet):"
echo "  ./scripts/setup/models-download.sh"
echo ""
echo "Luego edita .env (ROBITA_AUDIO_INPUT / ROBITA_AUDIO_OUTPUT) y:"
echo "  ./UDITO"
