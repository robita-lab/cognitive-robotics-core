"""
engine.py — Motor wakeword «udito» (OpenWakeWord + ONNX).

Toda la configuración vive en config/wakeword.json.
Este módulo solo carga el JSON, el modelo y expone inferencia.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("wakeword.engine")

_ENGINE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _ENGINE_DIR / "config" / "wakeword.json"

_config: dict[str, Any] | None = None
_engine: "WakeWordEngine | None" = None
_model_verified = False


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
        env = os.getenv("ROBITA_WAKEWORD_MODEL", "").strip()
        if env:
            p = Path(env) if Path(env).is_absolute() else _resolve(env)
        else:
            p = _resolve(self._cfg["model"]["path"])
        if not p.is_file():
            p = self._download_if_pretrained(p)
        if not p.is_file():
            raise FileNotFoundError(
                f"No existe el modelo wakeword: {p}\n"
                "Copia udito.onnx o usa ROBITA_WAKEWORD_MODEL=.../hey_jarvis_v0.1.onnx"
            )
        return p

    def _download_if_pretrained(self, path: Path) -> Path:
        """Descarga modelos OWW preentrenados (hey_jarvis, alexa, …) si faltan."""
        stem = path.stem
        if "_v0.1" not in stem:
            return path
        name = stem.replace("_v0.1", "")
        try:
            from openwakeword.utils import download_models

            logger.info("Descargando modelo preentrenado «%s»…", name)
            download_models(model_names=[name], target_directory=str(path.parent))
        except Exception as exc:
            logger.warning("No se pudo descargar %s: %s", name, exc)
        return path

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
        if not self._model.models:
            self._model_key = model_path.stem
        logger.info("Wakeword listo (clave: %s)", self._model_key)
        print(
            f"[wakeword] modelo={model_path}  clave={self._model_key}",
            flush=True,
        )
        _verify_loaded_model(self)
        try:
            from ros2_bridge import log_ros2_status

            log_ros2_status()
        except Exception:
            pass

    def _peak_on_audio(self, audio: np.ndarray) -> float:
        assert self._model is not None
        b = self.CHUNK_SAMPLES
        flat = np.asarray(audio, dtype=np.float32).reshape(-1)
        peak = 0.0
        for i in range(0, max(1, flat.size - b + 1), b):
            peak = max(peak, self._score(flat[i : i + b]))
        return peak

    def _pick_score(self, preds: dict[str, float]) -> float:
        """Elige la puntuación correcta (OWW usa el nombre del .onnx, p. ej. hey_jarvis_v0.1)."""
        if not preds:
            return 0.0
        if self._model_key in preds:
            return float(preds[self._model_key])
        stem = self._model_path().stem
        short = stem.replace("_v0.1", "")
        for key, val in preds.items():
            if key == stem or key.startswith(short) or short in key:
                return float(val)
        env_phrase = os.getenv("ROBITA_WAKEWORD", "").strip().replace(" ", "_").lower()
        if env_phrase:
            for key, val in preds.items():
                if env_phrase in key.lower().replace(" ", "_"):
                    return float(val)
        wake = str(self._cfg.get("wake_word", "udito")).replace(" ", "_").lower()
        for key, val in preds.items():
            if wake in key.lower().replace(" ", "_"):
                return float(val)
        if len(preds) == 1:
            return float(next(iter(preds.values())))
        return float(max(preds.values()))


    def _pcm16(self, audio: np.ndarray) -> np.ndarray:
        x = np.asarray(audio, dtype=np.float32).reshape(-1)
        if x.dtype == np.int16:
            return x
        if np.issubdtype(x.dtype, np.floating):
            x = np.clip(x, -1.0, 1.0)
            return (x * 32767.0).astype(np.int16)
        return x.astype(np.int16)

    def _score(self, audio: np.ndarray) -> float:
        self.load()
        assert self._model is not None
        x = self._pcm16(audio)
        preds = self._model.predict(x)
        if not isinstance(preds, dict):
            return 0.0
        return self._pick_score(preds)

    def run_inference(self, block_audio: np.ndarray) -> float:
        return self._score(block_audio)

    def run_inference_scores(self, block_audio: np.ndarray) -> tuple[float, float]:
        p = self._score(block_audio)
        return p, max(0.0, 1.0 - p)


def _verify_loaded_model(eng: WakeWordEngine, min_peak: float = 0.05) -> float:
    """Comprueba carga del modelo (udito roto ~0.0008; OWW muestra claves de predict)."""
    global _model_verified
    if _model_verified:
        return min_peak
    _model_verified = True
    assert eng._model is not None
    b = eng.CHUNK_SAMPLES
    rng = np.random.default_rng(0)
    eng._model.reset()
    warmup = np.zeros(b, dtype=np.float32)
    last_preds: dict = {}
    for _ in range(30):
        last_preds = eng._model.predict(warmup)
    print(f"[wakeword] claves OWW: {list(last_preds.keys())}", flush=True)
    peak = max(
        eng._peak_on_audio(np.zeros(b * 12, dtype=np.float32)),
        eng._peak_on_audio(rng.standard_normal(b * 12).astype(np.float32) * 0.2),
    )
    print(f"[wakeword] auto-test pico={peak:.5f}", flush=True)
    model_name = eng._model_path().name
    if model_name == "udito.onnx" and peak < min_peak:
        msg = (
            f"ERROR: models/udito.onnx no funciona (pico={peak:.4f}). "
            "Entrena uno válido: cd ww2 && python train_udito.py "
            "→ cp ww2/models/udito.onnx 01_SERVICES/wakeword-engine/models/ "
            "Mientras tanto: ROBITA_WAKEWORD_MODEL=.../hey_jarvis_v0.1.onnx en .env"
        )
        logger.error(msg)
        print(msg, file=sys.stderr)
    elif "hey_jarvis" in model_name and peak < 0.001:
        print(
            "[wakeword] AVISO: pico muy bajo con hey_jarvis — "
            "revisa modelos base en models/openwakeword/ (./scripts/setup/wakeword.sh)",
            flush=True,
        )
    return peak


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
