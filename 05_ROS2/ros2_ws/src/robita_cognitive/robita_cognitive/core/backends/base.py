"""Contrato de los backends cognitivos."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..types import BackendAnswer, CancelToken, PartialCallback, ThinkRequest, Turn


@runtime_checkable
class Backend(Protocol):
    name: str

    @property
    def ready(self) -> bool:
        """False mientras carga modelos/índices; el motor lo salta sin esperar."""
        ...

    def warmup(self) -> None:
        """Carga perezosa de lo pesado. Puede tardar minutos; se llama en un hilo aparte."""
        ...

    def answer(
        self,
        req: ThinkRequest,
        history: list[Turn],
        cancel: CancelToken,
        on_partial: PartialCallback | None = None,
    ) -> BackendAnswer | None:
        """Respuesta, o None si este backend no sabe/no puede contestar.

        Un backend que emita frases por streaming (on_partial) debe devolver
        al final la respuesta completa igualmente.
        """
        ...
