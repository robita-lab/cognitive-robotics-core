#!/usr/bin/env python3
"""UDITO — robot físico (cuerpo): wakeword local + cerebro por red."""

from __future__ import annotations

import logging
import os
import queue
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import httpx

_ROOT = Path(__file__).resolve().parents[2]
_KNOWLEDGE = _ROOT / "04_KNOWLEDGE_CORE"
if str(_KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE))
from load_responses import message  # noqa: E402

from robot_common import (
    SERVICES,
    audio_has_speech,
    calibrate_ambient,
    load_detection_cfg,
    play_wav_bytes,
    progress,
    record_question_vad,
    run_voice_assistant,
    save_wav,
    setup_wakeword_path,
    CHUNK_SEC,
)

setup_wakeword_path()
import Detector_wakeword as ww  # noqa: E402

sys.path.insert(0, str(SERVICES / "tts-engine"))
from piper_tts_real import PiperTTS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("udito")

SAMPLE_RATE = ww.SAMPLE_RATE
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)
SERVER_URL = os.getenv("ROBITA_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")


class UditoPhysical:
    def __init__(self) -> None:
        self.cfg = load_detection_cfg()
        self.tts = PiperTTS(config_path=str(SERVICES / "tts-engine" / "config" / "tts_config.json"))
        self.server = SERVER_URL
        self._check_server()
        self.noise_floor, self.ww_baseline = calibrate_ambient(
            ww, SAMPLE_RATE, float(self.cfg["calibrate_secs"]), self.cfg,
        )
        log.info("UDITO físico → cerebro %s", self.server)

    def _check_server(self) -> None:
        try:
            r = httpx.get(f"{self.server}/health", timeout=5.0)
            r.raise_for_status()
        except Exception as e:
            print(f"Sin cerebro en {self.server}: {e}")
            print("Arranca el cerebro: ./scripts/server/brain-docker.sh")
            sys.exit(1)

    def _speak(self, key: str, label: str) -> None:
        text = message(key)
        progress(f"[{label}] {text}")
        wav = self.tts.synthesize_to_bytes(text)
        if wav:
            play_wav_bytes(wav)

    def _query_brain(self, wav_path: str) -> bytes | None:
        with open(wav_path, "rb") as f:
            audio = f.read()
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    f"{self.server}/voice-query",
                    files={"audio": ("pregunta.wav", audio, "audio/wav")},
                )
        except httpx.HTTPError as e:
            log.error("voice-query error: %s", e)
            progress("[error] cerebro no respondió (reinicia launch.sh)")
            self._speak("error", "aviso")
            return None
        if r.status_code != 200:
            log.error("voice-query %s: %s", r.status_code, r.text[:200])
            progress(f"[error] cerebro HTTP {r.status_code}")
            return None
        if r.headers.get("X-Transcribed-Text"):
            progress(f"[stt] {r.headers['X-Transcribed-Text']}")
        intent = r.headers.get("X-Intent", "")
        if r.headers.get("X-Answer"):
            lbl = "despedida" if intent == "goodbye" else "rag"
            progress(f"[{lbl}] {r.headers['X-Answer']}")
        return r.content

    def _on_session(self, audio_q: queue.Queue, speaker_lock=None, pre_roll=None) -> None:
        audio = record_question_vad(
            audio_q, self.noise_floor, self.cfg,
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
            pre_roll=pre_roll,
        )
        if not audio_has_speech(
            audio, self.noise_floor, self.cfg["speech_margin"],
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
        ):
            self._speak("not_understood", "aviso")
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            save_wav(tmp_path, audio, SAMPLE_RATE)
            out = self._query_brain(tmp_path)
            if out:
                progress("[tts] reproduciendo")
                play_wav_bytes(out)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def run(self) -> None:
        print(f"UDITO (robot físico) — cerebro {self.server}\n")
        print(f"Conocimiento: {_KNOWLEDGE / 'responses'}\n")
        run_voice_assistant(
            ww, self.cfg, self.noise_floor, SAMPLE_RATE, CHUNK_SAMPLES,
            on_session=self._on_session,
            greet=lambda: self._speak("greeting", "saludo"),
            ww_baseline=self.ww_baseline,
        )


if __name__ == "__main__":
    UditoPhysical().run()
