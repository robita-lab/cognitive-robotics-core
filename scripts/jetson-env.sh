#!/usr/bin/env bash
# Variables de entorno para bajo consumo en Jetson (source desde otros scripts).
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export ROBITA_LOW_MEMORY="${ROBITA_LOW_MEMORY:-1}"
export ROBITA_RELEASE_MODELS="${ROBITA_RELEASE_MODELS:-1}"
export WHISPER_MODEL="${WHISPER_MODEL:-tiny}"
export ROBITA_RAG_CONFIG="${ROBITA_RAG_CONFIG:-/opt/robita-lab/01_SERVICES/rag-engine/config/rag_config.jetson.json}"
export HF_HOME="${HF_HOME:-/opt/robita-lab/data/huggingface}"
