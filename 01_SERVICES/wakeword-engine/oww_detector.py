"""
Wakeword «udito» con openWakeWord (Jetson / Linux).
Sin TFLite micro_model — ese camino era solo para Windows.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger("wakeword.oww")

BACKEND = "openwakeword"
SAMPLE_RATE = 16000
CHUNK_MS = 80
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)  # 1280
CHUNK_SEC = CHUNK_MS / 1000.0
BLOCK_DURATION = CHUNK_SEC
THRESHOLD_VOICE = 0.0002

_ENGINE_DIR = Path(__file__).resolve().parent
_MODELS_DIR = _ENGINE_DIR / "models" / "openwakeword"
_OWW_JSON = _ENGINE_DIR / "config" / "wake_word.json"


def _find_udito_model() -> Path:
    env_path = os.getenv("ROBITA_WAKEWORD_MODEL", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    if _OWW_JSON.is_file():
        try:
            rel = json.loads(_OWW_JSON.read_text(encoding="utf-8")).get("model_path", "")
            if rel:
                p = (_ENGINE_DIR / rel).resolve()
                if p.is_file():
                    return p
        except Exception:
            pass

    search_dirs = [
        _ENGINE_DIR / "models",
        _ENGINE_DIR,
    ]
    patterns = (
        "udito*.onnx", "udito*.tflite", "udito_model.*", "*udito*.onnx",
        "micro_model.tflite",  # único wakeword en GitHub (TFLite, legado)
    )
    for d in search_dirs:
        if not d.is_dir():
            continue
        for pat in patterns:
            for p in sorted(d.glob(pat)):
                if p.is_file() and p.stat().st_size > 10_000:
                    return p
    raise FileNotFoundError(
        "No hay modelo openWakeWord «udito». Coloca udito.onnx en:\n"
        f"  {_ENGINE_DIR / 'models' / 'udito.onnx'}\n"
        "o define ROBITA_WAKEWORD_MODEL=/ruta/al/modelo.onnx\n"
        "Ejecuta: ./scripts/setup-wakeword-oww.sh"
    )


def ensure_openwakeword_base_models() -> Path:
    """Descarga melspectrogram + embedding (ONNX) si faltan."""
    from openwakeword.utils import download_models

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    need = (
        not (_MODELS_DIR / "melspectrogram.onnx").is_file()
        or not (_MODELS_DIR / "embedding_model.onnx").is_file()
    )
    if need:
        logger.info("Descargando modelos base openWakeWord (ONNX)…")
        download_models(model_names=[], target_directory=str(_MODELS_DIR))
    return _MODELS_DIR


class OpenWakeWordEngine:
    """Motor wakeword para robot_common / udito_standalone."""

    BACKEND = BACKEND
    SAMPLE_RATE = SAMPLE_RATE
    CHUNK_SAMPLES = CHUNK_SAMPLES
    CHUNK_SEC = CHUNK_SEC
    BLOCK_DURATION = BLOCK_DURATION
    THRESHOLD_VOICE = THRESHOLD_VOICE

    def __init__(self) -> None:
        self._model = None
        self._model_key = "udito"
        self._udito_path: Path | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        from openwakeword import Model

        base = ensure_openwakeword_base_models()
        self._udito_path = _find_udito_model()
        framework = "onnx" if self._udito_path.suffix == ".onnx" else "onnx"
        if self._udito_path.suffix == ".tflite":
            framework = "tflite"

        logger.info("openWakeWord: modelo udito=%s (framework=%s)", self._udito_path.name, framework)
        self._model = Model(
            wakeword_models=[str(self._udito_path)],
            inference_framework=framework,
            melspec_model_path=str(base / "melspectrogram.onnx"),
            embedding_model_path=str(base / "embedding_model.onnx"),
            vad_threshold=float(os.getenv("ROBITA_OWW_VAD_THRESHOLD", "0.5")),
        )
        self._model_key = self._udito_path.stem.replace(".tflite", "").replace(".onnx", "")
        for key in self._model.models:
            self._model_key = key
            break
        logger.info("openWakeWord listo (clave predicción: %s)", self._model_key)

    def _score(self, audio: np.ndarray) -> float:
        self.load()
        assert self._model is not None
        x = np.asarray(audio, dtype=np.float32).reshape(-1)
        preds = self._model.predict(x)
        if isinstance(preds, dict):
            if self._model_key in preds:
                return float(preds[self._model_key])
            for name in ("udito", "UDITO"):
                if name in preds:
                    return float(preds[name])
            for k, v in preds.items():
                if "udito" in k.lower():
                    return float(v)
            if len(preds) == 1:
                return float(next(iter(preds.values())))
        return 0.0

    def run_inference(self, block_audio: np.ndarray) -> float:
        return self._score(block_audio)

    def run_inference_scores(self, block_audio: np.ndarray) -> tuple[float, float]:
        p = self._score(block_audio)
        return p, max(0.0, 1.0 - p)


# Instancia única (compatibilidad con «import Detector_wakeword as ww»)
_engine = OpenWakeWordEngine()


def load() -> None:
    _engine.load()


def run_inference(block_audio: np.ndarray) -> float:
    return _engine.run_inference(block_audio)


def run_inference_scores(block_audio: np.ndarray) -> tuple[float, float]:
    return _engine.run_inference_scores(block_audio)
