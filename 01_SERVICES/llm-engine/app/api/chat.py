from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.llm.prompts import get_persona
from app.memory.store import Turn

router = APIRouter(tags=["chat"])


class ContextTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: str = Field(..., description="Caller-chosen stable id; keyed in memory store.")
    user_text: str
    persona: str = "default"
    max_tokens: int | None = None
    recent_context: list[ContextTurn] = Field(
        default_factory=list,
        description="Optional carry-over from another tier; merged into stored memory.",
    )


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    tier: str


async def _build_messages(request: Request, body: ChatRequest) -> list[dict]:
    memory = request.app.state.memory
    for ctx in body.recent_context:
        await memory.append(body.conversation_id, Turn(role=ctx.role, content=ctx.content))

    history = await memory.window(body.conversation_id, size=settings.memory_window_size)

    messages: list[dict] = [{"role": "system", "content": get_persona(body.persona)}]
    messages.extend([{"role": t.role, "content": t.content} for t in history])
    messages.append({"role": "user", "content": body.user_text})
    return messages


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    messages = await _build_messages(request, body)
    reply = await request.app.state.llm.complete(
        messages=messages,
        max_tokens=body.max_tokens or settings.llm_max_tokens_default,
    )

    memory = request.app.state.memory
    await memory.append(body.conversation_id, Turn(role="user", content=body.user_text))
    await memory.append(body.conversation_id, Turn(role="assistant", content=reply))

    return ChatResponse(
        conversation_id=body.conversation_id,
        reply=reply,
        model=settings.llm_model,
        tier=settings.tier,
    )


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> EventSourceResponse:
    messages = await _build_messages(request, body)
    max_tokens = body.max_tokens or settings.llm_max_tokens_default

    async def event_source() -> AsyncIterator[dict]:
        collected: list[str] = []
        stream = request.app.state.llm.stream_complete(messages=messages, max_tokens=max_tokens)
        async for token in stream:
            collected.append(token)
            yield {"event": "token", "data": token}

        reply = "".join(collected)
        memory = request.app.state.memory
        await memory.append(body.conversation_id, Turn(role="user", content=body.user_text))
        await memory.append(body.conversation_id, Turn(role="assistant", content=reply))

        yield {
            "event": "done",
            "data": reply,
        }

    return EventSourceResponse(event_source())
