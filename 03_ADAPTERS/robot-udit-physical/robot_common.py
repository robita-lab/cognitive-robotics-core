"""Utilidades compartidas: audio, VAD, wakeword loop (etapa 1 y 2)."""

from __future__ import annotations

import json
import logging
import os
import queue
from collections import deque
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Callable, Optional

try:
    from speaker_lock import SpeakerLock
except ImportError:
    SpeakerLock = None  # type: ignore[misc, assignment]

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


_INPUT_NAME_PATTERNS: dict[str, tuple[str, ...]] = {
    "respeaker": ("respeaker", "seeed", "arrayuac", "mic array"),
    "pulse": ("pulse",),
    "default": ("default",),
}


def resolve_audio_input() -> int | str | None:
    """Resuelve micrófono por índice, alias (respeaker/pulse/default) o nombre parcial."""
    raw = os.getenv("ROBITA_AUDIO_INPUT", "").strip()
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw)
        info = sd.query_devices(idx)
        if int(info.get("max_input_channels", 0)) <= 0:
            log.error(
                "ROBITA_AUDIO_INPUT=%s (%s) no tiene entrada de micrófono — usa respeaker o pulse",
                idx,
                info.get("name", "?"),
            )
            return None
        return idx
    key = raw.lower()
    if key in ("pulse", "default"):
        return key
    patterns = _INPUT_NAME_PATTERNS.get(key, (key,))
    for idx, info in enumerate(sd.query_devices()):
        if int(info.get("max_input_channels", 0)) <= 0:
            continue
        name = str(info.get("name", "")).lower()
        if any(p in name for p in patterns):
            log.info("Micrófono resuelto: %s → [%s] %s", raw, idx, info.get("name"))
            return idx
    log.warning("No se encontró micrófono para '%s'; usando predeterminado del sistema", raw)
    return None


def audio_input_device() -> int | str | None:
    return resolve_audio_input()


def input_device_sample_rate(device: int | str | None, fallback: int = 16000) -> int:
    if device is None:
        try:
            return int(sd.query_devices(kind="input").get("default_samplerate", fallback))
        except Exception:
            return fallback
    try:
        if isinstance(device, int):
            info = sd.query_devices(device)
        else:
            info = sd.query_devices(device, kind="input")
        return int(info.get("default_samplerate", fallback))
    except Exception:
        return fallback


