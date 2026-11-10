"""Backend remoto: LLM del servidor (01_SERVICES/llm-engine, POST /v2/turn).

- Sin estado en el servidor (D5): en cada turno se manda el historial de la
  sesión (la memoria vive en el robot) y, si la búsqueda local encontró
  normativa, esos fragmentos como contexto para que el LLM redacte la
  respuesta basándose en ellos.
- Streaming SSE: cada frase completa sale por `on_partial` (feedback de Think)
  para que el TTS empiece con la primera.
- Cancelación: un hilo vigila el CancelToken y cierra el socket; el servidor
  lo detecta y deja de generar.
- Si el servidor no responde, se marca como caído durante `retry_after_s` y
  mientras tanto ni se intenta (sin WiFi el robot no espera en cada turno).
- Solo stdlib (http.client): no añade dependencias al nodo ROS.
"""

from __future__ import annotations

import http.client
import json
import logging
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from ..sentences import SentenceAccumulator
from ..speech_filter import clean_sentence
from ..types import BackendAnswer, CancelToken, PartialCallback, ThinkRequest, Turn

log = logging.getLogger("cognitive_language.llm_server")


class LlmServerError(Exception):
    pass


class _ForeignScript(Exception):
    """El LLM ha saltado a otro alfabeto: se corta el stream (no es un fallo del servidor)."""


