#!/usr/bin/env bash
# Robot físico UDITO → cerebro udito_virtual por red
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || ./scripts/setup-venv.sh
if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${ROBITA_SERVER_URL:=http://127.0.0.1:8000}"
: "${ROBITA_KNOWLEDGE_CORE:=$ROOT/04_KNOWLEDGE_CORE}"
export ROBITA_SERVER_URL ROBITA_KNOWLEDGE_CORE CUDA_VISIBLE_DEVICES="" ROBITA_VERBOSE="${ROBITA_VERBOSE:-1}"
echo "UDITO físico | cerebro: $ROBITA_SERVER_URL"
echo "Conocimiento: $ROBITA_KNOWLEDGE_CORE/responses"
exec .venv/bin/python -u 03_ADAPTERS/robot-udit-physical/udito.py
