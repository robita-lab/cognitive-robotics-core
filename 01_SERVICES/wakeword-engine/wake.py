"""
wake.py — Motor wakeword «udito» (OpenWakeWord + ONNX Runtime CUDA).

Toda la configuración vive en config/wakeword.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("wakeword.wake")

_ENGINE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _ENGINE_DIR / "config" / "wakeword.json"


def _resolve_config_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path if config_path.is_absolute() else (_ENGINE_DIR / config_path).resolve()
    env = os.getenv("ROBITA_WAKEWORD_CONFIG", "").strip()
    if env:
        p = Path(env)
        return p if p.is_absolute() else (_ENGINE_DIR / p).resolve()
    return _CONFIG_PATH

_config: dict[str, Any] | None = None
_engine: "WakeWordEngine | None" = None
_model_verified = False
_ort_patched = False

OWW_CHUNK_SAMPLES = 1280
OWW_SAMPLE_RATE = 16000


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Lee wakeword.json o ROBITA_WAKEWORD_CONFIG (p. ej. config/wakeword.pc.json)."""
    global _config
    path = _resolve_config_path(config_path)
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


def _normalize_float32(audio: np.ndarray) -> np.ndarray:
    """Normaliza entrada a float32 mono en [-1, 1] antes del modelo."""
    x = np.asarray(audio).reshape(-1)
    if x.dtype == np.int16:
        return (x.astype(np.float32) / 32768.0).clip(-1.0, 1.0)
    if np.issubdtype(x.dtype, np.integer):
        peak = float(np.iinfo(x.dtype).max)
        return (x.astype(np.float32) / peak).clip(-1.0, 1.0)
    return x.astype(np.float32).clip(-1.0, 1.0)


def _to_oww_int16(audio_f32: np.ndarray) -> np.ndarray:
    """OpenWakeWord preprocessor espera int16 PCM."""
    return (np.clip(audio_f32, -1.0, 1.0) * 32767.0).astype(np.int16)


def _enable_cuda_devices(provider_pref: str) -> None:
    """UDITO fija CUDA_VISIBLE_DEVICES='' para STT/RAG; el wakeword necesita ver la GPU."""
    if str(provider_pref).lower() not in ("cuda", "gpu"):
        return
    if os.environ.get("CUDA_VISIBLE_DEVICES", None) == "":
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)


def _build_ort_providers(pref: str) -> list[str]:
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    want_cuda = str(pref).lower() in ("cuda", "gpu")
    if want_cuda and "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


_PREPROCESSOR_MARKERS = ("melspectrogram", "embedding_model", "silero_vad")


def _install_ort_provider_patch(pref: str, *, preprocessor_on_cpu: bool) -> list[str]:
    """Parchea InferenceSession: OWW fuerza CPU en modelos custom."""
    global _ort_patched
    import onnxruntime as ort

    desired = _build_ort_providers(pref)
    if _ort_patched:
        return desired

    original = ort.InferenceSession

    class _PatchedInferenceSession(original):  # type: ignore[misc,valid-type]
        def __init__(self, path_or_bytes, sess_options=None, providers=None, **kwargs):
            path_str = (
                path_or_bytes.decode("utf-8", errors="ignore")
                if isinstance(path_or_bytes, (bytes, bytearray))
                else str(path_or_bytes)
            )
            if preprocessor_on_cpu and any(m in path_str for m in _PREPROCESSOR_MARKERS):
                use = ["CPUExecutionProvider"]
            elif providers is None or providers == ["CPUExecutionProvider"]:
                use = desired
            else:
                use = providers
            super().__init__(
                path_or_bytes,
                sess_options=sess_options,
                providers=use,
                **kwargs,
            )

    ort.InferenceSession = _PatchedInferenceSession  # type: ignore[assignment]
    _ort_patched = True
    return desired


