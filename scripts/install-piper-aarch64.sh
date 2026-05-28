#!/usr/bin/env bash
# Instala el binario Piper correcto para Jetson (aarch64) y sus librerías .so.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIPER_DIR="$ROOT/01_SERVICES/tts-engine/piper"
PIPER_BIN="$PIPER_DIR/piper"
ARCH="$(uname -m)"
PIPER_VERSION="${PIPER_VERSION:-2023.11.14-2}"

if [[ "$ARCH" != "aarch64" ]]; then
  echo "Arquitectura $ARCH: no se cambia Piper (servidor x86_64 usa el binario del repo)."
  exit 0
fi

if [[ -x "$PIPER_BIN" ]] && file "$PIPER_BIN" | grep -q "aarch64" \
  && [[ -f "$PIPER_DIR/libpiper_phonemize.so.1" ]] \
  && ldd "$PIPER_BIN" 2>/dev/null | grep -q "libpiper_phonemize"; then
  echo "Piper aarch64 ya instalado: $PIPER_BIN"
  exit 0
fi

URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Descargando Piper ${PIPER_VERSION} (aarch64)..."
curl -fsSL "$URL" -o "$TMP/piper.tar.gz"
tar -xzf "$TMP/piper.tar.gz" -C "$TMP"
SRC="$TMP/piper"

if [[ ! -x "$SRC/piper" ]]; then
  echo "ERROR: no se encontró piper en el tarball."
  exit 1
fi

if [[ -x "$PIPER_BIN" ]] && file "$PIPER_BIN" | grep -qv "aarch64"; then
  mv "$PIPER_BIN" "${PIPER_BIN}.x86_64.bak" 2>/dev/null || true
fi

cp "$SRC/piper" "$PIPER_BIN"
chmod +x "$PIPER_BIN"
cp -f "$SRC"/lib*.so* "$PIPER_DIR/" 2>/dev/null || true
cp -f "$SRC"/lib*.so.* "$PIPER_DIR/" 2>/dev/null || true
# espeak-ng del tarball (aarch64)
if [[ -x "$SRC/espeak-ng" ]]; then
  cp -f "$SRC/espeak-ng" "$PIPER_DIR/espeak-ng" 2>/dev/null || true
  chmod +x "$PIPER_DIR/espeak-ng" 2>/dev/null || true
fi

echo "==> Piper listo: $(file "$PIPER_BIN")"
echo "    Prueba: ./scripts/test-audio-standalone.sh"
