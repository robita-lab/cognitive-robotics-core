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
    if key == "respeaker":
        for idx, info in enumerate(sd.query_devices()):
            if int(info.get("max_input_channels", 0)) <= 0:
                continue
            name = str(info.get("name", "")).lower()
            if any(p in name for p in patterns):
                in_ch = int(info.get("max_input_channels", 0))
                if in_ch > 2:
                    log.info(
                        "ReSpeaker %sch ALSA → captura vía Pulse (beamforming; start.sh fija la source)",
                        in_ch,
                    )
                    return "pulse"
                log.info("Micrófono resuelto: %s → [%s] %s", raw, idx, info.get("name"))
                return idx
        log.info(
            "ReSpeaker: captura vía Pulse (multichannel); ALSA sin entrada usable"
        )
        return "pulse"
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

_PULSE_SOURCE_ALIASES = {
    "respeaker": "alsa_input.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.multichannel-input",
}


def resolve_pulse_source(audio_input: str) -> str | None:
    explicit = os.getenv("ROBITA_PULSE_SOURCE", "").strip()
    if explicit:
        return explicit
    key = audio_input.strip().lower()
    if key in _PULSE_SOURCE_ALIASES:
        return _PULSE_SOURCE_ALIASES[key]
    if key.startswith("alsa_input."):
        return audio_input.strip()
    return None


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
WW_CONFIG = SERVICES / "wakeword-engine" / "config" / "wakeword.json"
SESSION_CONFIG = Path(__file__).resolve().parent / "config" / "session.json"

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
    """Une detección wakeword (JSON del módulo) + sesión de voz (JSON del robot)."""
    cfg: dict = {}
    try:
        with open(WW_CONFIG, encoding="utf-8") as f:
            ww_data = json.load(f)
        cfg.update(ww_data.get("detection", {}))
        if "wake_word" in ww_data:
            cfg["wake_word"] = ww_data["wake_word"]
    except Exception as exc:
        log.warning("No se pudo leer %s: %s", WW_CONFIG, exc)
    try:
        with open(SESSION_CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception as exc:
        log.warning("No se pudo leer %s: %s", SESSION_CONFIG, exc)
    ww_env = os.getenv("ROBITA_WAKEWORD", "").strip()
    if ww_env:
        cfg["wake_word"] = ww_env
    return cfg


def wake_phrase(cfg: dict | None = None) -> str:
    if cfg and str(cfg.get("wake_word", "")).strip():
        return str(cfg["wake_word"]).strip()
    env = os.getenv("ROBITA_WAKEWORD", "").strip()
    return env or "udito"


def block_rms(block: np.ndarray) -> float:
    b = block.astype(np.float64).reshape(-1)
    if b.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(b * b)))


def input_capture_channels(device: int | str | None) -> tuple[int, bool]:
    """Canales de captura; downmix=True si hay que promediar (ReSpeaker 6ch)."""
    if device is None or isinstance(device, str):
        return 1, False
    try:
        n = int(sd.query_devices(device).get("max_input_channels", 1))
    except Exception:
        return 1, False
    if n > 1:
        return n, True
    return 1, False


