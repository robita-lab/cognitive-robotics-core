#!/usr/bin/env bash
# Descarga voces Piper es_ES: 2× low + 1× x_low (estilo más robótico).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICES="$ROOT/01_SERVICES/tts-engine/piper/voices"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"

mkdir -p "$VOICES"

download_voice() {
  local rel="$1"
  local name
  name="$(basename "$rel")"
  echo "==> $name"
  curl -fsSL --progress-bar -o "$VOICES/$name" "$BASE/$rel"
  curl -fsSL --progress-bar -o "$VOICES/${name}.json" "$BASE/${rel}.json"
  ls -lh "$VOICES/$name"
}

download_voice "es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx"
download_voice "es/es_ES/mls_9972/low/es_ES-mls_9972-low.onnx"
download_voice "es/es_ES/mls_10246/low/es_ES-mls_10246-low.onnx"

echo ""
echo "Listo. Voces en: $VOICES"
echo "Probar: ./scripts/test-piper-voices.sh"
