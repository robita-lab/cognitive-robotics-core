from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import base64
import httpx
import io
import logging
import os
import sys
from pathlib import Path

_KNOWLEDGE = Path(__file__).resolve().parents[2] / "04_KNOWLEDGE_CORE"
if str(_KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE))
from load_responses import is_goodbye, message  # noqa: E402

app = FastAPI(title="Pipeline Orchestrator", version="1.0")

STT_URL = os.getenv("STT_URL", "http://127.0.0.1:8001")
TTS_URL = os.getenv("TTS_URL", "http://127.0.0.1:8002")
WW_URL = os.getenv("WW_URL", "http://127.0.0.1:8003")
RAG_URL = os.getenv("RAG_URL", "http://127.0.0.1:8004")
TIMEOUT = httpx.Timeout(120.0)


def _header_value(text: str, max_len: int = 200) -> str:
    """Cabeceras HTTP solo ASCII en una línea (evita crash de Starlette)."""
    clean = " ".join((text or "").split())
    return clean.encode("ascii", "replace").decode("ascii")[:max_len]


@app.get("/health")
def health():
    return {"status": "ok", "services": [STT_URL, TTS_URL, WW_URL, RAG_URL]}


@app.get("/services/status")
async def services_status():
    results = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in [("stt", STT_URL), ("tts", TTS_URL), ("wakeword", WW_URL), ("rag", RAG_URL)]:
            try:
                r = await client.get(f"{url}/health")
                results[name] = r.json()
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}
    return results


@app.post("/voice-query")
async def voice_query(audio: UploadFile = File(...), collection: str = "general"):
    audio_bytes = await audio.read()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        stt_resp = await client.post(
            f"{STT_URL}/transcribe",
            files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
        )
        stt_resp.raise_for_status()
        text = stt_resp.json()["text"]
        logging.info("STT → '%s'", text)
        if not text.strip():
            raise HTTPException(400, "No se detectó texto en el audio")

        if is_goodbye(text):
            answer = message("farewell")
            tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
            tts_resp.raise_for_status()
            return StreamingResponse(
                io.BytesIO(tts_resp.content),
                media_type="audio/wav",
                headers={
                    "X-Transcribed-Text": _header_value(text),
                    "X-Answer": _header_value(answer),
                    "X-Intent": "goodbye",
                },
            )

        route_resp = await client.post(f"{RAG_URL}/route", json={"text": text})
        routed_collection = route_resp.json().get("collection", collection)

        rag_resp = await client.post(
            f"{RAG_URL}/query",
            json={"text": text, "collection": routed_collection},
        )
        rag_resp.raise_for_status()
        answer = rag_resp.json()["answer"]

        tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
        tts_resp.raise_for_status()
        audio_out = tts_resp.content

    return StreamingResponse(
        io.BytesIO(audio_out),
        media_type="audio/wav",
        headers={"X-Transcribed-Text": _header_value(text), "X-Answer": _header_value(answer)},
    )


class TextQuery(BaseModel):
    text: str
    collection: str = "general"
    respond_with_audio: bool = False


@app.post("/text-query")
async def text_query(req: TextQuery):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if is_goodbye(req.text):
            answer = message("farewell")
            result = {"answer": answer, "collection": "goodbye", "input": req.text, "intent": "goodbye"}
            if req.respond_with_audio:
                tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
                result["audio_base64"] = base64.b64encode(tts_resp.content).decode()
            return result

        route_resp = await client.post(f"{RAG_URL}/route", json={"text": req.text})
        col = route_resp.json().get("collection", req.collection)

        rag_resp = await client.post(f"{RAG_URL}/query", json={"text": req.text, "collection": col})
        rag_resp.raise_for_status()
        answer = rag_resp.json()["answer"]

        result = {"answer": answer, "collection": col, "input": req.text}

        if req.respond_with_audio:
            tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
            result["audio_base64"] = base64.b64encode(tts_resp.content).decode()

    return result
