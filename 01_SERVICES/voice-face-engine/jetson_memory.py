"""Ajustes de RAM/CPU para Jetson Orin (~8 GB)."""

from __future__ import annotations

import gc
import logging
import os

log = logging.getLogger("jetson_memory")


def apply_low_memory_env() -> None:
    """Variables que reducen picos de RAM y hilos en CPU."""
    defaults = {
        "CUDA_VISIBLE_DEVICES": "",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    }
    for key, val in defaults.items():
        os.environ.setdefault(key, val)
    try:
        import torch
        torch.set_num_threads(1)
    except ImportError:
        pass


def release_ram(label: str = "") -> None:
    gc.collect()
    if label and os.getenv("ROBITA_VERBOSE", "").strip() not in ("0", "false", "no"):
        try:
            import psutil
            mb = psutil.Process().memory_info().rss / (1024 * 1024)
            log.info("RAM tras %s: %.0f MB", label, mb)
        except ImportError:
            pass


def low_memory_mode() -> bool:
    return os.getenv("ROBITA_LOW_MEMORY", "1").strip().lower() not in ("0", "false", "no", "off")


def release_models_after_stt() -> bool:
    return os.getenv("ROBITA_RELEASE_MODELS", "1").strip().lower() not in ("0", "false", "no", "off")