def mono_from_capture(indata: np.ndarray) -> np.ndarray:
    if indata.ndim == 1:
        return indata.copy().astype(np.float32)
    return indata.mean(axis=1).astype(np.float32)


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
    cap_ch, downmix = input_capture_channels(dev)
    kwargs: dict = {"samplerate": sample_rate, "channels": cap_ch, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
        if verbose_progress():
            print(f"   micrófono: {dev}" + (f" ({cap_ch}ch→mono)" if downmix else ""))
    audio = sd.rec(int(seconds * sample_rate), **kwargs)
    sd.wait()
    flat = mono_from_capture(audio) if downmix else audio.reshape(-1)
    floor = max(block_rms(flat), 1e-5)
    if verbose_progress():
        print(f"   nivel ambiente RMS={floor:.5f}")

    baseline = 0.5
    if ww is not None and hasattr(ww, "run_inference"):
        block_samples = int(sample_rate * float(getattr(ww, "BLOCK_DURATION", 1.0)))
        voice_margin = float(cfg.get("voice_margin", 5.0))
        energy_min = max(float(getattr(ww, "THRESHOLD_VOICE", 1e-4)), floor * voice_margin * 0.35)
        probs: list[float] = []
        cal_flat = flat.astype(np.float32)
        for start in range(0, max(1, cal_flat.size - block_samples + 1), block_samples // 2):
            block = cal_flat[start : start + block_samples]
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


def play_listen_beep(sample_rate: int = 16000) -> None:
    """Dos tonos cortos por el altavoz — señal de «te escucho» (sin TTS)."""
    sr = int(sample_rate)
    parts: list[np.ndarray] = []
    for freq, dur in ((784, 0.06), (988, 0.08)):
        n = max(int(sr * dur), 1)
        t = np.arange(n, dtype=np.float32) / float(sr)
        ramp = np.minimum(1.0, np.minimum(t / 0.008, (dur - t) / 0.015))
        parts.append((0.22 * np.sin(2 * np.pi * freq * t) * ramp).astype(np.float32))
    tone = np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32)
    pcm = (np.clip(tone, -1.0, 1.0) * 32767.0).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        play_wav_file(path, playback_guard_sec=0.25)
    except OSError as exc:
        log.debug("listen beep: %s", exc)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def announce_session_listening() -> None:
    """Mensaje muy visible en terminal cuando empieza la escucha."""
    user_progress("")
    user_progress("═" * 46)
    user_progress("  ▶ TE ESCUCHO — habla ahora")
    user_progress("═" * 46)


def play_wav_bytes(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        if not play_wav_file(path):
            progress("[audio] ERROR — no se oyó nada. Ejecuta: ./scripts/udito/audio-test.sh")
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


def _mic_level_bar(rms: float, thresh: float, width: int = 14) -> str:
    if thresh <= 0:
        level = 0
    else:
        level = min(width, int(rms / thresh * width))
    return "█" * level + "░" * (width - level)


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
    on_partial_audio: Callable[[np.ndarray, float], None] | None = None,
) -> np.ndarray:
    if wait_playback:
        wait_for_playback_idle()
        drain_queue(audio_q, 0.12)

    vad_factor = float(cfg.get("vad_energy_factor", 1.8))
    speech_thresh = max(threshold_voice * vad_factor, noise_floor * cfg["speech_margin"])
    silence_thresh = max(noise_floor * 2.5, speech_thresh * 0.4)
    max_sec = float(cfg["max_record_sec"])
    min_speech_chunks = max(1, int(cfg["min_speech_sec"] / CHUNK_SEC))
    silence_chunks_needed = max(1, int(cfg["silence_after_speech_sec"] / CHUNK_SEC))
    min_record_speech_sec = float(cfg.get("min_record_speech_sec", 1.1))
    onset_timeout = float(cfg.get("listen_onset_timeout_sec", 5.0))
    mic_feedback = bool(cfg.get("mic_level_feedback", True))
    partial_interval = float(cfg.get("stt_live_preview_interval_sec", 1.5))
    parts: list[np.ndarray] = []
    if pre_roll is not None and pre_roll.size > 0:
        parts.append(pre_roll.astype(np.float32))
    speech_started = False
    speech_chunks = 0
    silence_chunks = 0
    speech_started_at = 0.0
    last_ui = 0.0
    last_partial_at = 0.0
    peak_rms = 0.0
    user_progress("[mic] esperando tu voz…")
    # Esperar a que el usuario empiece a hablar
    onset_deadline = time.time() + onset_timeout
    while time.time() < onset_deadline and not speech_started:
        try:
            data = audio_q.get(timeout=0.2)
        except queue.Empty:
            if mic_feedback and time.time() - last_ui >= 0.4:
                user_progress("[mic] escuchando… (habla ahora)", end="\r")
                last_ui = time.time()
            continue
        for start in range(0, len(data.reshape(-1)), chunk_samples):
            chunk = data.reshape(-1)[start : start + chunk_samples]
            if chunk.size < chunk_samples // 2:
                continue
            r = block_rms(chunk)
            peak_rms = max(peak_rms, r)
            if mic_feedback and time.time() - last_ui >= 0.12:
                user_progress(
                    f"[mic] {_mic_level_bar(r, speech_thresh)}  "
                    f"({r:.4f} / {speech_thresh:.4f})",
                    end="\r",
                )
                last_ui = time.time()
            if r >= speech_thresh:
                speech_started = True
                speech_started_at = time.time()
                parts.append(chunk.astype(np.float32))
                speech_chunks = 1
                user_progress("[mic] ● voz detectada — grabando…")
                break
    if not speech_started:
        user_progress(
            f"[mic] sin voz en {onset_timeout:.0f}s "
            f"(pico={peak_rms:.4f}, umbral={speech_thresh:.4f})"
        )
        return np.array([], dtype=np.float32)

    deadline = time.time() + max_sec
    started_at = time.time()
    last_tick = started_at
    while time.time() < deadline:
        now = time.time()
        rec_sec = now - speech_started_at
        if mic_feedback and now - last_tick >= 0.15:
            user_progress(f"[mic] ● grabando {rec_sec:.1f}s", end="\r")
            last_tick = now
        if (
            on_partial_audio
            and parts
            and rec_sec >= partial_interval
            and (now - last_partial_at) >= partial_interval
        ):
            on_partial_audio(np.concatenate(parts), rec_sec)
            last_partial_at = now
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
                    user_progress(f"[mic] fin ({rec_sec:.1f}s, {speech_chunks} tramos)")
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
    ww_label = wake_phrase(cfg)
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
    hop_samples = (
        max(1, block_samples // 2)
        if getattr(ww, "BACKEND", "") == "openwakeword"
        else max(1, int(block_samples * 0.5))
    )
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
        flat = mono_from_capture(indata.copy())
        pre_roll.push(flat)
        try:
            audio_q.put_nowait(flat)
        except queue.Full:
            pass

    mic = audio_input_device()
    cap_ch, _downmix = input_capture_channels(mic)
    stream_kwargs: dict = {
        "samplerate": sample_rate,
        "channels": cap_ch,
        "dtype": "float32",
        "blocksize": stream_block,
        "latency": "high",
        "callback": callback,
    }
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
        log.info("Micrófono: %s (stream %s Hz%s)", mic_name, sample_rate, f", {cap_ch}ch→mono" if cap_ch > 1 else "")
        if cap_hz != sample_rate:
            log.warning("Dispositivo nativo %s Hz — verifica ROBITA_AUDIO_INPUT", cap_hz)

    progress("")
    try:
        from ros2_bridge import log_ros2_status, publish_state

        log_ros2_status()
        publish_state("wakeword_listening")
    except ImportError:
        pass

    if verbose_progress():
        progress("=" * 52)
        progress(f"  LISTO — di «{ww_label}» para activar el asistente")
        progress("=" * 52)
        progress(f"  Activación: pico ≥{float(cfg.get('wakeword_rel_spike_min', 0.055)):.2f} sobre baseline  ({hits_needed} ventana(s))")
        progress(f"  Di «{ww_label}» claro, cerca del micrófono")
        progress("")
    else:
        status_line(f"Escuchando «{ww_label}»…")

    with sd.InputStream(**stream_kwargs):
        while True:
            try:
                data = audio_q.get(timeout=0.5)
            except queue.Empty:
                if verbose_progress() and time.time() - last_heartbeat >= 10.0:
                    progress(f"[escucha] LISTO — esperando «{ww_label}»…")
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
                try:
                    from ros2_bridge import publish_state, publish_wakeword_detected

                    publish_wakeword_detected(
                        wake_word=str(cfg.get("wake_word", "udito")),
                        probability=prob,
                        margin=margin,
                        baseline=ww_baseline,
                    )
                    publish_state("wakeword_detected", probability=prob)
                except ImportError:
                    pass

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

                drain_queue(audio_q, 0.12)

                try:
                    from ros2_bridge import publish_state

                    publish_state("session_listening")
                except ImportError:
                    pass
                try:
                    from udito_speech import publish_face_cue

                    publish_face_cue("listening", "te escucho — habla", source="session")
                except ImportError:
                    pass

                announce_session_listening()
                user_progress("[sesión] wakeword pausado — solo micrófono + STT")
                buffer = np.zeros(0, dtype=np.float32)
                cue = str(cfg.get("listen_cue", "beep")).strip().lower()
                if cfg.get("post_wake_greeting", False):
                    user_progress("[saludo] TTS local (Piper)…")
                    greet()
                    wait_for_playback_idle()
                    drain_queue(audio_q, float(cfg.get("post_greet_drain_sec", 0.1)))
                elif cue == "beep":
                    play_listen_beep(sample_rate)
                    drain_queue(audio_q, 0.08)
                elif cue == "tts_short":
                    user_progress("[escucha] Te escucho.")
                    greet()
                    wait_for_playback_idle()
                    drain_queue(audio_q, 0.08)
                else:
                    drain_queue(audio_q, 0.06)
                try:
                    # Sin pre_roll: evita que Whisper transcriba el eco del saludo TTS
                    on_session(audio_q, speaker_lock, None)
                finally:
                    drain_queue(audio_q, 0.5)
                    buffer = np.zeros(0, dtype=np.float32)
                    session_active = False
                    last_trigger = time.time()
                    try:
                        from ros2_bridge import publish_state

                        publish_state("idle")
                    except ImportError:
                        pass
                    mark_playback_active(float(cfg.get("post_playback_cooldown_sec", 3.0)))
                    user_progress("")
                    if verbose_progress():
                        progress("=" * 52)
                        progress(f"  LISTO — di «{ww_label}» para activar el asistente")
                        progress("=" * 52)
                        progress("")
                    else:
                        status_line(f"Escuchando «{ww_label}»…")


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
