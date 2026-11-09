"""Motor cognitivo: decide qué backend contesta cada turno.

Reglas (D4/D5 del documento de consenso):

1. Se prueban en orden los backends locales (los del robot). Gana el primero
   que devuelve respuesta. Un backend que no está listo devuelve None y se
   salta sin esperar.
2. Si la respuesta local pide ayuda (delegate=True: pregunta general, o
   normativa que conviene redactar con sus fragmentos en `context`), o nadie
   local sabe contestar, y hay backend remoto (LLM del servidor), se le pasa
   el turno con el historial de la sesión y la respuesta local como base.
3. Si el remoto falla o no existe, vale la respuesta local; si tampoco hay,
   la frase de respaldo.
4. La respuesta se emite por frases (on_partial) y se guarda en la memoria
   de la sesión. Un turno cancelado no se guarda.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Sequence

from .backends.base import Backend
from .memory import ConversationMemory
from .sentences import split_sentences
from .types import BackendAnswer, CancelToken, PartialCallback, ThinkRequest, ThinkResult

log = logging.getLogger("robita_cognitive.engine")

FALLBACK_TEXT = "Todavía estoy aprendiendo sobre eso. ¿Me lo preguntas de otra forma?"
EMPTY_TEXT = "No te he entendido bien. ¿Me lo repites?"


class CognitiveEngine:
    def __init__(
        self,
        local: Sequence[Backend],
        remote: Backend | None = None,
        memory: ConversationMemory | None = None,
        fallback_text: str = FALLBACK_TEXT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.local = list(local)
        self.remote = remote
        self.memory = memory or ConversationMemory()
        self.fallback_text = fallback_text
        self._clock = clock

    # ------------------------------------------------------------------ carga
    def warmup_async(self) -> threading.Thread:
        """Carga los backends en segundo plano; el motor responde mientras tanto."""

        def _run() -> None:
            for b in [*self.local, *([self.remote] if self.remote else [])]:
                try:
                    b.warmup()
                except Exception:  # noqa: BLE001
                    log.exception("warmup de %s falló", b.name)

        t = threading.Thread(target=_run, name="cognitive-warmup", daemon=True)
        t.start()
        return t

    def status(self) -> dict[str, bool]:
        backends = [*self.local, *([self.remote] if self.remote else [])]
        return {b.name: b.ready for b in backends}

    # ------------------------------------------------------------------ turno
    def think(
        self,
        req: ThinkRequest,
        cancel: CancelToken | None = None,
        on_partial: PartialCallback | None = None,
    ) -> ThinkResult:
        cancel = cancel or CancelToken()
        t0 = self._clock()
        tried: list[str] = []
        emitted = 0

        def emit(sentence: str, _index: int = -1) -> None:
            nonlocal emitted
            if on_partial is not None and not cancel.cancelled:
                on_partial(sentence, emitted)
            emitted += 1

        def done(ans: BackendAnswer, *, cancelled: bool = False) -> ThinkResult:
            return ThinkResult(
                text=ans.text,
                emotion=ans.emotion,
                source=ans.source,
                model_id=ans.model_id,
                latency_ms=(self._clock() - t0) * 1000.0,
                detail=ans.detail,
                cancelled=cancelled,
                backends_tried=tried,
            )

        text = req.text.strip()
        if not text:
            ans = BackendAnswer(EMPTY_TEXT, "confused", "fallback", detail="empty")
            for s in split_sentences(ans.text):
                emit(s)
            return done(ans)

        history = self.memory.history(req.session_id)

        local_ans: BackendAnswer | None = None
        for b in self.local:
            if cancel.cancelled:
                return done(BackendAnswer("", "neutral", "fallback"), cancelled=True)
            tried.append(b.name)
            try:
                local_ans = b.answer(req, history, cancel)
            except Exception:  # noqa: BLE001 — un backend roto no tumba el turno
                log.exception("backend %s falló", b.name)
                local_ans = None
            if local_ans is not None:
                break

        final: BackendAnswer | None = None
        streamed = False
        wants_remote = local_ans is None or local_ans.delegate
        if wants_remote and self.remote is not None and not cancel.cancelled:
            tried.append(self.remote.name)
            before = emitted
            try:
                final = self.remote.answer(req, history, cancel, on_partial=emit, local=local_ans)
            except Exception:  # noqa: BLE001
                log.exception("backend remoto %s falló", self.remote.name)
                final = None
            streamed = emitted > before

        if cancel.cancelled:
            partial = final or local_ans or BackendAnswer("", "neutral", "fallback")
            return done(partial, cancelled=True)

        if final is None:
            if local_ans is not None and local_ans.text:
                final = local_ans
            else:
                final = BackendAnswer(self.fallback_text, "sorry", "fallback", detail="no_answer")

        if not streamed:
            for s in split_sentences(final.text):
                emit(s)

        self.memory.append(req.session_id, text, final.text)
        result = done(final)
        log.info(
            "[%s/%s] «%s» → %s (%s, %.0f ms)",
            req.session_id, req.turn_id, text[:60], result.source, result.detail, result.latency_ms,
        )
        return result
