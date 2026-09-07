#!/usr/bin/env python3
"""
Prueba del micrófono — medidor RMS en vivo.

  ./example/mic_test.py              # barras en tiempo real (Ctrl+C salir)
  ./example/mic_test.py --record 5   # graba 5 s → /tmp/mic_test.wav
  ./example/mic_test.py --devices    # lista dispositivos
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_ADAPTERS" / "robot-udit-physical"))


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from robot_common import block_rms, input_capture_channels, mono_from_capture, resolve_audio_input  # noqa: E402


def _pulse_source_name() -> str | None:
    try:
        out = subprocess.run(
            ["pactl", "get-default-source"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        name = (out.stdout or "").strip()
        return name or None
    except Exception:
        return None


def print_mic_route() -> None:
    dev = resolve_audio_input()
    ch, downmix = input_capture_channels(dev)
    print(f"ROBITA_AUDIO_INPUT={os.getenv('ROBITA_AUDIO_INPUT', '(vacío)')!r}")
    print(f"Captura: dev={dev!r}  canales={ch}" + (" → mono" if downmix else ""))
    if dev == "pulse" or os.getenv("ROBITA_AUDIO_INPUT", "").lower() == "respeaker":
        src = _pulse_source_name()
        if src:
            print(f"Pulse source: {src}")
        if src and ("respeaker" in src.lower() or "seeed" in src.lower()):
            print("  OK — ReSpeaker USB Mic Array (vía Pulse, beamforming)")
        elif src:
            print("  AVISO — no parece ReSpeaker; revisa ROBITA_PULSE_SOURCE en .env")
    elif dev is None:
        print("  AVISO — sin dispositivo; ejecuta: source .env  o  ./example/run.sh")
    elif isinstance(dev, int):
        import sounddevice as sd
        info = sd.query_devices(dev)
        print(f"  ALSA [{dev}] {info.get('name')}")
    print()


def _bar(rms: float, scale: float = 0.15) -> str:
    n = min(40, int(rms / scale * 40))
    return "#" * n + "." * (40 - n)


def list_devices() -> None:
    for i, info in enumerate(sd.query_devices()):
        inch = int(info.get("max_input_channels", 0))
        outch = int(info.get("max_output_channels", 0))
        if inch or outch:
            print(f"  [{i}] in={inch} out={outch}  {info.get('name')}")


def live_meter(seconds: float | None) -> None:
    print_mic_route()
    dev = resolve_audio_input()
    ch, _ = input_capture_channels(dev)
    rate = 16000
    block = int(rate * 0.1)
    print(f"Mic: {dev} ({ch} ch) @ {rate} Hz")
    print("Habla — Ctrl+C salir\n")
    kwargs: dict = {"samplerate": rate, "channels": ch, "dtype": "float32", "blocksize": block}
    if dev is not None:
        kwargs["device"] = dev
    t0 = time.time()
    with sd.InputStream(**kwargs) as stream:
        while stream.active:
            data, _ = stream.read(block)
            flat = mono_from_capture(data)
            rms = block_rms(flat)
            print(f"  rms={rms:.5f}  [{_bar(rms)}]", flush=True)
            if seconds and time.time() - t0 >= seconds:
                break


def record_wav(path: Path, seconds: float) -> None:
    print_mic_route()
    dev = resolve_audio_input()
    ch, _ = input_capture_channels(dev)
    rate = 16000
    print(f"Grabando {seconds:.0f} s → {path}")
    print(f"Mic: {dev} ({ch} ch). ¡HABLA AHORA!\n")
    kwargs: dict = {"samplerate": rate, "channels": ch, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
    rec = sd.rec(int(seconds * rate), **kwargs)
    sd.wait()
    flat = mono_from_capture(rec) if rec.ndim > 1 else rec.reshape(-1)
    pcm = np.clip(flat, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm16.tobytes())
    print(f"OK: rms={block_rms(flat):.5f}  max={float(np.max(np.abs(flat))):.5f}  → {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba micrófono")
    parser.add_argument("--devices", action="store_true", help="Listar dispositivos")
    parser.add_argument("--info", action="store_true", help="Mostrar ruta de micrófono y salir")
    parser.add_argument("--record", type=float, metavar="SEC", help="Grabar WAV")
    parser.add_argument("-o", default="/tmp/mic_test.wav", help="Salida WAV")
    parser.add_argument("--seconds", type=float, default=None, help="Duración medidor")
    args = parser.parse_args()

    if args.devices:
        list_devices()
        return 0
    if args.info:
        print_mic_route()
        return 0
    if args.record:
        record_wav(Path(args.o), args.record)
        return 0
    try:
        live_meter(args.seconds)
    except KeyboardInterrupt:
        print("\nSalida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
