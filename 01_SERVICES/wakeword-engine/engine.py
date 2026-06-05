"""
engine.py — Motor wakeword «udito» (OpenWakeWord + ONNX).

Toda la configuración vive en config/wakeword.json.
Este módulo solo carga el JSON, el modelo y expone inferencia.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("wakeword.engine")

_ENGINE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _ENGINE_DIR / "config" / "wakeword.json"

_config: dict[str, Any] | None = None
_engine: "WakeWordEngine | None" = None


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Lee config/wakeword.json (sin defaults embebidos en código)."""
    global _config
    path = config_path or _CONFIG_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    _config = data
    return data


def _cfg() -> dict[str, Any]:
    if _config is None:
        load_config()
    assert _config is not None
    return _config


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_ENGINE_DIR / p).resolve()


class WakeWordEngine:
    """OpenWakeWord: carga udito.onnx y devuelve probabilidad por bloque de audio."""

    BACKEND = "openwakeword"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._cfg = config or _cfg()
        audio = self._cfg["audio"]
        self.SAMPLE_RATE = int(audio["sample_rate"])
        chunk_ms = int(audio["chunk_ms"])
        self.CHUNK_MS = chunk_ms
        self.CHUNK_SAMPLES = int(self.SAMPLE_RATE * chunk_ms / 1000)
        self.CHUNK_SEC = chunk_ms / 1000.0
        self.BLOCK_DURATION = self.CHUNK_SEC
        self.THRESHOLD_VOICE = float(audio["voice_energy_min"])
        det = self._cfg["detection"]
        self.WAKEWORD_THRESHOLD = float(det["wakeword_threshold"])
        self._model = None
        self._model_key = str(self._cfg.get("wake_word", "udito"))

    def _model_path(self) -> Path:
        rel = self._cfg["model"]["path"]
        p = _resolve(rel)
        if not p.is_file():
            raise FileNotFoundError(
                f"No existe el modelo wakeword: {p}\n"
                "Copia udito.onnx a 01_SERVICES/wakeword-engine/models/udito.onnx"
            )
        return p

    def _base_models_dir(self) -> Path:
        rel = self._cfg["model"]["base_models_dir"]
        return _resolve(rel)

    def ensure_base_models(self) -> Path:
        """Descarga melspectrogram + embedding si faltan."""
        from openwakeword.utils import download_models

        base = self._base_models_dir()
        base.mkdir(parents=True, exist_ok=True)
        need = (
            not (base / "melspectrogram.onnx").is_file()
            or not (base / "embedding_model.onnx").is_file()
        )
        if need:
            logger.info("Descargando modelos base OpenWakeWord…")
            download_models(model_names=[], target_directory=str(base))
        return base

    def load(self) -> None:
        if self._model is not None:
            return
        from openwakeword import Model

        base = self.ensure_base_models()
        model_path = self._model_path()
        framework = self._cfg["model"].get("framework", "onnx")
        if model_path.suffix == ".tflite":
            framework = "tflite"

        logger.info("Cargando wakeword: %s (%s)", model_path.name, framework)
        self._model = Model(
            wakeword_models=[str(model_path)],
            inference_framework=framework,
            melspec_model_path=str(base / "melspectrogram.onnx"),
            embedding_model_path=str(base / "embedding_model.onnx"),
            vad_threshold=float(self._cfg["model"].get("vad_threshold", 0.5)),
        )
        for key in self._model.models:
            self._model_key = key
            break
        logger.info("Wakeword listo (clave: %s)", self._model_key)
        try:
            from ros2_bridge import log_ros2_status

            log_ros2_status()
        except Exception:
            pass

    def _score(self, audio: np.ndarray) -> float:
        self.load()
        assert self._model is not None
        x = np.asarray(audio, dtype=np.float32).reshape(-1)
        preds = self._model.predict(x)
        if not isinstance(preds, dict):
            return 0.0
        if self._model_key in preds:
            return float(preds[self._model_key])
        wake = str(self._cfg.get("wake_word", "udito"))
        for name in (wake, wake.upper(), wake.capitalize()):
            if name in preds:
                return float(preds[name])
        for key, val in preds.items():
            if wake.lower() in key.lower():
                return float(val)
        if len(preds) == 1:
            return float(next(iter(preds.values())))
        return 0.0

    def run_inference(self, block_audio: np.ndarray) -> float:
        return self._score(block_audio)

    def run_inference_scores(self, block_audio: np.ndarray) -> tuple[float, float]:
        p = self._score(block_audio)
        return p, max(0.0, 1.0 - p)


def get_engine() -> WakeWordEngine:
    global _engine
    if _engine is None:
        _engine = WakeWordEngine()
    return _engine


def load() -> None:
    get_engine().load()


def run_inference(block_audio: np.ndarray) -> float:
    return get_engine().run_inference(block_audio)


def run_inference_scores(block_audio: np.ndarray) -> tuple[float, float]:
    return get_engine().run_inference_scores(block_audio)


def export_module_attrs() -> dict[str, Any]:
    """Constantes para robot_common (import Detector_wakeword as ww)."""
    eng = get_engine()
    return {
        "BACKEND": eng.BACKEND,
        "SAMPLE_RATE": eng.SAMPLE_RATE,
        "CHUNK_SAMPLES": eng.CHUNK_SAMPLES,
        "CHUNK_SEC": eng.CHUNK_SEC,
        "BLOCK_DURATION": eng.BLOCK_DURATION,
        "THRESHOLD_VOICE": eng.THRESHOLD_VOICE,
        "WAKEWORD_THRESHOLD": eng.WAKEWORD_THRESHOLD,
    }
