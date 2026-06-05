"""Perfil de voz del hablante que activó «udito» — ignora otras voces en la sesión."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import numpy as np

log = logging.getLogger("speaker_lock")

_SERVICES = Path(__file__).resolve().parents[2] / "01_SERVICES" / "wakeword-engine"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))


def _preemph(audio: np.ndarray) -> np.ndarray:
    x = audio.astype(np.float32).reshape(-1)
    if x.size < 8:
        return x
    x = x - np.mean(x)
    rms = float(np.sqrt(np.mean(x ** 2))) + 1e-8
    x = x / rms
    return np.append(x[0], x[1:] - 0.97 * x[:-1]).astype(np.float32)


def voice_embedding(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray | None:
    from voice_features import compute_mfcc

    x = _preemph(audio)
    if x.size < int(sample_rate * 0.25):
        return None
    mfcc = compute_mfcc(x, sample_rate)
    if mfcc.size == 0:
        return None
    return np.concatenate([mfcc.mean(axis=0), mfcc.std(axis=0)]).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    na = np.linalg.norm(a) + 1e-8
    nb = np.linalg.norm(b) + 1e-8
    return float(np.dot(a / na, b / nb))


class SpeakerLock:
    """Huella de voz del activador; compara antes de STT/RAG."""

    def __init__(self, threshold: float | None = None, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold if threshold is not None else float(
            os.getenv("ROBITA_SPEAKER_LOCK_THRESHOLD", "0.78")
        )
        self._profile: np.ndarray | None = None

    @property
    def ready(self) -> bool:
        return self._profile is not None

    def _chunk_embeddings(self, audio: np.ndarray, chunk_sec: float = 0.45) -> list[np.ndarray]:
        x = audio.astype(np.float32).reshape(-1)
        n = max(int(self.sample_rate * chunk_sec), 1)
        out: list[np.ndarray] = []
        for start in range(0, len(x), n):
            part = x[start : start + n]
            if part.size < int(self.sample_rate * 0.25):
                continue
            rms = float(np.sqrt(np.mean(part ** 2)))
            if rms < 0.004:
                continue
            emb = voice_embedding(part, self.sample_rate)
            if emb is not None:
                out.append(emb)
        return out

    def enroll(self, audio: np.ndarray) -> bool:
        embs = self._chunk_embeddings(audio, chunk_sec=0.4)
        if not embs:
            emb = voice_embedding(audio, self.sample_rate)
            if emb is None:
                log.warning("No se pudo crear perfil de hablante (audio muy corto)")
                return False
            self._profile = emb
            return True
        self._profile = np.mean(np.stack(embs, axis=0), axis=0).astype(np.float32)
        return True

    def verify(self, audio: np.ndarray) -> tuple[bool, float]:
        if self._profile is None:
            return True, 1.0
        embs = self._chunk_embeddings(audio, chunk_sec=0.35)
        if not embs:
            emb = voice_embedding(audio, self.sample_rate)
            if emb is None:
                return False, 0.0
            sim = cosine_similarity(self._profile, emb)
            return sim >= self.threshold, sim
        sims = [cosine_similarity(self._profile, e) for e in embs]
        sim = float(max(sims))
        return sim >= self.threshold, sim

    def verify_chunk(self, chunk: np.ndarray) -> tuple[bool, float]:
        if self._profile is None:
            return True, 1.0
        emb = voice_embedding(chunk, self.sample_rate)
        if emb is None:
            return False, 0.0
        sim = cosine_similarity(self._profile, emb)
        return sim >= self.threshold, sim
