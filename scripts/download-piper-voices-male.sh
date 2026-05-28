#!/usr/bin/env bash
# Voces Piper en español, masculinas, calidad baja o media.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICES="$ROOT/01_SERVICES/tts-engine/piper/voices"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"

mkdir -p "$VOICES"

download_voice() {
  local rel="$1"
  local name
  name="$(basename "$rel")"
  if [[ -f "$VOICES/$name" ]] && [[ -s "$VOICES/$name" ]]; then
    echo "==> $name (ya existe)"
    return 0
  fi
  echo "==> $name"
  curl -fsSL --progress-bar -o "$VOICES/$name" "$BASE/$rel"
  curl -fsSL --progress-bar -o "$VOICES/${name}.json" "$BASE/${rel}.json"
  ls -lh "$VOICES/$name"
}

# Masculinas documentadas en catálogo Piper (es / es_MX)
download_voice "es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx"      # muy baja, robótica
download_voice "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"    # media, España
download_voice "es/es_MX/ald/medium/es_MX-ald-medium.onnx"          # media, México

echo ""
echo "Listo (masculinas baja/media). Probar: ./scripts/test-piper-voices.sh"
