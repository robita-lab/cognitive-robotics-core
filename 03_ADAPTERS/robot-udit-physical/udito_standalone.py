#!/usr/bin/env python3
"""UDITO standalone — todo en un PC (sin Docker cerebro). Optimizado para Jetson 8GB."""

from __future__ import annotations

import logging
import os
import queue
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "03_ADAPTERS" / "robot-udit-physical") not in sys.path:
    sys.path.insert(0, str(_ROOT / "03_ADAPTERS" / "robot-udit-physical"))

from jetson_memory import apply_low_memory_env, low_memory_mode, release_models_after_stt, release_ram  # noqa: E402
from log_config import apply_log_config, verbose_mode  # noqa: E402

apply_low_memory_env()
apply_log_config()
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

_KNOWLEDGE = _ROOT / "04_KNOWLEDGE_CORE"
if str(_KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE))
from load_responses import (  # noqa: E402
    is_goodbye,
    match_fun_request,
    message,
    random_fun_fact,
    random_joke,
    repair_stt_garbled,
    sanitize_user_transcript,
    shorten_for_voice,
    transcript_seems_unusable,
)

from udito_speech import emotion_for_rag, speak, speak_joke_with_laugh  # noqa: E402
from robot_common import (  # noqa: E402
    SERVICES,
    audio_has_speech,
    calibrate_ambient,
    drain_queue,
    load_detection_cfg,
    play_wav_bytes,
    progress,
    record_question_vad,
    run_voice_assistant,
    save_wav,
    setup_wakeword_path,
    user_progress,
    status_line,
    CHUNK_SEC,
)

log = logging.getLogger("udito.standalone")


