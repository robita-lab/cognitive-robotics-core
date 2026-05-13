#!/usr/bin/env bash
# UDITO todo en un PC (sin cerebro Docker)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || ./scripts/setup-venv.sh
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
export CUDA_VISIBLE_DEVICES=""
exec .venv/bin/python -u 03_ADAPTERS/robot-udit-physical/udito_standalone.py
