#!/usr/bin/env bash
# Ordena el árbol del proyecto: mueve basura a _archive/historial y limpia cachés Python.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCH="$ROOT/_archive/historial"
DRY="${ROBITA_CLEANUP_DRY:-0}"

_log() { echo "==> $*"; }
_mv() {
  local src="$1" dest="$2"
  [[ -e "$src" ]] || return 0
  mkdir -p "$(dirname "$dest")"
  if [[ "$DRY" == "1" ]]; then
    echo "  [dry-run] mv $src -> $dest"
  else
    if mv -f "$src" "$dest" 2>/dev/null; then
      echo "  movido: $(basename "$src")"
    else
      echo "  omitido (ya archivado o en uso): $(basename "$src")"
    fi
  fi
}

_log "Limpieza de proyecto en $ROOT"
mkdir -p "$ARCH"/{scripts,logs,piper,tts,rag-factory,raw-docs}

# Scripts sustituidos
_mv "$ROOT/scripts/install_in_jetson.sh" "$ARCH/scripts/install_in_jetson.sh"
_mv "$ROOT/scripts/test-audio.sh" "$ARCH/scripts/test-audio.sh"

# Logs viejos (el directorio logs/ queda activo vacío)
mkdir -p "$ROOT/logs"
for f in "$ROOT/logs"/*.log; do
  [[ -f "$f" ]] || continue
  [[ "$(basename "$f")" == "udito-standalone.log" ]] && continue
  _mv "$f" "$ARCH/logs/$(basename "$f")"
done

# Piper x86 en Jetson
_mv "$ROOT/01_SERVICES/tts-engine/piper/piper.x86_64.bak" "$ARCH/piper/piper.x86_64.bak"

# TTS duplicado (el código usa piper_tts_real.py)
if [[ -f "$ROOT/01_SERVICES/tts-engine/piper_tts.py" ]]; then
  _mv "$ROOT/01_SERVICES/tts-engine/piper_tts.py" "$ARCH/tts/piper_tts.py"
fi

# Carpeta vacía legacy
if [[ -d "$ROOT/01_SERVICES/rag-engine/rag-factory" ]]; then
  _mv "$ROOT/01_SERVICES/rag-engine/rag-factory" "$ARCH/rag-factory"
fi

# PDF duplicado
_mv "$ROOT/04_KNOWLEDGE_CORE/raw-docs/NormativaExtincionTitulacionesOficiales (1).pdf" \
  "$ARCH/raw-docs/NormativaExtincionTitulacionesOficiales (1).pdf"

# __pycache__ del código (no .venv)
if [[ "$DRY" != "1" ]]; then
  find "$ROOT" -path "$ROOT/.venv" -prune -o -path "$ROOT/_archive" -prune -o \
    -path "$ROOT/data" -prune -o -type d -name __pycache__ -print0 2>/dev/null \
    | xargs -0 rm -rf 2>/dev/null || true
  _log "Eliminados __pycache__ (excepto .venv y data/)"
fi

_log "Limpieza de proyecto terminada. Archivo en: $ROOT/_archive/"
