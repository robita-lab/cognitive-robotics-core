#!/usr/bin/env bash
# Prepara Jetson Orin para UDITO standalone offline.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Robita-Lab — setup Jetson offline"
echo "    Ruta: $ROOT"

if ! command -v python3 >/dev/null; then
  echo "ERROR: instala python3 (apt install python3-venv python3-pip)"
  exit 1
fi

echo "==> Entorno virtual Python..."
bash "$ROOT/scripts/setup-venv.sh"

echo "==> Piper (aarch64 en Jetson)..."
bash "$ROOT/scripts/install-piper-aarch64.sh"

echo "==> Wakeword openWakeWord (base ONNX)..."
if bash "$ROOT/scripts/setup-wakeword-oww.sh" 2>/dev/null; then
  echo "    Wakeword OK"
else
  echo "    AVISO: falta models/udito.onnx — copia tu modelo entrenado y vuelve a ejecutar setup-wakeword-oww.sh"
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

chmod +x "$ROOT/scripts/"*.sh 2>/dev/null || true

echo ""
echo "=========================================="
echo "  Setup base completado"
echo "=========================================="
echo "Siguiente (con internet):"
echo "  ./scripts/download-offline-models.sh"
echo ""
echo "O copiar cachés desde el servidor:"
echo "  ROBITA_SERVER_HOST=IP ./scripts/sync-models-from-server.sh"
echo ""
echo "Luego:"
echo "  Edita .env (ROBITA_AUDIO_INPUT / ROBITA_AUDIO_OUTPUT)"
echo "  ./scripts/Principal-UDITO.sh"
