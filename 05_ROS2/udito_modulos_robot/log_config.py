"""Nivel de log: ROBITA_VERBOSE=0 → limpio; 1 → detalle (Hugging Face, RAG, etc.)."""

from __future__ import annotations

import logging
import os
import warnings


def verbose_mode() -> bool:
    return os.getenv("ROBITA_VERBOSE", "0").strip().lower() not in ("0", "false", "no", "off")


def apply_log_config() -> None:
    """Silencia librerías ruidosas cuando ROBITA_VERBOSE=0."""
    if verbose_mode():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            force=True,
        )
        return

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    logging.basicConfig(level=logging.WARNING, format="%(message)s", force=True)

    quiet_loggers = (
        "httpx",
        "httpcore",
        "urllib3",
        "huggingface_hub",
        "huggingface_hub.utils._http",
        "transformers",
        "sentence_transformers",
        "faiss",
        "faster_whisper",
        "whisper",
        "piper",
        "PiperTTS",
        "RAGSystem",
        "RAGManager",
        "VectorStore",
        "DocumentProcessor",
        "BasicQAManager",
        "WhisperSTT",
        "udito.standalone",
        "robot",
        "tensorflow",
        "absl",
        "onnxruntime",
    )
    for name in quiet_loggers:
        logging.getLogger(name).setLevel(logging.ERROR)

    warnings.filterwarnings("ignore", category=UserWarning, module="tensorflow")
    warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