class LlmServerBackend:
    name = "llm_server"

    def __init__(
        self,
        url: str,
        api_key: str = "",
        connect_timeout: float = 1.5,
        first_token_timeout: float = 8.0,
        total_timeout: float = 30.0,
        max_tokens: int = 120,
        max_history: int = 12,
        retry_after_s: float = 30.0,
        clock=time.monotonic,
    ) -> None:
        self.url = url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.connect_timeout = connect_timeout
        self.first_token_timeout = first_token_timeout
        self.total_timeout = total_timeout
        self.max_tokens = max_tokens
        self.max_history = max_history
        self.retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0
        self.last_error = ""

    # ------------------------------------------------------------------ estado
    @property
    def ready(self) -> bool:
        return bool(self.url)

    @property
    def available(self) -> bool:
        return bool(self.url) and self._clock() >= self._down_until

    def warmup(self) -> None:
        """Comprueba /healthz sin bloquear el arranque si el servidor no está."""
        if not self.url:
            return
        try:
            conn = self._connection(timeout=self.connect_timeout)
            conn.request("GET", self._path("/healthz"))
            ok = conn.getresponse().status == 200
            conn.close()
            log.info("llm-engine %s: %s", self.url, "accesible" if ok else "responde con error")
        except OSError as exc:
            log.warning("llm-engine %s no accesible al arrancar (%s); lo reintentaré en cada turno", self.url, exc)

    def _mark_down(self, why: str) -> None:
        self.last_error = why
        self._down_until = self._clock() + self.retry_after_s
        log.warning("llm-engine no disponible (%s); no lo intento durante %.0f s", why, self.retry_after_s)

    # ------------------------------------------------------------------ http
    def _path(self, p: str) -> str:
        base = urlsplit(self.url).path.rstrip("/")
        return f"{base}{p}"

    def _connection(self, timeout: float) -> http.client.HTTPConnection:
        u = urlsplit(self.url)
        if u.scheme == "https":
            return http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout,
                                               context=ssl.create_default_context())
        return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)

    def _body(self, req: ThinkRequest, history: list[Turn], local: BackendAnswer | None) -> bytes:
        hist = [{"role": t.role, "content": t.text} for t in history][-self.max_history:]
        context = list(local.context) if local is not None else []
        return json.dumps({
            "session_id": req.session_id or "default",
            "turn_id": req.turn_id,
            "user_text": req.text,
            "history": hist,
            "context": context,
            "lang": req.lang or "es",
            "max_tokens": self.max_tokens,
            "stream": True,
        }, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _sse(resp: http.client.HTTPResponse):
        """Itera (evento, datos) de un stream SSE."""
        event, data = "message", []
        while True:
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8").rstrip("\r\n")
            if not line:
                if data:
                    yield event, "\n".join(data)
                event, data = "message", []
            elif line.startswith(":"):
                continue  # comentario / ping
            elif line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                v = line[5:]
                data.append(v[1:] if v.startswith(" ") else v)
        if data:
            yield event, "\n".join(data)

    # ------------------------------------------------------------------ turno
    def answer(
        self,
        req: ThinkRequest,
        history: list[Turn],
        cancel: CancelToken,
        on_partial: PartialCallback | None = None,
        local: BackendAnswer | None = None,
    ) -> BackendAnswer | None:
        if not self.available or cancel.cancelled:
            return None
        t0 = self._clock()
        grounded = bool(local is not None and local.context)
        emitted: list[str] = []
        collected: list[str] = []
        acc = SentenceAccumulator()
        finished = threading.Event()
        conn: http.client.HTTPConnection | None = None

        def emit(sentence: str) -> None:
            sentence, cut = clean_sentence(sentence)
            if sentence:
                emitted.append(sentence)
                if on_partial is not None and not cancel.cancelled:
                    on_partial(sentence, len(emitted) - 1)
            if cut:
                raise _ForeignScript()

        def watch_cancel() -> None:
            while not finished.is_set():
                if cancel.wait(0.05):
                    try:
                        if conn is not None and conn.sock is not None:
                            conn.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return

        watcher = threading.Thread(target=watch_cancel, name="llm-cancel-watch", daemon=True)
        model, final_text = "", None
        try:
            conn = self._connection(timeout=self.connect_timeout)
            conn.connect()
            watcher.start()
            headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            conn.sock.settimeout(self.first_token_timeout)
            conn.request("POST", self._path("/v2/turn"), body=self._body(req, history, local), headers=headers)
            resp = conn.getresponse()
            if resp.status == 401:
                raise LlmServerError("clave de API rechazada (401): revisa COGNITIVE_LLM_API_KEY")
            if resp.status != 200:
                raise LlmServerError(f"HTTP {resp.status}")
            for event, data in self._sse(resp):
                if cancel.cancelled:
                    break
                if self._clock() - t0 > self.total_timeout:
                    raise LlmServerError(f"sin terminar tras {self.total_timeout:.0f} s")
                if event == "token":
                    collected.append(data)
                    for s in acc.feed(data):
                        emit(s)
                elif event == "done":
                    info = json.loads(data)
                    model, final_text = info.get("model", ""), info.get("text", "")
                    break
                elif event == "error":
                    raise LlmServerError(json.loads(data).get("error", "error del servidor"))
            if cancel.cancelled:
                return None
            if final_text is None:
                raise LlmServerError("el stream terminó sin evento done")
            for s in acc.flush():
                emit(s)
        except _ForeignScript:
            log.warning("[%s/%s] el LLM cambió de alfabeto; corto tras %d frases", req.session_id, req.turn_id,
                        len(emitted))
            if not emitted:
                return None
            return BackendAnswer(" ".join(emitted), local.emotion if grounded else "helpful", "llm_server",
                                 model_id=model, detail="llm_server:script_cut")
        except (OSError, http.client.HTTPException, ValueError, LlmServerError) as exc:
            if cancel.cancelled:
                log.info("[%s/%s] petición al LLM cancelada", req.session_id, req.turn_id)
                return None
            self._mark_down(f"{type(exc).__name__}: {exc}")
            if emitted:  # ya se dijo parte: devolvemos lo dicho para no mezclarlo con otra respuesta
                return BackendAnswer(" ".join(emitted), "helpful", "llm_server", model_id=model,
                                     detail="llm_server:truncated")
            return None
        finally:
            finished.set()
            if conn is not None:
                conn.close()

        # Lo que se devuelve (y se guarda en memoria) es exactamente lo que se ha dicho.
        text = " ".join(emitted).strip()
        if not text:
            return None
        detail = f"llm_server:grounded:{local.detail}" if grounded else "llm_server:open"
        log.info("[%s/%s] LLM %s en %.0f ms", req.session_id, req.turn_id, detail, (self._clock() - t0) * 1000)
        return BackendAnswer(text, local.emotion if grounded else "helpful", "llm_server",
                             model_id=model, detail=detail)
