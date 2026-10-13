"""OpenAI-compatible client — works with Ollama, llama.cpp-server, vLLM, TGI.

Keeps the surface minimal: chat completions + streaming + a couple of probes.
Swap backends by changing LLM_BASE_URL; no code change needed.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

log = logging.getLogger(__name__)


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def complete(self, messages: list[dict], max_tokens: int) -> str:
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": messages,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def stream_complete(self, messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json={
                "model": self._model,
                "messages": messages,
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    log.warning("Skipping malformed SSE payload: %r", payload)
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta

    async def ping(self) -> bool:
        try:
            resp = await self._client.get("/models", timeout=5.0)
            return resp.status_code < 500
        except httpx.HTTPError as exc:
            log.debug("LLM ping failed: %s", exc)
            return False

    async def warmup(self) -> None:
        await self.complete(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.get("/models", timeout=5.0)
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
        except httpx.HTTPError:
            return []

    async def close(self) -> None:
        await self._client.aclose()
