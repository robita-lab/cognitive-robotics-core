#!/usr/bin/env bash
# Cerebro UDITO virtual (Docker: STT + TTS + RAG + orquestador)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
if ! docker info &>/dev/null; then
  echo "Docker no disponible. Usa: ./scripts/launch.sh (mismo cerebro sin Docker)"
  exit 1
fi
docker compose up -d --build
echo "Cerebro udito_virtual en http://127.0.0.1:8000"
echo "En el robot: export ROBITA_SERVER_URL=http://IP_SERVIDOR:8000 && ./scripts/udito.sh"
