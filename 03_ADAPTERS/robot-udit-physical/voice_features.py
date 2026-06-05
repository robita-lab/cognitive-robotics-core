"""MFCC para speaker_lock (huella de voz). No es detección de wakeword."""

from __future__ import annotations

import numpy as np
import tensorflow as tf


def compute_mfcc(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    audio_t = tf.convert_to_tensor(audio.astype(np.float32))
    frame_length = int(sample_rate * 0.025)
    frame_step = int(sample_rate * 0.010)
    stft = tf.signal.stft(
        audio_t,
        frame_length=frame_length,
        frame_step=frame_step,
        fft_length=512,
        window_fn=tf.signal.hann_window,
    )
    spectrogram = tf.abs(stft)
    n_bins = spectrogram.shape[-1]
    mel_w = tf.signal.linear_to_mel_weight_matrix(
        num_mel_bins=40,
        num_spectrogram_bins=n_bins,
        sample_rate=sample_rate,
    )
    mel = tf.tensordot(spectrogram, mel_w, 1)
    mel.set_shape(spectrogram.shape[:-1].concatenate(mel_w.shape[-1:]))
    log_mel = tf.math.log(mel + 1e-6)
    mfcc = tf.signal.mfccs_from_log_mel_spectrograms(log_mel)[..., :13]
    return mfcc.numpy()
