#!/usr/bin/env python3
"""
Módulo STT (Speech-to-Text) con Faster-Whisper.
Pensado para uso en KnowledgeAssist-AI / voice-assistant.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("voice_assistant.stt")

# Configuración por defecto si no existe archivo
DEFAULT_STT_CONFIG = {
    "stt": {
        "engine": "faster-whisper",
        "model_name": "small",
        "device": "cpu",
        "compute_type": "int8",
        "beam_size": 5,
        "language": "es",
    },
    "audio_capture": {
        "sample_rate": 16000,
        "channels": 1,
    },
}


class WhisperSTT:
    """Wrapper de Faster-Whisper para transcripción de audio."""

    def __init__(self, config_path: str = "config/STT_config.json", project_root: Optional[str] = None):
        self.config_path = config_path
        self._root = Path(project_root).resolve() if project_root else Path(config_path).resolve().parent.parent
        self.config = self._load_config()
        self._model = None
        logger.info("WhisperSTT inicializado (modelo cargado bajo demanda)")

    def _load_config(self) -> Dict[str, Any]:
        path = Path(self.config_path)
        if not path.is_absolute():
            path = self._root / self.config_path
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                logger.info("Config STT cargada desde %s", path)
                return cfg
            except Exception as e:
                logger.warning("Error cargando STT config: %s; usando valores por defecto", e)
        return DEFAULT_STT_CONFIG

    def _ensure_model(self):
        if self._model is not None:
            return
        try:
            import os
            from faster_whisper import WhisperModel
            stt = self.config.get("stt", {})
            model_name = os.getenv("WHISPER_MODEL") or stt.get("model_name", "small")
            self._model = WhisperModel(
                model_name,
                device=stt.get("device", "cpu"),
                compute_type=stt.get("compute_type", "int8"),
            )
            logger.info("Modelo Whisper cargado: %s", model_name)
        except Exception as e:
            logger.exception("Error cargando Whisper: %s", e)
            raise

    def release_model(self) -> None:
        """Libera Whisper de RAM (útil en Jetson tras transcribir)."""
        if self._model is None:
            return
        try:
            del self._model
        except Exception:
            pass
        self._model = None
        import gc
        gc.collect()
        logger.info("Modelo Whisper liberado de RAM")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Transcribe un archivo de audio (WAV, etc.).
        Devuelve {"text": "..."} o None si falla.
        """
        self._ensure_model()
        lang = language or self.config.get("stt", {}).get("language", "es")
        beam_size = self.config.get("stt", {}).get("beam_size", 5)
        try:
            segments, _ = self._model.transcribe(
                audio_path,
                beam_size=beam_size,
                language=lang,
                condition_on_previous_text=False,
                vad_filter=True,
                compression_ratio_threshold=2.2,
                log_prob_threshold=-0.8,
                no_speech_threshold=0.55,
            )
            text = " ".join(s.text for s in segments).strip()
            if self.config.get("postprocessing", {}).get("strip_whitespace", True):
                text = text.strip()
            return {"text": text} if text else None
        except Exception as e:
            logger.error("Transcripción fallida %s: %s", audio_path, e)
            return None
