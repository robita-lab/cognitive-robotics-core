#!/usr/bin/env bash
# Descarga lo que SÍ está en GitHub (micro_model.tflite). El modelo OWW udito.onnx hay que subirlo aparte.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/01_SERVICES/wakeword-engine/models"
mkdir -p "$DEST"
URL="https://raw.githubusercontent.com/robita-lab/cognitive-robotics-core/main/01_SERVICES/wakeword-engine/micro_model.tflite"
echo "==> Descargando desde GitHub: micro_model.tflite"
curl -fsSL -o "$DEST/micro_model.tflite" "$URL"
ls -la "$DEST/micro_model.tflite"
echo ""
echo "En GitHub NO está udito.onnx ni udito_model.net (solo referenciado en wake_word.json)."
echo "Si entrenaste con openWakeWord, copia el export real:"
echo "  cp tu_udito.onnx $DEST/udito.onnx"
echo "Luego: ./scripts/setup-wakeword-oww.sh"
