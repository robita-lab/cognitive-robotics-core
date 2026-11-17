from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "tier": settings.tier}


@router.get("/readyz")
async def readyz(request: Request) -> dict:
    llm_ok = await request.app.state.llm.ping()
    memory_ok = await request.app.state.memory.ping()
    ready = llm_ok and memory_ok
    return {
        "ready": ready,
        "llm": llm_ok,
        "memory": memory_ok,
        "model": settings.llm_model,
        "tier": settings.tier,
    }


@router.get("/v1/models")
async def models(request: Request) -> dict:
    return {"default": settings.llm_model, "available": await request.app.state.llm.list_models()}
