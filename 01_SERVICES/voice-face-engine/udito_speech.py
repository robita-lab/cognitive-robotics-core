"""
Voz con pausas, emociones y salida etiquetada para ROS2.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

log = logging.getLogger("udito.speech")

# Pausas tras signos (ms) — preset supersonic_m5 (más ágil que davefx)
_PAUSE_COMMA = 340
_PAUSE_SEMI = 420
_PAUSE_SENTENCE = 600

# length_scale < 1 = más rápido (alineado con tts_config.json preset supersonic_m5)
EMOTION_PROFILES: dict[str, dict[str, Any]] = {
    "happy": {"length_scale": 0.74, "noise_scale": 0.55, "noise_w": 0.65, "comma_pause_ms": 300},
    "helpful": {"length_scale": 0.78, "noise_scale": 0.58, "noise_w": 0.68, "comma_pause_ms": 330},
    "neutral": {"length_scale": 0.78, "noise_scale": 0.6, "noise_w": 0.7, "comma_pause_ms": 310},
    "sorry": {"length_scale": 0.82, "noise_scale": 0.52, "noise_w": 0.6, "comma_pause_ms": 370},
    "thinking": {"length_scale": 0.84, "noise_scale": 0.48, "noise_w": 0.58, "comma_pause_ms": 400},
    "proud": {"length_scale": 0.76, "noise_scale": 0.56, "noise_w": 0.66, "comma_pause_ms": 320},
    "informative": {"length_scale": 0.78, "noise_scale": 0.57, "noise_w": 0.67, "comma_pause_ms": 340},
    "laugh": {"length_scale": 0.70, "noise_scale": 0.62, "noise_w": 0.72, "comma_pause_ms": 220},
}


@dataclass
class SpeechSegment:
    text: str
    pause_after_ms: int = 0


@dataclass
class SpeechEvent:
    """Etiquetas de salida para ROS2 / registro."""
    text: str
    emotion: str = "neutral"
    source: str = "tts"
    label: str = ""
    segments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def emotion_for_rag(source: str, default: str = "helpful") -> str:
    mapping = {
        "rag": "helpful",
        "rag_no_results": "sorry",
        "rag_low_confidence": "sorry",
        "fixed_udit_address": "informative",
        "basic_qa": "happy",
        "gpt": "neutral",
        "error": "sorry",
        "pre_search": "thinking",
        "fun_fact": "happy",
        "fun_joke": "happy",
    }
    return mapping.get(source, default)


def synthesize_laugh_wav_bytes(sample_rate: int = 22050) -> bytes:
    """Risa corta sintética (no TTS): varios «ja» sin decir «jijiji»."""
    rng = np.random.default_rng(42)
    parts: list[np.ndarray] = []
    for i in range(4):
        dur = int(sample_rate * (0.10 + 0.025 * rng.random()))
        t = np.arange(dur, dtype=np.float64) / sample_rate
        f0 = 200.0 + 35.0 * i + float(rng.uniform(-12, 12))
        tone = np.sin(2 * np.pi * f0 * t) * 0.38
        tone += np.sin(2 * np.pi * f0 * 2.1 * t) * 0.14
        noise = rng.standard_normal(dur) * 0.22
        env = np.sin(np.pi * np.arange(dur) / max(dur - 1, 1)) ** 1.7
        parts.append(((tone + noise) * env * 0.52).astype(np.float32))
        gap = int(sample_rate * (0.055 + 0.018 * rng.random()))
        parts.append(np.zeros(gap, dtype=np.float32))
    audio = np.concatenate(parts) if parts else np.zeros(int(sample_rate * 0.5), dtype=np.float32)
    peak = float(np.max(np.abs(audio))) or 1.0
    pcm = (audio / peak * 0.82 * 32767.0).astype(np.int16)
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out_path = out.name
    out.close()
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    data = Path(out_path).read_bytes()
    try:
        Path(out_path).unlink(missing_ok=True)
    except OSError:
        pass
    return data


def _laugh_sound_path() -> Path | None:
    raw = os.getenv("ROBITA_LAUGH_SOUND", "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p
    default = Path(__file__).resolve().parent / "assets" / "audio" / "laugh.mp3"
    return default if default.is_file() else None


def play_laugh_sound(play_fn: Callable[[bytes], None]) -> None:
    """Archivo opcional (ROBITA_LAUGH_SOUND) o risa sintética."""
    from robot_common import mark_playback_active, play_media_file

    path = _laugh_sound_path()
    if path is not None:
        mark_playback_active(1.8)
        if play_media_file(str(path), playback_guard_sec=1.8):
            return
    mark_playback_active(1.5)
    play_fn(synthesize_laugh_wav_bytes())


def speak_joke_with_laugh(
    tts,
    joke_text: str,
    *,
    play_fn: Callable[[bytes], None],
    progress_fn: Callable[[str], None] | None = None,
) -> None:
    """Cuenta el chiste y después un sonido de risa (no «ji ji ji» por voz)."""
    speak(
        tts,
        joke_text,
        emotion="happy",
        source="fun_joke",
        label="chiste",
        play_fn=play_fn,
        progress_fn=progress_fn,
    )
    if progress_fn:
        progress_fn("[risa] (sonido)")
    event = SpeechEvent(text="", emotion="laugh", source="fun_joke_laugh", label="risa")
    publish_speech_event(event)
    play_laugh_sound(play_fn)


def normalize_for_speech(text: str) -> str:
    """URLs y correos legibles en voz (no «uve doble ve…»)."""
    t = text.strip()
    t = re.sub(r"https?://(www\.)?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwww\.", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\budit\.es\b", "udit punto es", t, flags=re.IGNORECASE)
    t = re.sub(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", r"correo en \2", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_speech_text(text: str) -> str:
    t = normalize_for_speech(text)
    t = re.sub(r"\s+", " ", t.strip())
    t = re.sub(r",\s*,+", ",", t)
    # Pausa natural antes de «hasta» en rangos horarios
    t = re.sub(
        r"\s+hasta las ",
        ", hasta las ",
        t,
        flags=re.IGNORECASE,
    )
    return t


def segment_text(text: str, emotion: str = "neutral") -> list[SpeechSegment]:
    """Divide en frases con pausas tras comas y puntos."""
    prof = EMOTION_PROFILES.get(emotion, EMOTION_PROFILES["neutral"])
    pause_comma = int(prof.get("comma_pause_ms", _PAUSE_COMMA))
    t = normalize_speech_text(text)
    if not t:
        return []

    parts = re.split(r"(\s*[,;]\s*|\s+[.!?…]+\s*)", t)
    segments: list[SpeechSegment] = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        delim = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if chunk:
            pause = 0
            if "," in delim:
                pause = pause_comma
            elif ";" in delim:
                pause = _PAUSE_SEMI
            elif delim and re.search(r"[.!?]", delim):
                pause = _PAUSE_SENTENCE
            segments.append(SpeechSegment(text=chunk, pause_after_ms=pause))
        i += 2 if delim else 1

    if not segments:
        segments.append(SpeechSegment(text=t, pause_after_ms=0))
    return segments


def _wav_to_pcm(wav_path: str) -> tuple[bytes, int]:
    with wave.open(wav_path, "rb") as wf:
        rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    return pcm, rate


def _concat_wavs(paths: list[str], pauses_ms: list[int]) -> bytes:
    if not paths:
        return b""
    pcm_parts: list[np.ndarray] = []
    rate = 22050
    for idx, p in enumerate(paths):
        pcm, rate = _wav_to_pcm(p)
        arr = np.frombuffer(pcm, dtype=np.int16)
        pcm_parts.append(arr)
        if idx < len(pauses_ms) and pauses_ms[idx] > 0:
            n = int(rate * pauses_ms[idx] / 1000)
            pcm_parts.append(np.zeros(n, dtype=np.int16))
    merged = np.concatenate(pcm_parts)
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out_path = out.name
    out.close()
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(merged.tobytes())
    data = Path(out_path).read_bytes()
    try:
        Path(out_path).unlink(missing_ok=True)
    except OSError:
        pass
    return data


def synthesize_with_pauses(tts, text: str, emotion: str = "neutral") -> tuple[bytes | None, SpeechEvent]:
    """Sintetiza con pausas entre segmentos y perfil emocional."""
    segments = segment_text(text, emotion)
    prof = EMOTION_PROFILES.get(emotion, EMOTION_PROFILES["neutral"])
    paths: list[str] = []
    pauses: list[int] = []

    for seg in segments:
        if not seg.text.strip():
            continue
        wav = tts.synthesize_to_bytes(
            seg.text,
            tts_overrides={
                "length_scale": prof.get("length_scale"),
                "noise_scale": prof.get("noise_scale"),
                "noise_w": prof.get("noise_w"),
            },
        )
        if not wav:
            continue
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(wav)
        tmp.flush()
        paths.append(tmp.name)
        pauses.append(seg.pause_after_ms)

    event = SpeechEvent(
        text=text,
        emotion=emotion,
        segments=[{"text": s.text, "pause_after_ms": s.pause_after_ms} for s in segments],
    )
    if not paths:
        return None, event
    combined = _concat_wavs(paths, pauses)
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
    return combined, event


def publish_speech_event(event: SpeechEvent) -> None:
    """Escribe JSON y publica en /udito/speech_out si ROS2 está disponible."""
    payload = event.to_dict()
    out_file = os.getenv(
        "ROBITA_SPEECH_EVENT_FILE",
        "/tmp/udito_speech_out.json",
    )
    try:
        Path(out_file).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        log.debug("No se pudo escribir %s: %s", out_file, e)

    if os.getenv("ROBITA_ROS2_SPEECH", "1").strip().lower() in ("0", "false", "no"):
        return

    try:
        import rclpy
        from std_msgs.msg import String
    except ImportError:
        return

    global _ROS_NODE, _ROS_PUB
    try:
        if _ROS_NODE is None:
            if not rclpy.ok():
                rclpy.init()
            _ROS_NODE = rclpy.create_node("udito_speech")
            _ROS_PUB = _ROS_NODE.create_publisher(String, "/udito/speech_out", 10)
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        _ROS_PUB.publish(msg)
        rclpy.spin_once(_ROS_NODE, timeout_sec=0.02)
    except Exception as e:
        log.debug("ROS2 publish: %s", e)


_ROS_NODE = None
_ROS_PUB = None


def publish_face_cue(
    emotion: str,
    label: str = "",
    *,
    source: str = "pipeline",
) -> None:
    """Actualiza pantalla/ROS2 sin TTS (escuchando, transcribiendo, etc.)."""
    publish_speech_event(
        SpeechEvent(
            text=label,
            emotion=emotion,
            source=source,
            label=emotion,
        )
    )


def run_face_expression_cycle(
    steps: list[tuple[str, str]],
    *,
    step_sec: float = 1.15,
    intro: str = "Mira las expresiones.",
    tts=None,
    play_fn: Callable[[bytes], None] | None = None,
    progress_fn: Callable[[str], None] | None = None,
) -> None:
    """Ciclo sincronizado de expresiones en pantalla (y ROS2 / JSON)."""
    if progress_fn:
        progress_fn(f"[cara demo] {len(steps)} expresiones")
    if intro and tts is not None and play_fn is not None:
        wav, event = synthesize_with_pauses(tts, intro, "helpful")
        event.source = "face_demo"
        event.label = "intro"
        publish_speech_event(event)
        if wav:
            play_fn(wav)
    pause = max(0.35, float(step_sec))
    for expr, caption in steps:
        publish_face_cue(expr, caption, source="face_demo")
        if progress_fn:
            progress_fn(f"[cara demo] {expr}")
        time.sleep(pause)


def show_face_expression(
    expression: str,
    reply: str = "",
    *,
    tts=None,
    play_fn: Callable[[bytes], None] | None = None,
    progress_fn: Callable[[str], None] | None = None,
    speak_reply: bool = True,
) -> None:
    """Actualiza pantalla/ROS2 al instante; opcionalmente dice una frase corta."""
    event = SpeechEvent(
        text=reply,
        emotion=expression,
        source="face_command",
        label="cara",
    )
    publish_speech_event(event)
    if not speak_reply or not (reply or "").strip() or tts is None or play_fn is None:
        return
    if progress_fn:
        progress_fn(f"[cara] ({expression}) {reply[:60]}")
    wav, _ = synthesize_with_pauses(tts, reply, expression)
    if wav:
        play_fn(wav)


def speak(
    tts,
    text: str,
    *,
    emotion: str = "neutral",
    source: str = "tts",
    label: str = "",
    play_fn: Callable[[bytes], None],
    progress_fn: Callable[[str], None] | None = None,
) -> None:
    text = normalize_for_speech(text)
    if progress_fn:
        progress_fn(f"[{label}] ({emotion}) {text[:80]}{'…' if len(text) > 80 else ''}")
    wav, event = synthesize_with_pauses(tts, text, emotion)
    event.source = source
    event.label = label
    publish_speech_event(event)
    if wav:
        play_fn(wav)
