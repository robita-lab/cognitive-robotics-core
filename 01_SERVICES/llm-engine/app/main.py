import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, health
from app.config import settings
from app.llm.openai_compat import OpenAICompatClient
from app.memory.store import build_store

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("udito.server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("Starting UDITO LLM server (tier=%s, model=%s)", settings.tier, settings.llm_model)

    app.state.llm = OpenAICompatClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )
    app.state.memory = await build_store(settings)

    if settings.llm_warmup_on_start:
        try:
            await app.state.llm.warmup()
            log.info("LLM warm-up complete")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "LLM warm-up failed: %s — server continues, first turn will pay cold-start",
                exc,
            )

    try:
        yield
    finally:
        await app.state.llm.close()
        await app.state.memory.close()
        log.info("UDITO LLM server stopped")


app = FastAPI(title="UDITO LLM Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/v1")
app.include_router(conversations.router, prefix="/v1")
