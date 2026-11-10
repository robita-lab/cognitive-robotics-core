"""LlmServerBackend contra un servidor SSE de prueba (stdlib, sin red externa)."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cognitive_language.core import BackendAnswer, CancelToken, CognitiveEngine, ThinkRequest, Turn
from cognitive_language.core.backends import LlmServerBackend


class FakeLLMServer:
    """Imita /v2/turn del llm-engine. `mode` decide el comportamiento."""

    def __init__(self):
        self.mode = "ok"
        self.reply = "Hola, soy UDITO. Estoy en Madrid. ¿En qué te ayudo?"
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.aborted = threading.Event()
        self.tokens_sent = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.requests.append(json.loads(self.rfile.read(n)))
                outer.headers.append(dict(self.headers))
                if outer.mode == "500":
                    self.send_response(500); self.end_headers(); return
                if outer.mode == "auth" and self.headers.get("Authorization") != "Bearer clave":
                    self.send_response(401); self.end_headers(); return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                words = outer.reply.split(" ")
                try:
                    for i, w in enumerate(words):
                        if outer.mode == "slow":
                            time.sleep(0.05)
                        if outer.mode == "midfail" and i == len(words) - 2:
                            return  # corta el stream sin done
                        tok = w + (" " if i < len(words) - 1 else "")
                        self.wfile.write(f"event: token\ndata: {tok}\n\n".encode()); self.wfile.flush()
                        outer.tokens_sent += 1
                    if outer.mode == "error":
                        self.wfile.write(b'event: error\ndata: {"error": "ollama caido"}\n\n'); return
                    done = {"text": outer.reply, "model": "fake-7b", "latency_ms": 1}
                    self.wfile.write(f"event: done\ndata: {json.dumps(done)}\n\n".encode()); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    outer.aborted.set()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    s = FakeLLMServer()
    yield s
    s.close()


def req(text="hola", sid="s1"):
    return ThinkRequest(session_id=sid, turn_id="t1", text=text)


def test_streams_sentences_and_sends_history_and_context(server):
    b = LlmServerBackend(server.url)
    parts = []
    ctx = [{"source": "normativa:ACC:7", "title": "Acceso, art. 7", "text": "traducción jurada"}]
    local = BackendAnswer("Según el artículo 7...", source="rag_local", delegate=True,
                          detail="normativa:ACC:7@x", context=ctx)
    hist = [Turn("user", "Hola"), Turn("assistant", "¡Hola!")]
    ans = b.answer(req("¿y eso?"), hist, CancelToken(), on_partial=lambda s, i: parts.append(s), local=local)
    assert ans is not None and ans.source == "llm_server" and ans.model_id == "fake-7b"
    assert ans.text == server.reply
    assert parts == ["Hola, soy UDITO.", "Estoy en Madrid.", "¿En qué te ayudo?"]
    assert ans.detail == "llm_server:grounded:normativa:ACC:7@x"
    body = server.requests[0]
    assert body["history"] == [{"role": "user", "content": "Hola"}, {"role": "assistant", "content": "¡Hola!"}]
    assert body["context"] == ctx and body["stream"] is True


def test_open_question_without_context(server):
    ans = LlmServerBackend(server.url).answer(req(), [], CancelToken())
    assert ans.detail == "llm_server:open" and server.requests[0]["context"] == []


def test_api_key_header(server):
    server.mode = "auth"
    assert LlmServerBackend(server.url, api_key="clave").answer(req(), [], CancelToken()) is not None
    bad = LlmServerBackend(server.url, api_key="otra")
    assert bad.answer(req(), [], CancelToken()) is None
    assert "401" in bad.last_error


def test_http_error_marks_down_and_skips_until_retry(server):
    now = [0.0]
    b = LlmServerBackend(server.url, retry_after_s=30, clock=lambda: now[0])
    server.mode = "500"
    assert b.answer(req(), [], CancelToken()) is None
    assert not b.available
    server.mode = "ok"
    assert b.answer(req(), [], CancelToken()) is None and len(server.requests) == 1  # ni lo intenta
    now[0] = 31
    assert b.answer(req(), [], CancelToken()) is not None


def test_connection_refused_is_fast():
    b = LlmServerBackend("http://127.0.0.1:9", connect_timeout=0.5)
    t0 = time.monotonic()
    assert b.answer(req(), [], CancelToken()) is None
    assert time.monotonic() - t0 < 1.0 and not b.available


def test_server_error_event(server):
    server.mode = "error"
    parts = []
    ans = LlmServerBackend(server.url).answer(req(), [], CancelToken(), on_partial=lambda s, i: parts.append(s))
    # ya se dijeron frases: se devuelve lo dicho (truncado) en vez de mezclar con otra respuesta
    assert ans is not None and ans.detail == "llm_server:truncated"
    assert ans.text == " ".join(parts)


def test_stream_cut_without_done(server):
    server.mode = "midfail"
    server.reply = "Una frase completa. Y otra que se corta aquí"
    parts = []
    ans = LlmServerBackend(server.url).answer(req(), [], CancelToken(), on_partial=lambda s, i: parts.append(s))
    assert ans.detail == "llm_server:truncated" and parts == ["Una frase completa."]


def test_cancel_closes_connection_and_server_stops(server):
    server.mode = "slow"
    server.reply = " ".join(f"palabra{i}." for i in range(200))  # ~10 s de stream
    tok = CancelToken()
    threading.Timer(0.3, tok.cancel).start()
    t0 = time.monotonic()
    ans = LlmServerBackend(server.url).answer(req(), [], tok)
    assert ans is None
    assert time.monotonic() - t0 < 1.5
    assert server.aborted.wait(2.0), "el servidor debería ver la conexión cerrada"
    assert server.tokens_sent < 50


def test_engine_falls_back_to_local_when_server_down():
    local = BackendAnswer("Según el artículo 7: traducción jurada.", source="rag_local", delegate=True,
                          context=[{"source": "x", "title": "t", "text": "y"}])

    class Local:
        name, ready = "normativa", True

        def warmup(self):
            pass

        def answer(self, *a, **k):
            return local

    eng = CognitiveEngine([Local()], remote=LlmServerBackend("http://127.0.0.1:9", connect_timeout=0.3))
    r = eng.think(req("¿traducción?"))
    assert r.source == "rag_local" and r.text == local.text
    assert r.backends_tried == ["normativa", "llm_server"]


# ------------------------------------------------------------------ filtro de voz
from cognitive_language.core.speech_filter import clean_sentence  # noqa: E402


@pytest.mark.parametrize(("raw", "clean"), [
    ("Según [1], la matrícula no es reembolsable.", "La matrícula no es reembolsable."),
    ("Equivale a 25 horas, según el fragmento [1] y [3].", "Equivale a 25 horas."),
    ("Según el documento [2], no se devuelve.", "No se devuelve."),
    ("Según el artículo 7 de la normativa, sí.", "Según el artículo 7 de la normativa, sí."),
    ("Necesitas el título (1) y las notas (2).", "Necesitas el título y las notas."),
    ("Un crédito son 25 horas, según el fragmento 2.", "Un crédito son 25 horas."),
    ("Sin marcas, todo bien.", "Sin marcas, todo bien."),
    ("El *Quijote* lo escribió **Cervantes**.", "El Quijote lo escribió Cervantes."),
    ("Necesitas: - El título. - La credencial.", "Necesitas: El título. La credencial."),
    ("Más en la web unedasiss.uned.es/home y ya.", "Más en la web y ya."),
    ("Son 25 horas, sin guiones-raros.", "Son 25 horas, sin guiones-raros."),
])
def test_clean_sentence_markers(raw, clean):
    assert clean_sentence(raw) == (clean, False)


def test_clean_sentence_cuts_foreign_script():
    s, cut = clean_sentence("Además, genera y转让协议 The Share Transfer Agreement")
    assert cut and "转" not in s and "Share" not in s
    s, cut = clean_sentence("La misión de UDIT es formar profesionales creativos y转让")
    assert cut and s == "La misión de UDIT es formar profesionales creativos."


def test_foreign_script_stops_stream_and_keeps_what_was_said(server):
    server.reply = "La misión es formar profesionales. Además genera y转让协议 The Share Transfer Agreement is long."
    parts = []
    ans = LlmServerBackend(server.url).answer(req(), [], CancelToken(), on_partial=lambda s, i: parts.append(s))
    assert ans.detail == "llm_server:script_cut"
    assert parts == ["La misión es formar profesionales."] and ans.text == parts[0]
    b = LlmServerBackend(server.url)
    assert b.available  # no es culpa del servidor: no se marca como caído


def test_returned_text_is_what_was_spoken(server):
    server.reply = "Según [1], son 25 horas. Fin de la respuesta."
    ans = LlmServerBackend(server.url).answer(req(), [], CancelToken())
    assert ans.text == "Son 25 horas. Fin de la respuesta."
