"""
Bip/loop de «pensando» mientras STT o RAG procesan (Fase 1).
Reproduce Clock1.mp3 en bucle con GStreamer hasta stop().
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from robot_common import progress, resolve_pulse_sink, verbose_progress

log = logging.getLogger("udito.processing_cue")

_ADAPTER = Path(__file__).resolve().parent
DEFAULT_SOUND = _ADAPTER / "assets" / "audio" / "Clock1.mp3"


def processing_cue_enabled() -> bool:
    return os.getenv("ROBITA_PROCESSING_CUE", "1").strip().lower() not in ("0", "false", "no", "off")


def clock_sound_path() -> Path | None:
    raw = os.getenv("ROBITA_PROCESSING_SOUND", "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p
    if DEFAULT_SOUND.is_file():
        return DEFAULT_SOUND
    return None


def _volume() -> float:
    try:
        return float(os.getenv("ROBITA_PROCESSING_VOLUME", "0.35"))
    except ValueError:
        return 0.35


def _gst_play_cmd(path: Path) -> list[str]:
    sink = resolve_pulse_sink(os.getenv("ROBITA_AUDIO_OUTPUT", ""))
    vol = _volume()
    loc = str(path.resolve())
    cmd = [
        "gst-launch-1.0", "-q",
        "filesrc", f"location={loc}",
        "!", "decodebin",
        "!", "audioconvert",
        "!", "volume", f"volume={vol}",
        "!", "pulsesink",
    ]
    if sink:
        cmd.extend(["device", sink])
    return cmd


class ProcessingCue:
    """Reproduce sonido de carga en segundo plano; llamar stop() antes de hablar."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self._active = False

    def start(self) -> bool:
        if not processing_cue_enabled():
            return False
        path = clock_sound_path()
        if path is None:
            log.warning("No hay sonido de procesamiento (Clock1.mp3)")
            return False
        if self._active:
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(path,), daemon=True)
        self._thread.start()
        self._active = True
        if verbose_progress():
            progress("[proceso] pensando…")
        return True

    def stop(self) -> None:
        if not self._active:
            return
        self._stop.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
        self._proc = None
        self._thread = None
        self._active = False

    def _loop(self, path: Path) -> None:
        cmd = _gst_play_cmd(path)
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as e:
                log.debug("processing cue: %s", e)
                break
            while not self._stop.is_set():
                proc = self._proc
                if proc is None:
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
            if self._stop.is_set():
                proc = self._proc
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                break
            time.sleep(0.05)

    def __enter__(self) -> ProcessingCue:
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
