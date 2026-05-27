import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

from fastapi import FastAPI, UploadFile, File
from fastapi.websockets import WebSocket
import io
import logging
import wave

import numpy as np

from Detector_wakeword import run_inference, WAKEWORD_THRESHOLD, SAMPLE_RATE

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Wakeword Engine", version="1.0")


def _audio_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        sr = wf.getframerate()
    if sr != SAMPLE_RATE and len(audio) > 1:
        indices = np.linspace(0, len(audio) - 1, int(len(audio) * SAMPLE_RATE / sr))
        audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def _detect_from_bytes(audio_bytes: bytes) -> tuple[bool, float]:
    if not audio_bytes:
        return False, 0.0
    try:
        audio = _audio_bytes_to_float32(audio_bytes)
    except Exception:
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size == 0:
        return False, 0.0
    block = audio[-SAMPLE_RATE:] if audio.size > SAMPLE_RATE else audio
    prob = run_inference(block)
    detected = prob >= WAKEWORD_THRESHOLD
    return detected, float(prob)


@app.get("/health")
def health():
    return {"status": "ok", "engine": "tflite", "threshold": WAKEWORD_THRESHOLD}


@app.post("/detect")
async def detect(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    detected, confidence = _detect_from_bytes(audio_bytes)
    return {"detected": detected, "confidence": confidence}


@app.websocket("/stream")
async def stream_detection(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            detected, confidence = _detect_from_bytes(audio_chunk)
            await websocket.send_json({"detected": detected, "confidence": confidence})
    except Exception as e:
        logging.info("WebSocket cerrado: %s", e)
