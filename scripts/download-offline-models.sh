#!/usr/bin/env bash
# Descarga modelos necesarios para UDITO standalone (requiere internet la primera vez).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[[ -x .venv/bin/python ]] || ./scripts/setup-venv.sh

if [[ -f .env ]]; then set -a; source .env; set +a; fi
export HF_HOME="${HF_HOME:-$ROOT/data/huggingface}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
mkdir -p "$HF_HOME"

VENV_PY="$ROOT/.venv/bin/python"

echo "==> HF_HOME=$HF_HOME"
echo "==> Descargando Whisper (faster-whisper, modelo ${WHISPER_MODEL:-small})..."
"$VENV_PY" <<'PY'
import os
from faster_whisper import WhisperModel
m = os.environ.get("WHISPER_MODEL", "small")
WhisperModel(m, device="cpu", compute_type="int8")
print("Whisper OK:", m)
PY

echo "==> Descargando embeddings (sentence-transformers)..."
"$VENV_PY" <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
print("Embeddings OK")
PY

RAG_CFG="${ROBITA_RAG_CONFIG:-$ROOT/01_SERVICES/rag-engine/config/rag_config.jetson.json}"
BACKEND="$("$VENV_PY" -c "import json; print(json.load(open('$RAG_CFG')).get('llm',{}).get('backend','').lower())" 2>/dev/null || echo tinyllama)"
if [[ "$BACKEND" == "none" || "$BACKEND" == "off" || "$BACKEND" == "disabled" ]]; then
  echo "==> TinyLlama omitido (rag_config backend=$BACKEND — ahorro RAM en Jetson)"
else
  echo "==> Descargando TinyLlama (puede tardar varios minutos; ~2 GB RAM al usarlo)..."
  "$VENV_PY" <<'PY'
from transformers import AutoTokenizer, AutoModelForCausalLM
name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
AutoTokenizer.from_pretrained(name, trust_remote_code=True)
AutoModelForCausalLM.from_pretrained(name, trust_remote_code=True, low_cpu_mem_usage=True)
print("TinyLlama OK")
PY
fi

echo "==> Pre-indexando RAG..."
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
"$VENV_PY" <<PY
import os, sys
from pathlib import Path
root = Path("$ROOT")
sys.path.insert(0, str(root / "04_KNOWLEDGE_CORE"))
sys.path.insert(0, str(root / "01_SERVICES" / "rag-engine"))
os.chdir(root / "01_SERVICES" / "rag-engine")
from rag_system import RAGSystem
rag = RAGSystem(config_path="$RAG_CFG", settings_path=str(root / "01_SERVICES/rag-engine/config/settings.json"))
rag.initialize(force_rebuild=True)
print("RAG index OK")
PY

echo ""
echo "Modelos listos. Arranca: ./scripts/Principal-UDITO.sh  (o ./UDITO)"
