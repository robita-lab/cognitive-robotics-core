"""Tipos del núcleo cognitivo. Sin dependencias de ROS."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Literal

# Valores de `source` en el resultado de Think (ver robita_interfaces/action/Think.action).
Source = Literal["basic_qa", "rag_local", "rag_server", "llm_local", "llm_server", "fallback"]

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


@dataclass(frozen=True)
class ThinkRequest:
    session_id: str
    text: str
    turn_id: str = ""
    lang: str = ""


@dataclass
class BackendAnswer:
    """Respuesta de un backend.

    delegate=True significa "esto es una pregunta general: si hay un backend
    mejor (LLM) que la conteste él; mi `text` solo sirve de respaldo".
    """

    text: str
    emotion: str = "helpful"
    source: Source = "fallback"
    model_id: str = ""
    delegate: bool = False
    detail: str = ""  # origen fino del backend (p. ej. "knowledge_horarios"), para trazas
    # Fragmentos en los que se basa (para que el LLM remoto redacte a partir de ellos):
    # [{"source": "normativa:ACC:7", "title": "...", "text": "..."}]
    context: list[dict] = field(default_factory=list)


@dataclass
class ThinkResult:
    text: str
    emotion: str
    source: Source
    model_id: str = ""
    latency_ms: float = 0.0
    detail: str = ""
    cancelled: bool = False
    backends_tried: list[str] = field(default_factory=list)


class CancelToken:
    """Cancelación cooperativa: los backends la consultan entre pasos."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        """Bloquea hasta que se cancele (o venza timeout). Devuelve si está cancelado."""
        return self._event.wait(timeout)


# Callback de streaming: (frase, índice). Lo usa el servidor Think para publicar feedback.
PartialCallback = Callable[[str, int], None]
