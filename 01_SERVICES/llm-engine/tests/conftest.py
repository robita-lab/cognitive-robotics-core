from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.memory.store import InMemoryStore


class FakeLLMClient:
    def __init__(self, canned_reply: str = "hola, soy UDITO") -> None:
        self._reply = canned_reply

    async def complete(self, messages: list[dict], max_tokens: int) -> str:
        return self._reply

    async def stream_complete(self, messages: list[dict], max_tokens: int):
        for chunk in self._reply.split(" "):
            yield chunk + " "

    async def ping(self) -> bool:
        return True

    async def warmup(self) -> None:
        return None

    async def list_models(self) -> list[str]:
        return ["fake-model"]

    async def close(self) -> None:
        return None


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app.state.llm = FakeLLMClient()
    app.state.memory = InMemoryStore()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