class WakeWordEngine:
    """OpenWakeWord: udito.onnx con CUDA, buffer deslizante y umbral configurable."""

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

        det = self._cfg.get("detection", {})
        self.WAKEWORD_THRESHOLD = float(
            self._cfg.get("wake_threshold", det.get("wakeword_threshold", 0.3))
        )
        self._threshold_mode = str(self._cfg.get("wake_threshold_mode", "average")).lower()
        self._buffer_size = max(1, int(self._cfg.get("wake_buffer_size", 3)))
        self._debug_mode = bool(self._cfg.get("wake_debug_mode", False))
        self._provider_pref = str(self._cfg.get("wake_provider", "cuda")).lower()
        self._preprocessor_on_cpu = str(
            self._cfg.get("wake_preprocessor_device", "cpu")
        ).lower() in ("cpu", "")
        self._score_buffer: deque[float] = deque(maxlen=self._buffer_size)
        self._ort_providers: list[str] = []
        self._active_provider = "CPU"
        self._model = None
        self._model_key = str(self._cfg.get("wake_word", "udito"))

        if self.SAMPLE_RATE != OWW_SAMPLE_RATE:
            logger.warning(
                "sample_rate=%s — OpenWakeWord espera %s Hz",
                self.SAMPLE_RATE,
                OWW_SAMPLE_RATE,
            )
        if self.CHUNK_SAMPLES != OWW_CHUNK_SAMPLES:
            raise ValueError(
                f"chunk_samples={self.CHUNK_SAMPLES} — OpenWakeWord requiere "
                f"exactamente {OWW_CHUNK_SAMPLES} samples (80 ms @ 16 kHz). "
                f"Ajusta audio.chunk_ms en wakeword.json."
            )

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
                "Copia udito.onnx o usa ROBITA_WAKEWORD_MODEL=.../udito.onnx"
            )
        return p

    def _download_if_pretrained(self, path: Path) -> Path:
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
        return _resolve(self._cfg["model"]["base_models_dir"])

    def ensure_base_models(self) -> Path:
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

    def _oww_device(self) -> str:
        if self._preprocessor_on_cpu:
            return "cpu"
        return "gpu" if self._provider_pref in ("cuda", "gpu") else "cpu"

    def _refresh_active_provider(self) -> None:
        if self._model is None:
            return
        ww_providers: set[str] = set()
        for sess in self._model.models.values():
            ww_providers.update(sess.get_providers())
        if "CUDAExecutionProvider" in ww_providers:
            self._active_provider = "CUDA"
        else:
            self._active_provider = "CPU"

    def load(self) -> None:
        if self._model is not None:
            return

        _enable_cuda_devices(self._provider_pref)
        self._ort_providers = _install_ort_provider_patch(
            self._provider_pref,
            preprocessor_on_cpu=self._preprocessor_on_cpu,
        )
        from openwakeword import Model

        base = self.ensure_base_models()
        model_path = self._model_path()
        framework = self._cfg["model"].get("framework", "onnx")
        if model_path.suffix == ".tflite":
            framework = "tflite"

        logger.info(
            "Cargando wakeword: %s (%s) providers=%s",
            model_path.name,
            framework,
            self._ort_providers,
        )
        self._model = Model(
            wakeword_models=[str(model_path)],
            inference_framework=framework,
            melspec_model_path=str(base / "melspectrogram.onnx"),
            embedding_model_path=str(base / "embedding_model.onnx"),
            vad_threshold=float(self._cfg["model"].get("vad_threshold", 0)),
            device=self._oww_device(),
        )
        for key in self._model.models:
            self._model_key = key
            break
        if not self._model.models:
            self._model_key = model_path.stem

        self._refresh_active_provider()
        logger.info(
            "Wakeword listo (clave=%s, provider=%s)",
            self._model_key,
            self._active_provider,
        )
        pre_dev = "cpu" if self._preprocessor_on_cpu else self._oww_device()
        print(
            f"[wakeword] modelo={model_path}  clave={self._model_key}  "
            f"provider={self._active_provider}  preprocessor={pre_dev}  "
            f"ort={self._ort_providers}",
            flush=True,
        )
        _verify_loaded_model(self)
        try:
            from ros2_bridge import log_ros2_status

            log_ros2_status()
        except Exception:
            pass

    def active_provider(self) -> str:
        self._refresh_active_provider()
        return self._active_provider

    def _pick_score(self, preds: dict[str, float]) -> float:
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

    def _apply_threshold_mode(self, raw: float) -> float:
        self._score_buffer.append(raw)
        if self._threshold_mode == "single":
            return raw
        if len(self._score_buffer) == 0:
            return raw
        return float(sum(self._score_buffer) / len(self._score_buffer))

    def _raw_score(self, audio_f32: np.ndarray, *, timing: bool = False) -> tuple[float, float]:
        """Inferencia OWW; devuelve (score, latencia_ms)."""
        self.load()
        assert self._model is not None
        x = _to_oww_int16(audio_f32)
        t0 = time.perf_counter()
        if timing:
            preds, _timing = self._model.predict(x, timing=True)
        else:
            preds = self._model.predict(x)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if not isinstance(preds, dict):
            return 0.0, latency_ms
        return self._pick_score(preds), latency_ms

    def _score(self, audio: np.ndarray) -> float:
        audio_f32 = _normalize_float32(audio)
        if audio_f32.size != self.CHUNK_SAMPLES:
            if audio_f32.size < self.CHUNK_SAMPLES:
                pad = np.zeros(self.CHUNK_SAMPLES - audio_f32.size, dtype=np.float32)
                audio_f32 = np.concatenate([audio_f32, pad])
            else:
                audio_f32 = audio_f32[: self.CHUNK_SAMPLES]
        raw, _ = self._raw_score(audio_f32)
        return self._apply_threshold_mode(raw)

    def _peak_on_audio(self, audio: np.ndarray) -> float:
        assert self._model is not None
        b = self.CHUNK_SAMPLES
        flat = _normalize_float32(audio)
        peak = 0.0
        for i in range(0, max(1, flat.size - b + 1), b):
            peak = max(peak, self._score(flat[i : i + b]))
        return peak

    def run_inference(self, block_audio: np.ndarray) -> float:
        return self._score(block_audio)

    def run_inference_scores(self, block_audio: np.ndarray) -> tuple[float, float]:
        p = self._score(block_audio)
        return p, max(0.0, 1.0 - p)

    def run_inference_debug(
        self, block_audio: np.ndarray
    ) -> tuple[float, str, float]:
        """Score + provider + latencia (ms) — para calibración."""
        audio_f32 = _normalize_float32(block_audio)
        if audio_f32.size != self.CHUNK_SAMPLES:
            if audio_f32.size < self.CHUNK_SAMPLES:
                pad = np.zeros(self.CHUNK_SAMPLES - audio_f32.size, dtype=np.float32)
                audio_f32 = np.concatenate([audio_f32, pad])
            else:
                audio_f32 = audio_f32[: self.CHUNK_SAMPLES]
        raw, latency_ms = self._raw_score(audio_f32, timing=False)
        score = self._apply_threshold_mode(raw)
        return score, self.active_provider(), latency_ms


