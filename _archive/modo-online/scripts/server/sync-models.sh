#!/usr/bin/env bash
# Copia cachés de modelos y documentos desde el servidor del laboratorio (rsync).
# Uso: ROBITA_SERVER_HOST=192.168.1.100 ROBITA_SERVER_USER=udito ./scripts/server/sync-models.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${ROBITA_SERVER_HOST:-}"
USER="${ROBITA_SERVER_USER:-$USER}"
REMOTE_ROOT="${ROBITA_SERVER_PATH:-/opt/robita-lab}"

if [[ -z "$HOST" ]]; then
  echo "Define la IP del servidor:"
  echo "  export ROBITA_SERVER_HOST=192.168.x.x"
  echo "  export ROBITA_SERVER_USER=usuario   # opcional"
  echo "  $0"
  exit 1
fi

REMOTE="${USER}@${HOST}:${REMOTE_ROOT}"
mkdir -p "$ROOT/data/huggingface" "$ROOT/04_KNOWLEDGE_CORE/raw-docs"

echo "==> Sincronizando desde $REMOTE"
echo "    (pedirá contraseña SSH o usa clave configurada)"

rsync -avz --progress "${REMOTE}/data/huggingface/" "$ROOT/data/huggingface/" 2>/dev/null \
  || rsync -avz --progress "${USER}@${HOST}:~/.cache/huggingface/" "$ROOT/data/huggingface/"

rsync -avz --progress "${REMOTE}/01_SERVICES/rag-engine/data/rag_cache/" \
  "$ROOT/01_SERVICES/rag-engine/data/rag_cache/" 2>/dev/null || true

rsync -avz --progress "${REMOTE}/04_KNOWLEDGE_CORE/raw-docs/" \
  "$ROOT/04_KNOWLEDGE_CORE/raw-docs/"

rsync -avz --progress "${REMOTE}/01_SERVICES/wakeword-engine/models/" \
  "$ROOT/01_SERVICES/wakeword-engine/models/" 2>/dev/null || true

echo ""
echo "Listo. Comprueba .env (HF_HOME=$ROOT/data/huggingface) y ejecuta:"
echo "  ./scripts/udito/start.sh"
