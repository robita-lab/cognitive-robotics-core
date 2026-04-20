"""Conversation memory — rolling window keyed by conversation_id.

Two backends:
  - InMemoryStore: process-local dict, used when REDIS_URL is empty (local tier).
  - RedisStore:    persistent across restarts, TTL'd (server tier).
"""

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

import redis.asyncio as redis


@dataclass(slots=True)
class Turn:
    role: str
    content: str


class MemoryStore(Protocol):
    async def append(self, conversation_id: str, turn: Turn) -> None: ...

    async def window(self, conversation_id: str, size: int | None) -> list[Turn]: ...

    async def reset(self, conversation_id: str) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class InMemoryStore:
    def __init__(self, max_turns: int = 512) -> None:
        self._max_turns = max_turns
        self._data: dict[str, deque[Turn]] = defaultdict(lambda: deque(maxlen=max_turns))

    async def append(self, conversation_id: str, turn: Turn) -> None:
        self._data[conversation_id].append(turn)

    async def window(self, conversation_id: str, size: int | None) -> list[Turn]:
        turns = list(self._data.get(conversation_id, ()))
        return turns[-size:] if size else turns

    async def reset(self, conversation_id: str) -> None:
        self._data.pop(conversation_id, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()


class RedisStore:
    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._client: redis.Redis = redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, conversation_id: str) -> str:
        return f"udito:conv:{conversation_id}"

    async def append(self, conversation_id: str, turn: Turn) -> None:
        key = self._key(conversation_id)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, json.dumps({"role": turn.role, "content": turn.content}))
            pipe.expire(key, self._ttl)
            await pipe.execute()

    async def window(self, conversation_id: str, size: int | None) -> list[Turn]:
        key = self._key(conversation_id)
        start = -size if size else 0
        raw = await self._client.lrange(key, start, -1)
        out: list[Turn] = []
        for item in raw:
            parsed = json.loads(item)
            out.append(Turn(role=parsed["role"], content=parsed["content"]))
        return out

    async def reset(self, conversation_id: str) -> None:
        await self._client.delete(self._key(conversation_id))

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except redis.RedisError:
            return False

    async def close(self) -> None:
        await self._client.aclose()


async def build_store(settings) -> MemoryStore:
    if settings.use_redis:
        return RedisStore(settings.redis_url, settings.memory_ttl_seconds)
    return InMemoryStore()