def resample_mono(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    if from_rate == to_rate or audio.size == 0:
        return audio.reshape(-1)
    x = audio.reshape(-1).astype(np.float64)
    n_out = max(1, int(round(len(x) * to_rate / float(from_rate))))
    src = np.linspace(0.0, len(x) - 1, num=len(x), dtype=np.float64)
    dst = np.linspace(0.0, len(x) - 1, num=n_out, dtype=np.float64)
    return np.interp(dst, src, x).astype(np.float32)


def audio_output_alsa() -> str | None:
    return os.getenv("ROBITA_AUDIO_OUTPUT", "").strip() or None


# Salidas PulseAudio en esta Jetson (pactl list short sinks)
_PULSE_SINK_ALIASES = {
    "respeaker": "alsa_output.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.analog-stereo",
    "hdmi": "alsa_output.platform-3510000.hda.hdmi-stereo",
    "platform": "alsa_output.platform-sound.analog-stereo",
    "placa": "alsa_output.platform-sound.analog-stereo",
}


def resolve_pulse_sink(output: str) -> str | None:
    """Nombre de sink PulseAudio o None = predeterminado del sistema."""
    explicit = os.getenv("ROBITA_PULSE_SINK", "").strip()
    if explicit:
        return explicit
    key = output.strip().lower()
    if key in _PULSE_SINK_ALIASES:
        return _PULSE_SINK_ALIASES[key]
    if key.startswith("alsa_output."):
        return output.strip()
    return None


def verbose_progress() -> bool:
    return os.getenv("ROBITA_VERBOSE", "0").strip().lower() not in ("0", "false", "no", "off")


def progress(msg: str, *, end: str = "\n", always: bool = False) -> None:
    """always=True: conversación ([wake], [stt], …). False: solo con ROBITA_VERBOSE=1."""
    if always or verbose_progress():
        print(msg, flush=True, end=end)


def user_progress(msg: str, *, end: str = "\n") -> None:
    """Mensajes de conversación visibles aunque ROBITA_VERBOSE=0."""
    progress(msg, end=end, always=True)


def status_line(msg: str, *, end: str = "\n") -> None:
    """Una línea visible aunque ROBITA_VERBOSE=0 (arranque, resumen)."""
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


_playback_until: float = 0.0


def mark_playback_active(seconds: float = 3.0) -> None:
    """Ignorar wakeword mientras suena TTS (evita auto-activación por eco)."""
    global _playback_until
    _playback_until = time.time() + max(0.5, seconds)


def playback_blocks_wakeword() -> bool:
    return time.time() < _playback_until


def wait_for_playback_idle(timeout: float = 10.0) -> None:
    """No grabar hasta que el TTS (p. ej. «¿Dime?») haya terminado."""
    deadline = time.time() + max(0.5, timeout)
    while time.time() < deadline:
        if not playback_blocks_wakeword():
            time.sleep(0.06)
            if not playback_blocks_wakeword():
                return
        time.sleep(0.04)


def load_detection_cfg() -> dict:
    defaults = {
        "wakeword_threshold": 0.52,
        "wakeword_spike_range_min": 0.10,
        "wakeword_peak_min": 0.68,
        "wakeword_margin_min": 0.055,
        "wakeword_rel_spike_min": 0.055,
        "hits_required": 1,
        "prob_smooth_window": 3,
        "cool_down_sec": 2.5,
        "post_playback_cooldown_sec": 2.5,
        "post_greet_drain_sec": 0.25,
        "voice_margin": 1.5,
        "audio_pre_roll_sec": 0.6,
        "speaker_lock_enabled": True,
        "speaker_lock_threshold": 0.74,
        "speaker_lock_min_ratio": 0.45,
        "speaker_enroll_sec": 0.5,
        "listen_onset_timeout_sec": 5.0,
        "min_record_speech_sec": 1.1,
        "min_stt_audio_sec": 0.85,
        "wakeword_class_index": 1,
        "reject_prob_at_or_above": 1.0,
        "calibrate_secs": 2.5,
        "speech_margin": 1.8,
        "silence_after_speech_sec": 0.8,
        "max_record_sec": 7.0,
        "min_speech_sec": 0.5,
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
    floor, _ = calibrate_ambient(None, sample_rate, seconds, {})
    return floor


def calibrate_ambient(ww, sample_rate: int, seconds: float, cfg: dict) -> tuple[float, float]:
    """RMS de ruido + puntuación wakeword típica en ambiente (evita falsos positivos por sesgo del modelo)."""
    if verbose_progress():
        print(f"Calibrando ruido ambiente ({seconds:.0f}s en silencio)...")
    else:
        status_line("Calibrando micrófono…", end="\r")
    dev = audio_input_device()
    kwargs: dict = {"samplerate": sample_rate, "channels": 1, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
        if verbose_progress():
            print(f"   micrófono: {dev}")
    audio = sd.rec(int(seconds * sample_rate), **kwargs)
    sd.wait()
    floor = max(block_rms(audio.reshape(-1)), 1e-5)
    if verbose_progress():
        print(f"   nivel ambiente RMS={floor:.5f}")

    baseline = 0.5
    if ww is not None and hasattr(ww, "run_inference"):
        block_samples = int(sample_rate * float(getattr(ww, "BLOCK_DURATION", 1.0)))
        voice_margin = float(cfg.get("voice_margin", 5.0))
        energy_min = max(float(getattr(ww, "THRESHOLD_VOICE", 1e-4)), floor * voice_margin * 0.35)
        probs: list[float] = []
        flat = audio.reshape(-1).astype(np.float32)
        for start in range(0, max(1, flat.size - block_samples + 1), block_samples // 2):
            block = flat[start : start + block_samples]
            if block.size < block_samples:
                break
            if block_rms(block) >= energy_min:
                probs.append(float(ww.run_inference(block)))
        if probs:
            baseline = float(np.median(probs))
        else:
            baseline = float(ww.run_inference(np.zeros(block_samples, dtype=np.float32)))
        baseline = min(max(baseline, 0.0), 0.88)
        hi_c = float(cfg.get("wakeword_threshold", 0.54))
        if verbose_progress():
            print(
                f"   wakeword baseline={baseline:.2f}  "
                f"activación: Δ≥{float(cfg.get('wakeword_rel_spike_min', 0.055)):.2f} sobre baseline"
            )
        else:
            status_line("Micrófono listo          ")
    elif not verbose_progress():
        status_line("Micrófono listo          ")
    return floor, baseline


def drain_queue(audio_q: queue.Queue, seconds: float = 0.6) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            audio_q.get_nowait()
        except queue.Empty:
            time.sleep(0.03)


def save_wav(path: str, audio: np.ndarray, sample_rate: int, *, target_rate: int = 16000) -> None:
    audio = np.clip(audio.reshape(-1), -1.0, 1.0)
    if sample_rate != target_rate:
        audio = resample_mono(audio, sample_rate, target_rate)
        sample_rate = target_rate
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def _pulse_prepare_sink(sink: str) -> None:
    """Activa sink (HDMI suele estar SUSPENDED) y sube volumen."""
    for cmd in (
        ["pactl", "suspend-sink", sink, "0"],
        ["pactl", "set-sink-volume", sink, "100%"],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    if os.getenv("ROBITA_PULSE_SET_DEFAULT", "1").strip().lower() not in ("0", "false", "no"):
        try:
            subprocess.run(["pactl", "set-default-sink", sink], check=True, capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass


def _play_via_paplay(path: str, sink: str | None = None) -> bool:
    try:
        if subprocess.run(["which", "paplay"], capture_output=True).returncode != 0:
            return False
        cmd = ["paplay", path]
        label = "PulseAudio (predeterminado)"
        if sink:
            _pulse_prepare_sink(sink)
            cmd = ["paplay", "--device", sink, path]
            label = sink
        subprocess.run(cmd, check=True, capture_output=True)
        log.info("Audio reproducido en: %s", label)
        if verbose_progress():
            progress(f"[audio] {label}")
        return True
    except subprocess.CalledProcessError as e:
        log.debug("paplay falló (%s): %s", sink, e.stderr)
        return False


def _wav_duration_sec(path: str) -> float:
    try:
        with wave.open(path, "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 3.5


def _gst_play_media(path: Path, volume: float = 0.85) -> bool:
    """MP3/OGG vía GStreamer + Pulse (mismo criterio que processing_cue)."""
    sink = resolve_pulse_sink(os.getenv("ROBITA_AUDIO_OUTPUT", ""))
    loc = str(path.resolve())
    cmd = [
        "gst-launch-1.0", "-q",
        "filesrc", f"location={loc}",
        "!", "decodebin",
        "!", "audioconvert",
        "!", "volume", f"volume={volume}",
        "!", "pulsesink",
    ]
    if sink:
        cmd.extend(["device", sink])
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        log.info("Audio reproducido (gst): %s", path.name)
        if verbose_progress():
            progress(f"[audio] {path.name}")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        log.debug("gst play falló: %s", e)
        return False


def play_media_file(path: str, *, playback_guard_sec: float | None = None) -> bool:
    """WAV (aplay/paplay) o MP3/OGG (GStreamer)."""
    p = Path(path)
    if not p.is_file():
        return False
    guard = playback_guard_sec if playback_guard_sec is not None else 2.0
    mark_playback_active(guard)
    if p.suffix.lower() == ".wav":
        return play_wav_file(str(p), playback_guard_sec=guard)
    if p.suffix.lower() in (".mp3", ".ogg", ".opus"):
        ok = _gst_play_media(p)
        if ok:
            mark_playback_active(guard)
        return ok
    return play_wav_file(str(p), playback_guard_sec=guard)


def play_wav_file(path: str, *, playback_guard_sec: float | None = None) -> bool:
    """Reproduce WAV. Devuelve True si algún dispositivo funcionó."""
    guard = playback_guard_sec if playback_guard_sec is not None else _wav_duration_sec(path) + 1.0
    mark_playback_active(guard)
    raw = audio_output_alsa() or ""
    primary = raw.strip().lower()
    pulse_sink = resolve_pulse_sink(raw)

    # ALSA directo (plughw:0,0 = jack USB ReSpeaker)
    if primary.startswith(("plughw:", "hw:", "default")):
        for dev in (raw.strip(), "plughw:0,0", "plughw:1,3", "default"):
            cmd = ["aplay", "-q", "-D", dev, path]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                log.info("Audio reproducido en: %s", dev)
                if verbose_progress():
                    progress(f"[audio] {dev}")
                mark_playback_active(guard)
                return True
            except subprocess.CalledProcessError:
                continue

    # Pulse: respeaker | hdmi | platform | pulse | nombre alsa_output.*
    if pulse_sink or primary in ("", "pulse", "paplay", "default"):
        if _play_via_paplay(path, pulse_sink):
            mark_playback_active(guard)
            return True

    for dev in ("plughw:0,0", "plughw:1,3"):
        try:
            subprocess.run(["aplay", "-q", "-D", dev, path], check=True, capture_output=True)
            if verbose_progress():
                progress(f"[audio] {dev}")
            mark_playback_active(guard)
            return True
        except subprocess.CalledProcessError:
            continue
    ok = _play_via_paplay(path, None)
    if ok:
        mark_playback_active(guard)
    return ok


def play_wav_bytes(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        if not play_wav_file(path):
            progress("[audio] ERROR — no se oyó nada. Ejecuta: ./scripts/test-audio-standalone.sh")
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


class AudioPreRoll:
    """Últimos N segundos de micrófono (no perder el inicio de la pregunta)."""

    def __init__(self, sample_rate: int, seconds: float) -> None:
        self._max = max(int(sample_rate * seconds), 1)
        self._buf = np.zeros(0, dtype=np.float32)

    def push(self, chunk: np.ndarray) -> None:
        x = chunk.reshape(-1).astype(np.float32)
        self._buf = (
            x if self._buf.size == 0 else np.concatenate([self._buf, x])
        )
        if self._buf.size > self._max:
            self._buf = self._buf[-self._max :]

    def snapshot(self) -> np.ndarray:
        return self._buf.copy()


def record_question_vad(
    audio_q: queue.Queue,
    noise_floor: float,
    cfg: dict,
    sample_rate: int,
    chunk_samples: int,
    threshold_voice: float,
    pre_roll: np.ndarray | None = None,
    speaker_lock: Optional["SpeakerLock"] = None,
    *,
    wait_playback: bool = False,
) -> np.ndarray:
    if wait_playback:
        wait_for_playback_idle()
        drain_queue(audio_q, 0.12)

    speech_thresh = max(threshold_voice * 1.8, noise_floor * cfg["speech_margin"])
    silence_thresh = max(noise_floor * 2.5, speech_thresh * 0.4)
    max_sec = float(cfg["max_record_sec"])
    min_speech_chunks = max(1, int(cfg["min_speech_sec"] / CHUNK_SEC))
    silence_chunks_needed = max(1, int(cfg["silence_after_speech_sec"] / CHUNK_SEC))
    min_record_speech_sec = float(cfg.get("min_record_speech_sec", 1.1))
    onset_timeout = float(cfg.get("listen_onset_timeout_sec", 5.0))
    parts: list[np.ndarray] = []
    if pre_roll is not None and pre_roll.size > 0:
        parts.append(pre_roll.astype(np.float32))
    speech_started = False
    speech_chunks = 0
    silence_chunks = 0
    speech_started_at = 0.0
    progress("[graba] …")
    # Esperar a que el usuario empiece (no grabar eco de «¿Dime?»)
    onset_deadline = time.time() + onset_timeout
    while time.time() < onset_deadline and not speech_started:
        try:
            data = audio_q.get(timeout=0.2)
        except queue.Empty:
            continue
        for start in range(0, len(data.reshape(-1)), chunk_samples):
            chunk = data.reshape(-1)[start : start + chunk_samples]
            if chunk.size < chunk_samples // 2:
                continue
            if block_rms(chunk) >= speech_thresh:
                speech_started = True
                speech_started_at = time.time()
                parts.append(chunk.astype(np.float32))
                speech_chunks = 1
                break
    if not speech_started:
        progress("   (sin voz — di la pregunta tras «¿Dime?»)          ")
        return np.array([], dtype=np.float32)

    deadline = time.time() + max_sec
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
                spoke_long_enough = (time.time() - speech_started_at) >= min_record_speech_sec
                if (
                    spoke_long_enough
                    and speech_chunks >= min_speech_chunks
                    and silence_chunks >= silence_chunks_needed
                ):
                    progress(f"   audio OK ({speech_chunks} tramos)          ")
                    break
        else:
            continue
        break
    if parts and speech_chunks >= min_speech_chunks and speaker_lock is not None and speaker_lock.ready:
        merged = np.concatenate(parts)
        ok, sim = speaker_lock.verify(merged)
        if not ok:
            progress(f"   voz de fondo ignorada (sim={sim:.2f})          ")
            return np.array([], dtype=np.float32)
    if parts and speech_chunks >= min_speech_chunks:
        return np.concatenate(parts)
    if parts:
        progress(f"   fin grabación ({len(parts)} tramos)          ")
    else:
        progress("   sin voz del activador          ")
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


def _speaker_lock_enabled(cfg: dict) -> bool:
    if os.getenv("ROBITA_SPEAKER_LOCK", "1").strip().lower() in ("0", "false", "no"):
        return False
    return bool(cfg.get("speaker_lock_enabled", True)) and SpeakerLock is not None


def run_voice_assistant(
    ww,
    cfg: dict,
    noise_floor: float,
    sample_rate: int,
    chunk_samples: int,
    on_session: Callable[..., None],
    greet: Callable[[], None],
    ww_baseline: float = 0.5,
) -> None:
    """Micrófono siempre abierto. Solo reacciona al wakeword; luego saludo → sesión → escucha."""
    hi = float(cfg["wakeword_threshold"])
    lo = max(0.0, hi - 0.10)
    spike_range_min = float(cfg.get("wakeword_spike_range_min", 0.10))
    peak_min = float(cfg.get("wakeword_peak_min", 0.72))
    hits_needed = int(cfg["hits_required"])
    cool_down = float(cfg["cool_down_sec"])
    voice_margin = float(cfg.get("voice_margin", 1.5))
    reject_hi = float(cfg.get("reject_prob_at_or_above", 1.0))
    smooth_n = max(1, int(cfg.get("prob_smooth_window", 3)))
    energy_min = max(float(ww.THRESHOLD_VOICE), noise_floor * voice_margin)

    audio_q: queue.Queue = queue.Queue(maxsize=1200)
    buffer = np.zeros(0, dtype=np.float32)
    block_samples = int(sample_rate * float(getattr(ww, "BLOCK_DURATION", 1.0)))
    hop_samples = block_samples if getattr(ww, "BACKEND", "") == "openwakeword" else max(1, int(block_samples * 0.5))
    consecutive_hits = 0
    last_trigger = 0.0
    session_active = False
    last_heartbeat = time.time()
    last_prob_shown = 0.0
    prob_hist: deque[float] = deque(maxlen=smooth_n)
    pre_roll = AudioPreRoll(sample_rate, float(cfg.get("audio_pre_roll_sec", 1.2)))
    stream_block = chunk_samples

    def callback(indata, frames, ctime, status):
        if status:
            log.warning("Audio: %s", status)
        flat = indata.copy().reshape(-1)
        pre_roll.push(flat)
        try:
            audio_q.put_nowait(flat)
        except queue.Full:
            pass

    stream_kwargs: dict = {
        "samplerate": sample_rate,
        "channels": 1,
        "dtype": "float32",
        "blocksize": stream_block,
        "latency": "high",
        "callback": callback,
    }
    mic = audio_input_device()
    if mic is not None:
        stream_kwargs["device"] = mic
        try:
            if isinstance(mic, int):
                mic_name = sd.query_devices(mic).get("name", mic)
            else:
                mic_name = str(mic)
        except Exception:
            mic_name = str(mic)
        cap_hz = input_device_sample_rate(mic, sample_rate)
        log.info("Micrófono: %s (stream %s Hz)", mic_name, sample_rate)
        if cap_hz != sample_rate:
            log.warning("Dispositivo nativo %s Hz — verifica ROBITA_AUDIO_INPUT", cap_hz)

    progress("")
    if verbose_progress():
        progress("=" * 52)
        progress("  LISTO — di «udito» para activar el asistente")
        progress("=" * 52)
        progress(f"  Activación: pico ≥{float(cfg.get('wakeword_rel_spike_min', 0.055)):.2f} sobre baseline  ({hits_needed} ventana(s))")
        progress("  Di «udito» claro, cerca del micrófono")
        progress("")
    else:
        status_line("Escuchando «udito»…")

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

                if playback_blocks_wakeword():
                    consecutive_hits = 0
                    continue

                if block_rms(block) < energy_min:
                    consecutive_hits = max(0, consecutive_hits - 1)
                    continue

                if getattr(ww, "BACKEND", "") == "openwakeword":
                    prob = ww.run_inference(block)
                    margin = prob - ww_baseline
                elif hasattr(ww, "run_inference_scores"):
                    prob, prob_other = ww.run_inference_scores(block)
                    margin = prob - prob_other
                else:
                    prob = ww.run_inference(block)
                    margin = prob - ww_baseline
                if reject_hi < 1.0 and prob >= reject_hi:
                    consecutive_hits = 0
                    continue
                prob_hist.append(prob)
                avg_prob = float(sum(prob_hist) / len(prob_hist))
                arr = list(prob_hist)
                p_range = (max(arr) - min(arr)) if len(arr) >= 2 else 0.0
                p_max = max(arr) if arr else prob
                rel_margin = prob - ww_baseline
                rel_pmax = p_max - ww_baseline
                rel_spike_min = float(cfg.get("wakeword_rel_spike_min", 0.055))
                margin_min = float(cfg.get("wakeword_margin_min", 0.055))
                has_spike = (
                    p_range >= spike_range_min
                    or rel_pmax >= rel_spike_min
                    or rel_margin >= rel_spike_min
                )
                # Con baseline alto (~0.7 en ruido), activar por pico RELATIVO al decir «udito».
                above = (
                    has_spike
                    and rel_margin >= margin_min
                    and prob >= lo
                    and block_rms(block) >= energy_min
                )
                if verbose_progress() and (prob > ww_baseline + 0.02 or prob > 0.40) and (time.time() - last_prob_shown) > 0.45:
                    progress(
                        f"[voz] udito={prob:.2f} base={ww_baseline:.2f} Δ={rel_margin:+.2f} pico={p_max:.2f}  "
                        f"[{consecutive_hits}/{hits_needed}]",
                        end="\r",
                    )
                    last_prob_shown = time.time()
                    last_heartbeat = time.time()

                if above:
                    consecutive_hits += 1
                else:
                    consecutive_hits = max(0, consecutive_hits - 1)

                if consecutive_hits < hits_needed:
                    continue
                if (time.time() - last_trigger) <= cool_down:
                    consecutive_hits = 0
                    continue

                last_trigger = time.time()
                consecutive_hits = 0
                buffer = np.zeros(0, dtype=np.float32)
                session_active = True

                progress(f"\n[wake] udito detectado (prob={prob:.2f}, margen={margin:.2f})", always=True)

                speaker_lock: Optional[SpeakerLock] = None
                if _speaker_lock_enabled(cfg):
                    enroll = [block.astype(np.float32)]
                    enroll_deadline = time.time() + float(cfg.get("speaker_enroll_sec", 0.5))
                    while time.time() < enroll_deadline:
                        try:
                            enroll.append(audio_q.get(timeout=0.05).reshape(-1))
                        except queue.Empty:
                            pass
                    speaker_lock = SpeakerLock(
                        threshold=float(cfg.get("speaker_lock_threshold", 0.74)),
                        sample_rate=sample_rate,
                    )
                    if speaker_lock.enroll(np.concatenate(enroll)):
                        progress("[voz] perfil del hablante guardado (solo esa voz en la sesión)")
                    else:
                        speaker_lock = None

                drain_queue(audio_q, 0.2)

                user_progress("[saludo] TTS local (Piper)…")
                greet()
                wait_for_playback_idle()
                drain_queue(audio_q, float(cfg.get("post_greet_drain_sec", 0.15)))

                user_progress("[sesión] escuchando…")
                try:
                    # Sin pre_roll: evita que Whisper transcriba el eco del saludo TTS
                    on_session(audio_q, speaker_lock, None)
                finally:
                    drain_queue(audio_q, 0.5)
                    buffer = np.zeros(0, dtype=np.float32)
                    session_active = False
                    last_trigger = time.time()
                    mark_playback_active(float(cfg.get("post_playback_cooldown_sec", 3.0)))
                    user_progress("")
                    if verbose_progress():
                        progress("=" * 52)
                        progress("  LISTO — di «udito» para activar el asistente")
                        progress("=" * 52)
                        progress("")
                    else:
                        status_line("Escuchando «udito»…")


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
