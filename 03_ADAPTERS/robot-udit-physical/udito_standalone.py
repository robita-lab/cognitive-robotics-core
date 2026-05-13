#!/usr/bin/env python3
"""UDITO standalone — todo en un PC (sin Docker cerebro)."""

from __future__ import annotations

import logging
import os
import queue
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

_ROOT = Path(__file__).resolve().parents[2]
_KNOWLEDGE = _ROOT / "04_KNOWLEDGE_CORE"
if str(_KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE))
from load_responses import is_goodbye, message, shorten_for_voice  # noqa: E402

from robot_common import (
    SERVICES,
    audio_has_speech,
    calibrate_noise_floor,
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

for sub in ("stt-engine", "tts-engine", "rag-engine"):
    p = str(SERVICES / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from piper_tts_real import PiperTTS  # noqa: E402
from rag_system import RAGSystem  # noqa: E402
from whisper_stt import WhisperSTT  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("udito.standalone")

SAMPLE_RATE = ww.SAMPLE_RATE
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)


class UditoStandalone:
    def __init__(self) -> None:
        self.cfg = load_detection_cfg()
        self.tts = PiperTTS(config_path=str(SERVICES / "tts-engine" / "config" / "tts_config.json"))
        self.stt = WhisperSTT(
            config_path=str(SERVICES / "stt-engine" / "config" / "STT_config.json"),
            project_root=str(SERVICES / "stt-engine"),
        )
        os.chdir(SERVICES / "rag-engine")
        self.rag = RAGSystem(
            config_path=str(SERVICES / "rag-engine" / "config" / "rag_config.json"),
            settings_path=str(SERVICES / "rag-engine" / "config" / "settings.json"),
        )
        log.info("Cargando STT y RAG...")
        self.stt._ensure_model()
        self.rag.initialize(force_rebuild=False)
        self.noise_floor = calibrate_noise_floor(SAMPLE_RATE, float(self.cfg["calibrate_secs"]))

    def _speak_key(self, key: str, label: str) -> None:
        text = message(key)
        progress(f"[{label}] {text}")
        wav = self.tts.synthesize_to_bytes(text)
        if wav:
            play_wav_bytes(wav)

    def _speak_text(self, text: str, label: str = "tts") -> None:
        progress(f"[{label}] {text}")
        wav = self.tts.synthesize_to_bytes(text)
        if wav:
            play_wav_bytes(wav)

    def _process_text(self, text: str) -> bool:
        progress(f"[stt] {text}")
        if is_goodbye(text):
            self._speak_key("farewell", "despedida")
            return False
        answer = (self.rag.process_query(text).get("answer") or "").strip()
        if not answer:
            self._speak_key("not_found", "aviso")
            return True
        spoken = shorten_for_voice(answer)
        self._speak_text(spoken, "rag")
        return True

    def _transcribe(self, audio) -> str | None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            save_wav(tmp_path, audio, SAMPLE_RATE)
            result = self.stt.transcribe(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if not result or not result.get("text", "").strip():
            return None
        return result["text"].strip()

    def _on_session(self, audio_q: queue.Queue) -> None:
        audio = record_question_vad(
            audio_q, self.noise_floor, self.cfg,
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
        )
        if not audio_has_speech(
            audio, self.noise_floor, self.cfg["speech_margin"],
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
        ):
            self._speak_key("not_understood", "aviso")
            return
        text = self._transcribe(audio)
        if not text:
            self._speak_key("not_understood", "aviso")
            return
        if not self._process_text(text):
            return
        progress("[seguimiento] otra pregunta o despídete")
        audio2 = record_question_vad(
            audio_q, self.noise_floor, self.cfg,
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
        )
        if not audio_has_speech(
            audio2, self.noise_floor, self.cfg["speech_margin"],
            SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
        ):
            return
        text2 = self._transcribe(audio2)
        if text2:
            self._process_text(text2)

    def run(self) -> None:
        print("UDITO standalone (todo local)\n")
        print(f"Conocimiento: {_KNOWLEDGE / 'responses'}\n")
        run_voice_assistant(
            ww, self.cfg, self.noise_floor, SAMPLE_RATE, CHUNK_SAMPLES,
            on_session=self._on_session,
            greet=lambda: self._speak_key("greeting", "saludo"),
        )


if __name__ == "__main__":
    UditoStandalone().run()
