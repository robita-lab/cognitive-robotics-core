"""Utilidades compartidas: audio, VAD, wakeword loop (etapa 1 y 2)."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

log = logging.getLogger("robot")

CHUNK_SEC = 0.1

ROOT = Path(__file__).resolve().parents[2]


def _parse_audio_device(env_key: str) -> int | str | None:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def audio_input_device() -> int | str | None:
    return _parse_audio_device("ROBITA_AUDIO_INPUT")


def audio_output_alsa() -> str | None:
    return os.getenv("ROBITA_AUDIO_OUTPUT", "").strip() or None


def verbose_progress() -> bool:
    return os.getenv("ROBITA_VERBOSE", "1").strip().lower() not in ("0", "false", "no", "off")


def progress(msg: str, *, end: str = "\n") -> None:
    if verbose_progress():
        print(msg, flush=True, end=end)


SERVICES = ROOT / "01_SERVICES"
WW_CONFIG = SERVICES / "wakeword-engine" / "config" / "wake_word_config.json"

WAKEWORD_ONLY = re.compile(
    r"^(udito|uito|udito\.|hola udito|oye udito|hey udito|udíto)[\s\.\?\!]*$",
    re.IGNORECASE,
)


def setup_wakeword_path() -> None:
    p = str(SERVICES / "wakeword-engine")
    if p not in __import__("sys").path:
        __import__("sys").path.insert(0, p)


def load_detection_cfg() -> dict:
    defaults = {
        "wakeword_threshold": 0.49,
        "hits_required": 2,
        "cool_down_sec": 2.0,
        "voice_margin": 2.0,
        "calibrate_secs": 2.5,
        "speech_margin": 3.5,
        "silence_after_speech_sec": 1.2,
        "max_record_sec": 8.0,
        "min_speech_sec": 0.7,
        "min_question_chars": 8,
    }
    try:
        with open(WW_CONFIG, encoding="utf-8") as f:
            det = json.load(f).get("detection", {})
        for k in defaults:
            if k in det:
                defaults[k] = det[k]
    except Exception:
        pass
    return defaults


def block_rms(block: np.ndarray) -> float:
    b = block.astype(np.float64).reshape(-1)
    if b.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(b * b)))


def calibrate_noise_floor(sample_rate: int, seconds: float) -> float:
    print(f"Calibrando ruido ambiente ({seconds:.0f}s en silencio)...")
    dev = audio_input_device()
    kwargs: dict = {"samplerate": sample_rate, "channels": 1, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
        print(f"   micrófono: {dev}")
    audio = sd.rec(int(seconds * sample_rate), **kwargs)
    sd.wait()
    floor = max(block_rms(audio), 1e-5)
    print(f"   nivel ambiente RMS={floor:.5f}")
    return floor


def drain_queue(audio_q: queue.Queue, seconds: float = 0.6) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            audio_q.get_nowait()
        except queue.Empty:
            time.sleep(0.03)


def save_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    audio = np.clip(audio.reshape(-1), -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def play_wav_file(path: str) -> bool:
    """Reproduce WAV. Devuelve True si algún dispositivo funcionó."""
    primary = audio_output_alsa()
    devices: list[str | None] = []
    if primary:
        devices.append(primary)
    for dev in ("default", "plughw:0,0", "plughw:3,0"):
        if dev not in devices:
            devices.append(dev)
    devices.append(None)  # aplay sin -D

    for dev in devices:
        cmd = ["aplay", "-q", path] if dev is None else ["aplay", "-q", "-D", dev, path]
        try:
            if subprocess.run(["which", "aplay"], capture_output=True).returncode != 0:
                break
            subprocess.run(cmd, check=True, capture_output=True)
            label = dev or "aplay (predeterminado)"
            log.info("Audio reproducido en: %s", label)
            if verbose_progress():
                progress(f"[audio] reproducido en: {label}")
            return True
        except subprocess.CalledProcessError as e:
            log.debug("aplay falló en %s: %s", dev, e.stderr)
            continue

    for cmd in (["paplay", path],):
        try:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.run(cmd, check=True)
                progress("[audio] reproducido vía paplay")
                return True
        except subprocess.CalledProcessError:
            continue
    return False


def play_wav_bytes(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        if not play_wav_file(path):
            progress("[audio] ERROR — no se oyó nada. Ejecuta: ./scripts/test-audio.sh")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def is_real_question(text: str, cfg: dict) -> bool:
    t = text.strip()
    if len(t) < int(cfg["min_question_chars"]):
        return False
    if WAKEWORD_ONLY.match(t):
        return False
    cleaned = re.sub(r"^(udito|uito)[\s,\.\-]*", "", t, flags=re.IGNORECASE).strip()
    if len(cleaned) < int(cfg["min_question_chars"]):
        return False
    return not WAKEWORD_ONLY.match(cleaned)


def record_question_vad(
    audio_q: queue.Queue,
    noise_floor: float,
    cfg: dict,
    sample_rate: int,
    chunk_samples: int,
    threshold_voice: float,
) -> np.ndarray:
    speech_thresh = max(threshold_voice * 2.5, noise_floor * cfg["speech_margin"])
    silence_thresh = max(noise_floor * 2.5, speech_thresh * 0.4)
    max_sec = float(cfg["max_record_sec"])
    min_speech_chunks = max(1, int(cfg["min_speech_sec"] / CHUNK_SEC))
    silence_chunks_needed = max(1, int(cfg["silence_after_speech_sec"] / CHUNK_SEC))
    parts: list[np.ndarray] = []
    speech_started = False
    speech_chunks = 0
    silence_chunks = 0
    deadline = time.time() + max_sec
    progress("[graba] di tu pregunta…")
    started_at = time.time()
    last_tick = started_at
    while time.time() < deadline:
        now = time.time()
        if verbose_progress() and now - last_tick >= 1.0:
            progress(f"   … grabando ({now - started_at:.0f}s / {max_sec:.0f}s)", end="\r")
            last_tick = now
        try:
            data = audio_q.get(timeout=0.25)
        except queue.Empty:
            if speech_started and speech_chunks >= min_speech_chunks and silence_chunks >= silence_chunks_needed:
                break
            continue
        data = data.reshape(-1)
        for start in range(0, len(data), chunk_samples):
            chunk = data[start : start + chunk_samples]
            if chunk.size < chunk_samples // 2:
                continue
            r = block_rms(chunk)
            if r >= speech_thresh:
                speech_started = True
                speech_chunks += 1
                silence_chunks = 0
                parts.append(chunk.astype(np.float32))
            elif speech_started:
                parts.append(chunk.astype(np.float32))
                silence_chunks += 1 if r < silence_thresh else 0
                if speech_chunks >= min_speech_chunks and silence_chunks >= silence_chunks_needed:
                    progress(f"   audio OK ({speech_chunks} tramos de voz)          ")
                    return np.concatenate(parts) if parts else np.array([], dtype=np.float32)
    if parts:
        progress(f"   fin grabación ({len(parts)} tramos)          ")
    else:
        progress("   sin voz en la grabación          ")
    return np.concatenate(parts) if parts else np.array([], dtype=np.float32)


def audio_has_speech(
    audio: np.ndarray,
    noise_floor: float,
    margin: float,
    sample_rate: int,
    chunk_samples: int,
    threshold_voice: float,
) -> bool:
    if audio.size < sample_rate * 0.25:
        return False
    thresh = max(threshold_voice * 2.0, noise_floor * margin * 0.6)
    peak = block_rms(audio)
    if peak >= thresh:
        return True
    chunks = voiced = 0
    for start in range(0, len(audio), chunk_samples):
        chunk = audio[start : start + chunk_samples]
        if chunk.size < chunk_samples // 2:
            continue
        chunks += 1
        if block_rms(chunk) >= thresh:
            voiced += 1
    return chunks > 0 and voiced >= 1


def run_voice_assistant(
    ww,
    cfg: dict,
    noise_floor: float,
    sample_rate: int,
    chunk_samples: int,
    on_session: Callable[[queue.Queue], None],
    greet: Callable[[], None],
) -> None:
    """Micrófono siempre abierto. Solo reacciona al wakeword; luego saludo → sesión → escucha."""
    hi = float(cfg["wakeword_threshold"])
    lo = max(0.0, hi - 0.10)
    hits_needed = int(cfg["hits_required"])
    cool_down = float(cfg["cool_down_sec"])

    audio_q: queue.Queue = queue.Queue(maxsize=200)
    buffer = np.zeros(0, dtype=np.float32)
    block_samples = int(sample_rate * ww.BLOCK_DURATION)
    hop_samples = max(1, int(block_samples * 0.5))
    consecutive_hits = 0
    last_trigger = 0.0
    session_active = False
    last_heartbeat = time.time()
    last_prob_shown = 0.0

    def callback(indata, frames, ctime, status):
        if status:
            log.warning("Audio: %s", status)
        try:
            audio_q.put_nowait(indata.copy().reshape(-1))
        except queue.Full:
            pass

    stream_kwargs: dict = {
        "samplerate": sample_rate,
        "channels": 1,
        "dtype": "float32",
        "blocksize": chunk_samples,
        "callback": callback,
    }
    mic = audio_input_device()
    if mic is not None:
        stream_kwargs["device"] = mic
        log.info("Micrófono: %s", mic)

    progress("")
    progress("=" * 52)
    progress("  LISTO — di «udito» para activar el asistente")
    progress("=" * 52)
    progress("")

    with sd.InputStream(**stream_kwargs):
        while True:
            try:
                data = audio_q.get(timeout=0.5)
            except queue.Empty:
                if verbose_progress() and time.time() - last_heartbeat >= 10.0:
                    progress("[escucha] LISTO — esperando «udito»…")
                    last_heartbeat = time.time()
                continue

            buffer = np.concatenate([buffer, data])
            while buffer.size >= block_samples and not session_active:
                block = buffer[:block_samples]
                buffer = buffer[hop_samples:]

                if block_rms(block) < ww.THRESHOLD_VOICE:
                    consecutive_hits = max(0, consecutive_hits - 1)
                    continue

                prob = ww.run_inference(block)
                if verbose_progress() and prob > 0.20 and (time.time() - last_prob_shown) > 0.4:
                    progress(
                        f"[voz] udito={prob:.2f}  (activa con ≥{hi:.2f}, "
                        f"paso {consecutive_hits}/{hits_needed})",
                        end="\r",
                    )
                    last_prob_shown = time.time()
                    last_heartbeat = time.time()

                if prob >= hi:
                    consecutive_hits += 1
                elif prob <= lo:
                    consecutive_hits = 0

                if consecutive_hits < hits_needed:
                    continue
                if (time.time() - last_trigger) <= cool_down:
                    consecutive_hits = 0
                    continue

                last_trigger = time.time()
                consecutive_hits = 0
                buffer = np.zeros(0, dtype=np.float32)
                session_active = True

                progress(f"\n[wake] udito detectado (prob={prob:.2f})")
                drain_queue(audio_q, 0.5)

                progress("[saludo] TTS local (Piper)…")
                greet()
                drain_queue(audio_q, 0.6)
                time.sleep(0.35)

                progress("[sesión] grabación → STT → RAG → TTS")
                try:
                    on_session(audio_q)
                finally:
                    drain_queue(audio_q, 0.5)
                    buffer = np.zeros(0, dtype=np.float32)
                    session_active = False
                    progress("")
                    progress("=" * 52)
                    progress("  LISTO — di «udito» para activar el asistente")
                    progress("=" * 52)
                    progress("")


# compatibilidad etapa 1 / scripts antiguos
def run_wakeword_loop(
    ww,
    cfg: dict,
    noise_floor: float,
    sample_rate: int,
    chunk_samples: int,
    on_wake: Callable[[queue.Queue], None],
    speak_prompt: Callable[[str], None],
    prompt_text: str = "¿En qué te puedo ayudar?",
) -> None:
    run_voice_assistant(
        ww, cfg, noise_floor, sample_rate, chunk_samples,
        on_session=on_wake,
        greet=lambda: speak_prompt(prompt_text),
    )
