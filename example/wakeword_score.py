#!/usr/bin/env python3
"""
Prueba wakeword sobre grabación — sin mic en vivo.

  ./example/wakeword_score.py                    # graba 4 s y puntúa
  ./example/wakeword_score.py /tmp/mic_test.wav  # puntúa un WAV
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "01_SERVICES/wakeword-engine"))
sys.path.insert(0, str(ROOT / "03_ADAPTERS/robot-udit-physical"))

from robot_common import block_rms, setup_wakeword_path, wake_phrase  # noqa: E402


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


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return raw.astype(np.float32) / 32768.0, rate


def score(path: Path) -> None:
    _load_env()
    setup_wakeword_path()
    import Detector_wakeword as ww  # noqa: WPS433
    from engine import get_engine

    ww.load()
    eng = get_engine()
    phrase = wake_phrase()
    prob_min = float(os.getenv("ROBITA_DEMO_WW_THRESHOLD", "") or getattr(ww, "WAKEWORD_THRESHOLD", 0.35))
    audio, rate = load_wav(path)
    if rate != ww.SAMPLE_RATE:
        from robot_common import resample_mono
        audio = resample_mono(audio, rate, ww.SAMPLE_RATE)
    b = int(ww.SAMPLE_RATE * ww.BLOCK_DURATION)
    eng._model.reset()
    peaks: list[tuple[int, float, float]] = []
    for i in range(0, max(1, len(audio) - b), b // 2):
        chunk = audio[i : i + b]
        if chunk.size < b:
            break
        rms = block_rms(chunk)
        prob = float(ww.run_inference(chunk))
        if rms > 0.003 or prob > 0.001:
            peaks.append((i, rms, prob))
    best = max((p[2] for p in peaks), default=0.0)
    print(f"Archivo: {path}")
    print(f"Wakeword: «{phrase}»  modelo: {eng._model_path().name}")
    print(f"Duración: {len(audio)/ww.SAMPLE_RATE:.1f}s  pico prob={best:.6f}")
    print("\nMomentos con voz o prob>0:")
    for i, rms, prob in peaks[-30:]:
        t = i / ww.SAMPLE_RATE
        mark = " <<< DISPARA" if prob >= prob_min else ""
        print(f"  t={t:5.2f}s  rms={rms:.4f}  prob={prob:.6f}{mark}")
    print(f"\nUmbral demo: {prob_min:.2f}")
    if best < prob_min and best >= 0.015:
        print(
            f"Tu pico ({best:.3f}) está cerca — prueba:\n"
            f"  ROBITA_DEMO_WW_THRESHOLD={best * 0.85:.3f} ./example/run.sh"
        )
    elif best < 0.015:
        print(
            "\nAVISO: pico muy bajo — prueba decir «hey jarvis» en INGLÉS, "
            "más cerca del mic, o revisa ./example/mic_test.py --record 5"
        )


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", nargs="?", help="WAV mono 16 kHz (opcional)")
    parser.add_argument("--record", type=float, default=4.0, help="Segundos si no hay WAV")
    args = parser.parse_args()

    if args.wav:
        score(Path(args.wav))
        return 0

    wav = Path("/tmp/wakeword_test.wav")
    py = ROOT / "example/mic_test.py"
    print(f"Grabando {args.record:.0f} s — di «hey jarvis» en inglés…\n")
    subprocess.run([sys.executable, str(py), "--record", str(args.record), "-o", str(wav)], check=True)
    print()
    score(wav)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