class UditoStandalone:
  def __init__(self) -> None:
    self.cfg = load_detection_cfg()
    self._stt = None
    self._rag = None
    self._rag_ready = False
    self._tts = None
    self._ww = None
    self.noise_floor = 0.0

  def _tts_engine(self):
    if self._tts is None:
      sys.path.insert(0, str(SERVICES / "tts-engine"))
      from piper_tts_real import PiperTTS
      tts_cfg = os.getenv(
        "ROBITA_TTS_CONFIG",
        str(SERVICES / "tts-engine" / "config" / "tts_config.json"),
      )
      self._tts = PiperTTS(config_path=tts_cfg)
    return self._tts

  def _wakeword(self):
    if self._ww is None:
      setup_wakeword_path()
      import Detector_wakeword as ww  # noqa: WPS433
      self._ww = ww
    return self._ww

  def _stt_engine(self):
    if self._stt is None:
      sys.path.insert(0, str(SERVICES / "stt-engine"))
      from whisper_stt import WhisperSTT
      self._stt = WhisperSTT(
        config_path=str(SERVICES / "stt-engine" / "config" / "STT_config.json"),
        project_root=str(SERVICES / "stt-engine"),
      )
    return self._stt

  def _rag_engine(self):
    if self._rag is None:
      sys.path.insert(0, str(SERVICES / "rag-engine"))
      from rag_system import RAGSystem
      os.chdir(SERVICES / "rag-engine")
      rag_cfg = os.getenv(
        "ROBITA_RAG_CONFIG",
        str(SERVICES / "rag-engine" / "config" / "rag_config.json"),
      )
      self._rag = RAGSystem(
        config_path=rag_cfg,
        settings_path=str(SERVICES / "rag-engine" / "config" / "settings.json"),
      )
    return self._rag

  def _ensure_rag(self) -> None:
    if self._rag_ready:
      return
    progress("[carga] RAG (índice + embeddings)…")
    rebuild = os.getenv("ROBITA_RAG_REBUILD", "0").strip().lower() in ("1", "true", "yes")
    self._rag_engine().initialize(force_rebuild=rebuild)
    self._rag_ready = True
    if verbose_mode():
      release_ram("RAG listo")

  def _bootstrap(self) -> None:
    """RAG → TTS → wakeword → STT (precargado)."""
    if verbose_mode():
      progress("")
      progress("=== Arranque UDITO ===")
      progress("[1/4] RAG…")
      self._ensure_rag()
      progress("[2/4] TTS (Piper)…")
      self._tts_engine()
      progress("[3/4] Wakeword…")
      ww = self._wakeword()
      if hasattr(ww, "load"):
        ww.load()
      progress("[4/4] Whisper (STT en RAM)…")
      self._stt_engine()._ensure_model()
      progress("=== Listo para escuchar ===")
      progress("")
    else:
      status_line("UDITO · cargando modelos locales…", end="\r")
      self._ensure_rag()
      self._tts_engine()
      ww = self._wakeword()
      if hasattr(ww, "load"):
        ww.load()
      self._stt_engine()._ensure_model()
      status_line("UDITO · listo — di «udito» para activar          ")

  def _speak_key(self, key: str, label: str, emotion: str = "neutral") -> None:
    text = message(key)
    speak(
      self._tts_engine(),
      text,
      emotion=emotion,
      source="fixed",
      label=label,
      play_fn=play_wav_bytes,
      progress_fn=user_progress,
    )

  def _speak_text(
    self,
    text: str,
    label: str = "tts",
    *,
    emotion: str = "helpful",
    source: str = "tts",
  ) -> None:
    speak(
      self._tts_engine(),
      text,
      emotion=emotion,
      source=source,
      label=label,
      play_fn=play_wav_bytes,
      progress_fn=user_progress,
    )

  def _handle_fun_request(self, kind: str) -> bool:
    if kind == "joke":
      speak_joke_with_laugh(
        self._tts_engine(),
        random_joke(),
        play_fn=play_wav_bytes,
        progress_fn=user_progress,
      )
      return True
    if kind == "curious_fact":
      self._speak_text(
        random_fun_fact(),
        "dato_curioso",
        emotion="happy",
        source="fun_fact",
      )
      return True
    return False

  def _process_text(self, text: str) -> bool:
    if not self._rag_ready:
      raise RuntimeError("RAG no cargado — reinicia el pipeline")
    raw = text.strip()
    text = sanitize_user_transcript(raw)
    if raw != text:
      progress(f"[stt limpio] {text or '(vacío)'}")
    if not text or len(text) < int(self.cfg.get("min_question_chars", 6)):
      self._speak_key("not_understood", "aviso", emotion="sorry")
      return True
    progress(f"[texto] {text}", always=True)
    if is_goodbye(text):
      self._speak_key("farewell", "despedida", emotion="happy")
      return False
    fun_kind = match_fun_request(text)
    if fun_kind:
      if self._handle_fun_request(fun_kind):
        return True
    progress("[proceso] …")
    result = self._rag_engine().process_query(text)
    answer = (result.get("answer") or "").strip()
    if not answer:
      self._speak_key("not_found", "aviso", emotion="sorry")
      return True
    src = result.get("source", "")
    if src == "fun_joke" or result.get("needs_laugh"):
      speak_joke_with_laugh(
        self._tts_engine(),
        shorten_for_voice(answer),
        play_fn=play_wav_bytes,
        progress_fn=user_progress,
      )
      return True
    if src == "fun_fact":
      self._speak_text(
        shorten_for_voice(answer),
        "dato_curioso",
        emotion="happy",
        source="fun_fact",
      )
      return True
    emotion = result.get("emotion") or emotion_for_rag(src)
    if src in ("rag", "fixed_udit_address"):
      spoken = shorten_for_voice(answer, max_sentences=4, max_chars=380)
    else:
      spoken = shorten_for_voice(answer)
    self._speak_text(spoken, "rag", emotion=emotion, source=src)
    return True

  def _transcribe(self, audio, ww) -> str | None:
    stt = self._stt_engine()
    stt._ensure_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
      tmp_path = tmp.name
    try:
      save_wav(tmp_path, audio, ww.SAMPLE_RATE)
      result = stt.transcribe(tmp_path)
    finally:
      try:
        os.unlink(tmp_path)
      except OSError:
        pass
    if not result or not result.get("text", "").strip():
      return None
    return result["text"].strip()

  def _release_stt_if_needed(self) -> None:
    if not (low_memory_mode() and release_models_after_stt()):
      return
    stt = self._stt
    if stt is not None:
      stt.release_model()
      release_ram("STT liberado")

  def _check_speaker(self, audio, speaker_lock, ww) -> bool:
    if speaker_lock is None or not speaker_lock.ready:
      return True
    ok, sim = speaker_lock.verify(audio)
    if ok:
      return True
    progress(f"[sesión] otra voz — no respondo (no es quien activó)")
    return False

  def _session_followup_enabled(self) -> bool:
    return os.getenv("ROBITA_SESSION_FOLLOWUP", "0").strip().lower() in ("1", "true", "yes")

  def _on_session(self, audio_q: queue.Queue, speaker_lock=None, pre_roll=None) -> None:
    ww = self._wakeword()
    chunk_samples = int(ww.SAMPLE_RATE * CHUNK_SEC)
    audio = record_question_vad(
      audio_q, self.noise_floor, self.cfg,
      ww.SAMPLE_RATE, chunk_samples, ww.THRESHOLD_VOICE,
      pre_roll=pre_roll,
      speaker_lock=speaker_lock,
    )
    if not audio_has_speech(
      audio, self.noise_floor, self.cfg["speech_margin"],
      ww.SAMPLE_RATE, chunk_samples, ww.THRESHOLD_VOICE,
    ):
      if speaker_lock is not None and speaker_lock.ready:
        progress("[sesión] voz de fondo ignorada — di «udito» de nuevo")
        return
      self._speak_key("not_understood", "aviso")
      return
    if not self._check_speaker(audio, speaker_lock, ww):
      return
    audio_sec = float(audio.size) / float(ww.SAMPLE_RATE)
    text = self._transcribe(audio, ww)
    self._release_stt_if_needed()
    if not text:
      self._speak_key("not_understood", "aviso")
      return
    text = repair_stt_garbled(text)
    progress(f"[stt] {text}", always=True)
    cleaned = sanitize_user_transcript(text) or text
    if transcript_seems_unusable(cleaned, audio_sec):
      progress("[stt] audio corto o poco claro — pide repetir", always=True)
      self._speak_key("not_understood", "aviso")
      return
    if not self._process_text(cleaned):
      return
    if not self._session_followup_enabled():
      progress("[sesión] fin — di «udito» para otra pregunta", always=True)
      return
    progress("[seguimiento] otra pregunta o despídete")
    drain_queue(audio_q, 1.0)
    audio2 = record_question_vad(
      audio_q, self.noise_floor, self.cfg,
      ww.SAMPLE_RATE, chunk_samples, ww.THRESHOLD_VOICE,
      speaker_lock=speaker_lock,
    )
    if not audio_has_speech(
      audio2, self.noise_floor, self.cfg["speech_margin"],
      ww.SAMPLE_RATE, int(ww.SAMPLE_RATE * CHUNK_SEC), ww.THRESHOLD_VOICE,
    ):
      return
    if not self._check_speaker(audio2, speaker_lock, ww):
      return
    text2 = self._transcribe(audio2, ww)
    self._release_stt_if_needed()
    if text2:
      progress(f"[stt] {text2}")
      self._process_text(sanitize_user_transcript(text2) or text2)

  def run(self) -> None:
    if verbose_mode():
      print(f"UDITO standalone ({'bajo consumo' if low_memory_mode() else 'estándar'})\n")
      print(f"Conocimiento: {_KNOWLEDGE / 'responses'}\n")
    self._bootstrap()
    ww = self._wakeword()
    self.noise_floor, ww_baseline = calibrate_ambient(
      ww, ww.SAMPLE_RATE, float(self.cfg["calibrate_secs"]), self.cfg,
    )
    run_voice_assistant(
      ww, self.cfg, self.noise_floor, ww.SAMPLE_RATE, int(ww.SAMPLE_RATE * CHUNK_SEC),
      ww_baseline=ww_baseline,
      on_session=self._on_session,
      greet=lambda: self._speak_key("greeting", "saludo", emotion="helpful"),
    )


if __name__ == "__main__":
  UditoStandalone().run()
