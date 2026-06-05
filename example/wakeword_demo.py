#!/usr/bin/env python3
"""
Prueba wakeword: mic → frase (.env) → respuesta TTS.

  ./example/run.sh           # di «hey jarvis» (inglés, claro)
  ./example/run.sh --test    # solo comprueba TTS (sin mic)
  Ctrl+C                     # salir
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "03_ADAPTERS" / "robot-udit-physical"
WW_DIR = ROOT / "01_SERVICES" / "wakeword-engine"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(WW_DIR))

from robot_common import (  # noqa: E402
    block_rms,
    input_capture_channels,
    mark_playback_active,
    mono_from_capture,
    play_wav_bytes,
    resolve_audio_input,
    setup_wakeword_path,
    wake_phrase,
)

GREETING = "Hola señor, ¿en qué lo puedo ayudar hoy?"
COOLDOWN_SEC = float(os.getenv("ROBITA_DEMO_COOLDOWN", "3.0"))


def _threshold(ww) -> float:
    env = os.getenv("ROBITA_DEMO_WW_THRESHOLD", "").strip()
    if env:
        return float(env)
    return float(getattr(ww, "WAKEWORD_THRESHOLD", 0.45))


def _tts_greeting() -> None:
    sys.path.insert(0, str(ROOT / "01_SERVICES" / "tts-engine"))
    from piper_tts_real import PiperTTS

    cfg = os.getenv(
        "ROBITA_TTS_CONFIG",
        str(ROOT / "01_SERVICES" / "tts-engine" / "config" / "tts_config.json"),
    )
    tts = PiperTTS(config_path=cfg)
    mark_playback_active(max(len(GREETING) * 0.08, 4.0))
    play_wav_bytes(tts.synthesize_to_bytes(GREETING))


def _respond(reason: str) -> None:
    print(f"\n>>> DETECTADO ({reason})", flush=True)
    print(f">>> {GREETING}\n", flush=True)
    try:
        _tts_greeting()
    except Exception as exc:
        print(f"ERROR TTS: {exc}", flush=True)


def _check_env(phrase: str) -> None:
    model_env = os.getenv("ROBITA_WAKEWORD_MODEL", "").strip()
    if "jarvis" in phrase.lower() and not model_env:
        print(
            "ERROR: ROBITA_WAKEWORD_MODEL no está en .env — "
            "se cargará udito.onnx (roto, prob≈0).\n"
            "Añade:\n"
            '  ROBITA_WAKEWORD="hey jarvis"\n'
            "  ROBITA_WAKEWORD_MODEL=/opt/robita-lab/01_SERVICES/wakeword-engine/"
            "models/openwakeword/hey_jarvis_v0.1.onnx\n",
            flush=True,
        )
        raise SystemExit(1)
    if model_env and not Path(model_env).is_file():
        print(f"ERROR: no existe el modelo: {model_env}", flush=True)
        raise SystemExit(1)


def _warn_phrase_model_mismatch(phrase: str, model_path: Path) -> None:
    """Avisa si la frase del .env no coincide con el modelo cargado."""
    name = model_path.name.lower()
    pl = phrase.lower()
    if "udito" in pl and "jarvis" in name:
        print(
            "\n*** AVISO: ROBITA_WAKEWORD=udito pero el modelo es hey_jarvis.\n"
            "    Cambia .env:\n"
            "      ROBITA_WAKEWORD_MODEL=.../models/udito.onnx\n"
            "    O usa: ./example/run_udito.sh\n",
            flush=True,
        )
    elif "jarvis" in pl and "udito" in name:
        print(
            "\n*** AVISO: ROBITA_WAKEWORD=hey jarvis pero el modelo es udito.onnx.\n"
            "    Di «udito» o cambia .env / usa ./example/run_udito.sh\n",
            flush=True,
        )
    elif "jarvis" in pl and "jarvis" in name:
        print(
            "\n  (Modelo hey jarvis: di la frase en INGLÉS, claro: «hey jarvis»)\n"
            "  Para «udito»: ./example/run_udito.sh\n",
            flush=True,
        )
    elif "udito" in pl and "udito" in name:
        print(
            "\n  (Modelo udito: di «udito» claro, cerca del mic)\n"
            "  Umbral típico: ROBITA_DEMO_WW_THRESHOLD=0.30\n",
            flush=True,
        )


def _calibrate_floor(dev, ch: int, rate: int, seconds: float = 2.0) -> float:
    """Piso de ruido (mediana por bloques — no subir si hablas en la calibración)."""
    print(f"Calibrando ({seconds:.0f}s — NO hables, espera…) ", end="", flush=True)
    kwargs: dict = {"samplerate": rate, "channels": ch, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
    rec = sd.rec(int(seconds * rate), **kwargs)
    sd.wait()
    flat = mono_from_capture(rec) if rec.ndim > 1 else rec.reshape(-1)
    block = max(1, int(rate * 0.1))
    chunks = [block_rms(flat[i : i + block]) for i in range(0, len(flat) - block, block)]
    floor = float(np.median(chunks)) if chunks else block_rms(flat)
    floor = max(floor, 1e-5)
    peak = float(max(chunks)) if chunks else block_rms(flat)
    if peak > floor * 6:
        print(f"\n  AVISO: hubo ruido/voz en calibración (pico={peak:.4f}).", flush=True)
        print("  Repite sin hablar o el umbral quedará muy alto.", flush=True)
    else:
        print("OK", flush=True)
    print(f"  piso RMS={floor:.5f}\n", flush=True)
    return floor


def listen(phrase: str) -> None:
    _check_env(phrase)
    setup_wakeword_path()
    import Detector_wakeword as ww  # noqa: WPS433
    from engine import get_engine  # noqa: WPS433

    ww.load()
    eng = get_engine()
    model_path = eng._model_path()
    _warn_phrase_model_mismatch(phrase, model_path)
    prob_min = _threshold(ww)
    dev = resolve_audio_input()
    ch, _downmix = input_capture_channels(dev)
    rate = ww.SAMPLE_RATE
    block = int(rate * ww.BLOCK_DURATION)

    noise_floor = _calibrate_floor(dev, ch, rate)
    env_rms = float(os.getenv("ROBITA_DEMO_RMS_MIN", "0") or "0")
    print_min = min(max(env_rms, noise_floor * 2.5, 0.004), 0.012)
    trigger_min = max(noise_floor * 1.8, 0.003)

    print("=" * 56)
    print(f"  Wakeword: «{phrase}»  (di en INGLÉS si es hey jarvis)")
    print(f"  Modelo:   {model_path}")
    print(f"  Mic:      {dev} ({ch} ch) @ {rate} Hz")
    print(f"  Umbral:   prob >= {prob_min:.2f}  |  voz rms >= {print_min:.4f}")
    print("=" * 56)
    print("Calentando OWW (~2 s)…", flush=True)
    eng._model.reset()
    z = np.zeros(block, dtype=np.float32)
    for _ in range(25):
        ww.run_inference(z)
    print(f"Listo. Di «{phrase}». Ctrl+C para salir.", flush=True)
    print("(Sin líneas = silencio normal. Solo aparece algo cuando hablas.)\n", flush=True)

    audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=400)
    buffer = np.zeros(0, dtype=np.float32)
    cool_until = 0.0

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", flush=True)
        flat = mono_from_capture(indata.copy())
        try:
            audio_q.put_nowait(flat)
        except queue.Full:
            pass

    stream_kw: dict = {
        "samplerate": rate,
        "channels": ch,
        "dtype": "float32",
        "blocksize": block,
        "callback": callback,
    }
    if dev is not None:
        stream_kw["device"] = dev

    with sd.InputStream(**stream_kw):
        while True:
            try:
                data = audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            buffer = np.concatenate([buffer, data])
            while buffer.size >= block:
                chunk = buffer[:block]
                buffer = buffer[block:]
                rms = block_rms(chunk)
                now = time.time()

                if rms < print_min:
                    continue

                prob = float(ww.run_inference(chunk))
                mark = "  ◀ DISPARA" if prob >= prob_min else ""
                print(f"  rms={rms:.4f}  prob={prob:.6f}{mark}", flush=True)

                if now < cool_until or rms < trigger_min:
                    continue
                if prob >= prob_min:
                    _respond(f"prob={prob:.2f}")
                    cool_until = now + COOLDOWN_SEC
                    eng._model.reset()
                    buffer = np.zeros(0, dtype=np.float32)
                    for _ in range(15):
                        ww.run_inference(z)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba mic → wakeword → TTS")
    parser.add_argument("--test", action="store_true", help="Solo TTS (sin mic)")
    args = parser.parse_args()

    phrase = wake_phrase()
    if args.test:
        print("Modo --test: solo TTS\n")
        _respond("modo --test")
        return 0

    try:
        listen(phrase)
    except KeyboardInterrupt:
        print("\nSalida.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
