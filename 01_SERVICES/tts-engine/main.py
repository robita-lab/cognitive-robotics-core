from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io
import logging
from pathlib import Path

from piper_tts_real import PiperTTS

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="TTS Engine", version="1.0")

_BASE = Path(__file__).resolve().parent
tts_engine: PiperTTS | None = None


class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0


@app.on_event("startup")
async def startup():
    global tts_engine
    tts_engine = PiperTTS(config_path=str(_BASE / "config" / "tts_config.json"))


@app.get("/health")
def health():
    model = "es_ES-sharvard-medium.onnx"
    if tts_engine and tts_engine.config.get("voice_model"):
        model = tts_engine.config["voice_model"]
    return {"status": "ok", "model": model, "engine": "piper"}


@app.post("/synthesize")
def synthesize(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "Texto vacío")
    if tts_engine is None:
        raise HTTPException(503, "TTS no inicializado")
    audio_bytes = tts_engine.synthesize_to_bytes(req.text)
    if not audio_bytes:
        raise HTTPException(500, "Error al sintetizar audio")
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")


@app.post("/synthesize-stream")
async def synthesize_stream(req: TTSRequest):
    return synthesize(req)
