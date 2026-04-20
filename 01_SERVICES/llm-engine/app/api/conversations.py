from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["conversations"])


class TurnView(BaseModel):
    role: str
    content: str


class ConversationView(BaseModel):
    conversation_id: str
    turns: list[TurnView]


@router.get("/conversations/{conversation_id}", response_model=ConversationView)
async def get_conversation(conversation_id: str, request: Request) -> ConversationView:
    turns = await request.app.state.memory.window(conversation_id, size=None)
    return ConversationView(
        conversation_id=conversation_id,
        turns=[TurnView(role=t.role, content=t.content) for t in turns],
    )


@router.delete("/conversations/{conversation_id}")
async def reset_conversation(conversation_id: str, request: Request) -> dict:
    await request.app.state.memory.reset(conversation_id)
    return {"conversation_id": conversation_id, "reset": True}
