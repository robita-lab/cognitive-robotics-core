"""Sync HTTP client for the UDITO FastAPI LLM server.

Kept deliberately small and synchronous: the ROS node calls it from a worker
thread (thread pool), not the rclpy executor thread, so sync is fine and
avoids the friction of running asyncio inside a ROS2 callback.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ChatReply:
    reply: str
    model: str
    tier: str
    latency_ms: int


class LLMClient:
    """Thin wrapper around the server's /v1/chat endpoint."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def chat(
        self,
        conversation_id: str,
        user_text: str,
        persona: str = "default",
        max_tokens: int | None = None,
        recent_context: list[dict] | None = None,
    ) -> ChatReply:
        payload: dict = {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "persona": persona,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if recent_context:
            payload["recent_context"] = recent_context

        started = time.monotonic()
        resp = self._client.post("/v1/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

        return ChatReply(
            reply=data["reply"],
            model=data.get("model", ""),
            tier=data.get("tier", ""),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    def healthy(self) -> bool:
        try:
            resp = self._client.get("/healthz", timeout=2.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
