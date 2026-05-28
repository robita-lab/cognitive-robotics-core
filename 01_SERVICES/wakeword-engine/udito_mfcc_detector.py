"""
Wakeword «udito» — modelo UDITO (dguevaras/UDITO).
Fuente: https://github.com/dguevaras/UDITO/tree/master/WakeWord-project
  wakeword_model.h5 → convertido a udito_from_h5.tflite

No es openWakeWord: CNN + MFCC propia. En Jetson usa tensorflow.lite (no tflite_runtime).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import tensorflow as tf

logger = logging.getLogger("wakeword.udito_mfcc")

BACKEND = "udito_mfcc"
SAMPLE_RATE = 16000
BLOCK_DURATION = 1.0
CHUNK_SEC = 0.1
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)
THRESHOLD_VOICE = 0.0002

_ENGINE_DIR = Path(__file__).resolve().parent
_MODELS = _ENGINE_DIR / "models"
_TFLITE = _MODELS / "udito_from_h5.tflite"
_H5 = _MODELS / "wakeword_model.h5"

_interpreter = None
_input_details = None
_output_details = None


def _model_path() -> Path:
    if os.getenv("ROBITA_WAKEWORD_MODEL", "").strip():
        p = Path(os.getenv("ROBITA_WAKEWORD_MODEL"))
        if p.is_file():
            return p
    if _TFLITE.is_file():
        return _TFLITE
    raise FileNotFoundError(
        f"Falta {_TFLITE}. Ejecuta: ./scripts/fetch-wakeword-udito-repo.sh"
    )


def ensure_model() -> Path:
    _MODELS.mkdir(parents=True, exist_ok=True)
    tflite = _model_path()
    if tflite.is_file() and tflite.stat().st_size > 10_000:
        return tflite
    if not _H5.is_file():
        raise FileNotFoundError(f"Falta {_H5}; ejecuta ./scripts/fetch-wakeword-udito-repo.sh")
    logger.info("Convirtiendo wakeword_model.h5 → TFLite…")
    model = tf.keras.models.load_model(str(_H5))
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    data = conv.convert()
    out = _TFLITE
    out.write_bytes(data)
    logger.info("TFLite guardado: %s (%d bytes)", out, len(data))
    return out


def _ensure_interpreter():
    global _interpreter, _input_details, _output_details
    if _interpreter is not None:
        return _interpreter
    path = ensure_model()
    logger.info("Wakeword UDITO MFCC: %s (tensorflow.lite)", path.name)
    _interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=1)
    _interpreter.allocate_tensors()
    _input_details = _interpreter.get_input_details()
    _output_details = _interpreter.get_output_details()
    return _interpreter


def compute_mfcc(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    audio_t = tf.convert_to_tensor(audio.astype(np.float32))
    frame_length = int(sample_rate * 0.025)
    frame_step = int(sample_rate * 0.010)
    stft = tf.signal.stft(
        audio_t, frame_length=frame_length, frame_step=frame_step,
        fft_length=512, window_fn=tf.signal.hann_window,
    )
    spectrogram = tf.abs(stft)
    n_bins = spectrogram.shape[-1]
    mel_w = tf.signal.linear_to_mel_weight_matrix(
        num_mel_bins=40, num_spectrogram_bins=n_bins, sample_rate=sample_rate,
    )
    mel = tf.tensordot(spectrogram, mel_w, 1)
    mel.set_shape(spectrogram.shape[:-1].concatenate(mel_w.shape[-1:]))
    log_mel = tf.math.log(mel + 1e-6)
    mfcc = tf.signal.mfccs_from_log_mel_spectrograms(log_mel)[..., :13]
    return mfcc.numpy()


def _prepare_input(mfcc_frames: np.ndarray) -> np.ndarray:
    """Entrada modelo: (1, 13, 100, 1)."""
    if mfcc_frames.ndim != 2:
        mfcc_frames = np.reshape(mfcc_frames, (-1, mfcc_frames.shape[-1]))
    feat = mfcc_frames.T  # (13, time)
    h, w = 13, 100
    if feat.shape[1] > w:
        feat = feat[:, :w]
    elif feat.shape[1] < w:
        feat = np.pad(feat, ((0, 0), (0, w - feat.shape[1])))
    if feat.shape[0] != h:
        feat = feat[:h, :] if feat.shape[0] > h else np.pad(feat, ((0, h - feat.shape[0]), (0, 0)))
    feat = feat[..., np.newaxis]
    return np.expand_dims(feat, 0).astype(np.float32)


def run_inference(block_audio: np.ndarray) -> float:
    p, _ = run_inference_scores(block_audio)
    return p


def run_inference_scores(block_audio: np.ndarray) -> tuple[float, float]:
    interp = _ensure_interpreter()
    x_raw = np.clip(block_audio.astype(np.float32), -1.0, 1.0)
    x = x_raw - np.mean(x_raw)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-8
    x = x / rms
    x_pre = np.append(x[0], x[1:] - 0.97 * x[:-1])
    mfcc = compute_mfcc(x_pre)
    inp = _prepare_input(mfcc)
    interp.set_tensor(_input_details[0]["index"], inp)
    interp.invoke()
    out = interp.get_tensor(_output_details[0]["index"]).astype(np.float32).ravel()
    if out.size == 1:
        val = float(out[0])
        if val < 0.0 or val > 1.0:
            val = 1.0 / (1.0 + np.exp(-val))
        return float(np.clip(val, 0.0, 1.0)), 1.0 - float(np.clip(val, 0.0, 1.0))
    if out.size == 2:
        e = np.exp(out - np.max(out))
        sm = e / np.sum(e)
        return float(sm[1]), float(sm[0])
    return float(np.max(out)), 0.0


def load() -> None:
    _ensure_interpreter()
