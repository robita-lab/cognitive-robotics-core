"""POST /v2/turn — un turno de conversación SIN estado en el servidor (D5).

El robot es la fuente de verdad de la memoria: manda en cada petición el
historial reciente y, si su búsqueda local encontró algo, los fragmentos de
normativa (`context`) para que el LLM redacte una respuesta basada en ellos.

- stream=true (por defecto): SSE con eventos `token` (texto), `done` (JSON
  {text, model, latency_ms, finish}) o `error`.
- stream=false: JSON con los mismos campos.

Cancelación: si el robot cierra la conexión (se canceló la acción Think),
se cancela el generador, se cierra la petición a Ollama y éste deja de
generar. Se registra como "cancelado por el cliente".
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.auth import require_api_key
from app.config import settings
from app.llm.prompts import build_turn_messages

log = logging.getLogger("udito.turn")
router = APIRouter(tags=["turn"], dependencies=[Depends(require_api_key)])


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class Passage(BaseModel):
    source: str = Field("", description="id citable, p. ej. normativa:ACC:7")
    title: str = ""
    text: str = Field(..., max_length=4000)


class TurnRequest(BaseModel):
    session_id: str = Field(..., max_length=128)
    turn_id: str = Field("", max_length=128)
    user_text: str = Field(..., min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=64)
    context: list[Passage] = Field(default_factory=list, max_length=8)
    lang: str = "es"
    max_tokens: int | None = Field(None, ge=1)
    stream: bool = True


class TurnResponse(BaseModel):
    text: str
    model: str
    latency_ms: float
    finish: str = "stop"


def _prepare(body: TurnRequest) -> tuple[list[dict], int]:
    history = [m.model_dump() for m in body.history][-settings.turn_max_history:]
    messages = build_turn_messages(
        body.user_text, history, [p.model_dump() for p in body.context], settings.turn_max_context_chars
    )
    max_tokens = min(body.max_tokens or settings.llm_max_tokens_default, settings.turn_max_tokens_cap)
    return messages, max_tokens


@router.post("/turn", response_model=TurnResponse)
async def turn(request: Request, body: TurnRequest):
    messages, max_tokens = _prepare(body)
    llm = request.app.state.llm
    t0 = time.perf_counter()
    tag = f"{body.session_id}/{body.turn_id}"
    log.info("[%s] turno: %d msgs historial, %d fragmentos, stream=%s",
             tag, len(body.history), len(body.context), body.stream)

    if not body.stream:
        text = await llm.complete(messages=messages, max_tokens=max_tokens)
        return TurnResponse(text=text.strip(), model=settings.llm_model,
                            latency_ms=(time.perf_counter() - t0) * 1000)

    async def events() -> AsyncIterator[dict]:
        collected: list[str] = []
        try:
            async for token in llm.stream_complete(messages=messages, max_tokens=max_tokens):
                collected.append(token)
                yield {"event": "token", "data": token}
            done = {"text": "".join(collected).strip(), "model": settings.llm_model,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "finish": "stop"}
            log.info("[%s] terminado en %.0f ms (%d trozos)", tag, done["latency_ms"], len(collected))
            yield {"event": "done", "data": json.dumps(done, ensure_ascii=False)}
        except asyncio.CancelledError:
            log.info("[%s] cancelado por el cliente tras %d trozos: generación abortada", tag, len(collected))
            raise
        except Exception as exc:  # noqa: BLE001 — el robot recurre a su respuesta local
            log.warning("[%s] error del LLM: %s", tag, exc)
            yield {"event": "error", "data": json.dumps({"error": str(exc)[:300]}, ensure_ascii=False)}

    return EventSourceResponse(events(), ping=15)
