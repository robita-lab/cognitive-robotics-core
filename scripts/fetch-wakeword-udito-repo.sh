#!/usr/bin/env bash
# Modelo wakeword desde https://github.com/dguevaras/UDITO/tree/master/WakeWord-project
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/01_SERVICES/wakeword-engine/models"
PY="$ROOT/.venv/bin/python"
mkdir -p "$DEST"
URL="https://github.com/dguevaras/UDITO/raw/master/WakeWord-project/wakeword_model.h5"
echo "==> Descargando wakeword_model.h5 (repo dguevaras/UDITO)…"
curl -fsSL -o "$DEST/wakeword_model.h5" "$URL"
ls -la "$DEST/wakeword_model.h5"
echo "==> Convirtiendo a TFLite para Jetson…"
"$PY" -c "
import sys
sys.path.insert(0, '$ROOT/01_SERVICES/wakeword-engine')
from udito_mfcc_detector import ensure_model
p = ensure_model()
print('OK:', p)
"
echo ""
echo "Listo. Arranca UDITO con: ROBITA_WAKEWORD_BACKEND=udito_mfcc ./scripts/start-udito-visible.sh"
