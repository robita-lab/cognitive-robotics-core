"""Memoria de conversación en el robot (D5: el robot es la fuente de verdad).

Se indexa por session_id. Cada sesión guarda los últimos `max_turns` pares
pregunta/respuesta y caduca tras `ttl_s` segundos sin actividad.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from .types import Turn


class ConversationMemory:
    def __init__(
        self,
        max_turns: int = 8,
        ttl_s: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns debe ser >= 1")
        self.max_turns = max_turns
        self.ttl_s = ttl_s
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, tuple[float, deque[Turn]]] = {}

    def _expire(self, now: float) -> None:
        dead = [sid for sid, (last, _) in self._sessions.items() if now - last > self.ttl_s]
        for sid in dead:
            del self._sessions[sid]

    def history(self, session_id: str) -> list[Turn]:
        with self._lock:
            self._expire(self._clock())
            entry = self._sessions.get(session_id)
            return list(entry[1]) if entry else []

    def append(self, session_id: str, user_text: str, assistant_text: str) -> None:
        with self._lock:
            now = self._clock()
            self._expire(now)
            _, turns = self._sessions.get(session_id, (now, deque(maxlen=2 * self.max_turns)))
            turns.append(Turn("user", user_text))
            turns.append(Turn("assistant", assistant_text))
            self._sessions[session_id] = (now, turns)

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def sessions(self) -> list[str]:
        with self._lock:
            self._expire(self._clock())
            return list(self._sessions)
