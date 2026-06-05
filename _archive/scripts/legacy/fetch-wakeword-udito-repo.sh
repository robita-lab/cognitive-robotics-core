#!/usr/bin/env bash
# Copia udito.onnx desde el árbol de entrenamiento local (ww2 o WakeWord-Project).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/01_SERVICES/wakeword-engine/models"
mkdir -p "$DEST"

for src in \
  "$ROOT/WakeWord-Project/models/udito.onnx" \
  "$ROOT/ww2/models/udito.onnx" \
  "$ROOT/ww2/training/output/udito.onnx"; do
  if [[ -f "$src" ]]; then
    cp "$src" "$DEST/udito.onnx"
    ls -lh "$DEST/udito.onnx"
    echo "Copiado desde: $src"
    echo "Prueba: ./scripts/setup-wakeword-oww.sh"
    exit 0
  fi
done

echo "No se encontró udito.onnx. Entrena localmente o copia manualmente a:"
echo "  $DEST/udito.onnx"
exit 1
