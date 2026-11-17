"""MFCC para speaker_lock (huella de voz). Sin TensorFlow — solo numpy/scipy."""

from __future__ import annotations

import numpy as np
from scipy.fft import rfft
from scipy.signal import get_window


def _mel_filterbank(
    n_mels: int, n_fft: int, sample_rate: int, fmin: float = 0.0, fmax: float | None = None
) -> np.ndarray:
    if fmax is None:
        fmax = sample_rate / 2.0

    def hz_to_mel(hz: float) -> float:
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel: float) -> float:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz = mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sample_rate).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float64)
    for i in range(n_mels):
        left, center, right = bins[i], bins[i + 1], bins[i + 2]
        if center == left or right == center:
            continue
        for j in range(left, center):
            if 0 <= j < fb.shape[1]:
                fb[i, j] = (j - left) / max(center - left, 1)
        for j in range(center, right):
            if 0 <= j < fb.shape[1]:
                fb[i, j] = (right - j) / max(right - center, 1)
    return fb.astype(np.float32)


def _dct2(mel_energies: np.ndarray, n_mfcc: int = 13) -> np.ndarray:
    n_frames, n_mels = mel_energies.shape
    k = np.arange(n_mfcc)[:, None]
    n = np.arange(n_mels)[None, :]
    basis = np.cos(np.pi * k * (2 * n + 1) / (2 * n_mels))
    return (mel_energies @ basis.T).astype(np.float32)


def compute_mfcc(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """MFCC 13 coefs — mismos parámetros que la versión TensorFlow anterior."""
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    frame_length = int(sample_rate * 0.025)
    frame_step = int(sample_rate * 0.010)
    n_fft = 512
    n_mels = 40
    n_mfcc = 13

    if x.size < frame_length:
        return np.zeros((0, n_mfcc), dtype=np.float32)

    window = get_window("hann", frame_length, fftbins=True).astype(np.float32)
    mel_fb = _mel_filterbank(n_mels, n_fft, sample_rate)

    frames: list[np.ndarray] = []
    for start in range(0, x.size - frame_length + 1, frame_step):
        frame = x[start : start + frame_length] * window
        spec = np.abs(rfft(frame, n=n_fft)) ** 2
        mel = mel_fb @ spec[: mel_fb.shape[1]]
        frames.append(np.log(mel + 1e-6))

    if not frames:
        return np.zeros((0, n_mfcc), dtype=np.float32)

    log_mel = np.stack(frames, axis=0)
    return _dct2(log_mel, n_mfcc=n_mfcc)
