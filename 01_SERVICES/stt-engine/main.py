from fastapi import FastAPI, UploadFile, File, HTTPException
import logging
import os
import tempfile
from pathlib import Path

from whisper_stt import WhisperSTT

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="STT Engine", version="1.0")

_BASE = Path(__file__).resolve().parent
stt_engine: WhisperSTT | None = None


@app.on_event("startup")
async def load_model():
    global stt_engine
    config = _BASE / "config" / "STT_config.json"
    stt_engine = WhisperSTT(config_path=str(config), project_root=str(_BASE))
    stt_engine._ensure_model()
    logging.info("STT listo (faster-whisper)")


@app.get("/health")
def health():
    model = os.getenv("WHISPER_MODEL", "small")
    if stt_engine and stt_engine.config.get("stt", {}).get("model_name"):
        model = stt_engine.config["stt"]["model_name"]
    return {"status": "ok", "model": model, "engine": "faster-whisper"}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = "es"):
    if stt_engine is None:
        raise HTTPException(503, "Modelo no cargado")
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        result = stt_engine.transcribe(tmp_path, language=language)
        if not result:
            raise HTTPException(422, "No se pudo transcribir el audio")
        return {"text": result["text"], "language": language, "segments": []}
    finally:
        os.unlink(tmp_path)
