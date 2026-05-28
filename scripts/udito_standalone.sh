#!/usr/bin/env bash
# UDITO todo en un PC (sin cerebro Docker)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || ./scripts/setup-jetson-offline.sh
# shellcheck source=/dev/null
[[ -f scripts/jetson-env.sh ]] && source scripts/jetson-env.sh
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
export HF_HOME="${HF_HOME:-$ROOT/data/huggingface}"
export ROBITA_RAG_CONFIG="${ROBITA_RAG_CONFIG:-$ROOT/01_SERVICES/rag-engine/config/rag_config.jetson.json}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
exec .venv/bin/python -u 03_ADAPTERS/robot-udit-physical/udito_standalone.py
