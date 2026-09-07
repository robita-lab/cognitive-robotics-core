#!/usr/bin/env bash
# Variables de entorno para bajo consumo en Jetson (source desde otros scripts).
_ROBITA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export ROBITA_LOW_MEMORY="${ROBITA_LOW_MEMORY:-1}"
export ROBITA_RELEASE_MODELS="${ROBITA_RELEASE_MODELS:-1}"
export WHISPER_MODEL="${WHISPER_MODEL:-tiny}"
export ROBITA_RAG_CONFIG="${ROBITA_RAG_CONFIG:-$_ROBITA_ROOT/01_SERVICES/rag-engine/config/rag_config.jetson.json}"
export HF_HOME="${HF_HOME:-$_ROBITA_ROOT/data/huggingface}"

# cuDNN 8 local (solo si install_onnx_jetson instaló ORT 1.18 sin cuDNN 9 en sistema)
_CUDNN8_LOCAL="$_ROBITA_ROOT/.local-lib/cudnn8-docker"
if [[ -d "$_CUDNN8_LOCAL" && -f "$_CUDNN8_LOCAL/libcudnn.so.8" ]]; then
  export LD_LIBRARY_PATH="$_CUDNN8_LOCAL${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