def _load_selftest_wav(path: Path) -> np.ndarray:
    import wave

    with wave.open(str(path), "rb") as wf:
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if wf.getnchannels() > 1:
        raw = raw.reshape(-1, wf.getnchannels())[:, 0]
    return raw.astype(np.float32) / 32768.0


def _verify_loaded_model(eng: WakeWordEngine, min_peak: float = 0.05) -> float:
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
        last_preds = eng._model.predict(_to_oww_int16(warmup))
    print(f"[wakeword] claves OWW: {list(last_preds.keys())}", flush=True)
    noise_peak = eng._peak_on_audio(rng.standard_normal(b * 12).astype(np.float32) * 0.2)
    silence_peak = eng._peak_on_audio(np.zeros(b * 12, dtype=np.float32))
    ambient_peak = max(silence_peak, noise_peak)
    print(f"[wakeword] auto-test silencio/ruido pico={ambient_peak:.5f}", flush=True)

    model_name = eng._model_path().name
    if model_name == "udito.onnx":
        ref = eng._model_path().parent / "udito_selftest.wav"
        if ref.is_file():
            ref_peak = eng._peak_on_audio(_load_selftest_wav(ref))
            print(f"[wakeword] auto-test referencia pico={ref_peak:.5f}", flush=True)
            if ref_peak < 0.35:
                msg = (
                    f"ERROR: models/udito.onnx no detecta la referencia (pico={ref_peak:.4f}). "
                    "Reentrena: cd ww2 && python train_udito.py "
                    "→ cp ww2/models/udito.onnx 01_SERVICES/wakeword-engine/models/"
                )
                logger.error(msg)
                print(msg, file=sys.stderr)
            return ref_peak
        if ambient_peak > 0.5:
            print(
                "[wakeword] AVISO: pico alto en silencio/ruido — posibles falsos positivos",
                flush=True,
            )
        print("[wakeword] modelo udito cargado (sin udito_selftest.wav)", flush=True)
        return ambient_peak
    if "hey_jarvis" in model_name and ambient_peak < 0.001:
        print(
            "[wakeword] AVISO: pico muy bajo con hey_jarvis — "
            "revisa modelos base en models/openwakeword/",
            flush=True,
        )
    return ambient_peak


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


def run_debug_monitor() -> None:
    """
    Modo debug: mic → score/provider/latencia por chunk.
    No activa el pipeline; solo calibrar wake_threshold.
    """
    import queue

    import sounddevice as sd

    eng = get_engine()
    cfg = eng._cfg
    threshold = eng.WAKEWORD_THRESHOLD
    phrase = str(cfg.get("wake_word", "udito"))
    block = eng.CHUNK_SAMPLES
    sr = eng.SAMPLE_RATE
    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, _frames, _time_info, status):
        if status:
            print(f"[debug] audio status: {status}", flush=True)
        q.put(indata.copy())

    eng.load()
    print(
        f"\n=== wake debug monitor ===\n"
        f"Frase: «{phrase}»  threshold={threshold:.3f}  "
        f"mode={eng._threshold_mode}  buffer={eng._buffer_size}\n"
        f"Chunk: {block} samples @ {sr} Hz  provider={eng.active_provider()}\n"
        f"Ctrl+C para salir\n",
        flush=True,
    )

    with sd.InputStream(
        samplerate=sr,
        channels=1,
        dtype="float32",
        blocksize=block,
        callback=callback,
    ):
        while True:
            chunk = q.get()
            mono = np.asarray(chunk, dtype=np.float32).reshape(-1)
            score, provider, latency_ms = eng.run_inference_debug(mono)
            fired = " <<< DISPARA" if score >= threshold else ""
            print(
                f"score={score:.4f}  raw_buf={len(eng._score_buffer)}  "
                f"provider={provider}  {latency_ms:.1f} ms{fired}",
                flush=True,
            )


def main() -> int:
    cfg = load_config()
    if not bool(cfg.get("wake_debug_mode", False)):
        print(
            "wake_debug_mode=false en wakeword.json — "
            "activa wake_debug_mode para usar el monitor.",
            flush=True,
        )
        return 0
    try:
        run_debug_monitor()
    except KeyboardInterrupt:
        print("\n[debug] fin", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
