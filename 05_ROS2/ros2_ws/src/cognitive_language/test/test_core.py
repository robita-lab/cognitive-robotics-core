"""Tests del núcleo cognitivo (sin ROS, sin modelos)."""

from __future__ import annotations

import pytest

from cognitive_language.core import (
    FALLBACK_TEXT,
    BackendAnswer,
    CancelToken,
    CognitiveEngine,
    ConversationMemory,
    SentenceAccumulator,
    ThinkRequest,
    split_sentences,
)
from cognitive_language.core.backends import map_legacy_result


class FakeBackend:
    def __init__(self, name, answer=None, ready=True, raises=False, partials=(), on_call=None):
        self.name = name
        self._answer = answer
        self._ready = ready
        self._raises = raises
        self._partials = partials
        self._on_call = on_call
        self.calls = []

    @property
    def ready(self):
        return self._ready

    def warmup(self):
        self._ready = True

    def answer(self, req, history, cancel, on_partial=None, local=None):
        self.calls.append((req, list(history)))
        self.local_seen = local
        if self._on_call:
            self._on_call(cancel)
        if self._raises:
            raise RuntimeError("boom")
        for i, p in enumerate(self._partials):
            if on_partial:
                on_partial(p, i)
        return self._answer


def req(text, sid="s1", turn="1"):
    return ThinkRequest(session_id=sid, turn_id=turn, text=text)


# --------------------------------------------------------------- frases
def test_split_sentences_basic():
    assert split_sentences("Hola. Soy UDITO. ¿Qué tal?") == ["Hola.", "Soy UDITO.", "¿Qué tal?"]


def test_split_sentences_keeps_decimals_and_abbrev():
    assert split_sentences("Mide 3.5 metros. Lo dijo el Dr. Pérez.") == [
        "Mide 3.5 metros.",
        "Lo dijo el Dr. Pérez.",
    ]


def test_split_sentences_empty():
    assert split_sentences("   ") == []


def test_sentence_accumulator_keeps_spaces_between_tokens():
    acc = SentenceAccumulator()
    out = []
    for tok in ["Estoy ", "en ", "Madrid. ", "Lo ", "dijo ", "el ", "Dr. ", "Pérez. ", "Fin"]:
        out += acc.feed(tok)
    out += acc.flush()
    assert out == ["Estoy en Madrid.", "Lo dijo el Dr. Pérez.", "Fin"]


def test_sentence_accumulator_streams_complete_sentences():
    acc = SentenceAccumulator()
    out = []
    for chunk in ["Hola", ", soy UDI", "TO. Estoy", " listo. Y", " tú"]:
        out += acc.feed(chunk)
    out += acc.flush()
    assert out == ["Hola, soy UDITO.", "Estoy listo.", "Y tú"]


# --------------------------------------------------------------- memoria
def test_memory_bounded_and_ttl():
    now = [0.0]
    mem = ConversationMemory(max_turns=2, ttl_s=10, clock=lambda: now[0])
    for i in range(3):
        mem.append("a", f"q{i}", f"r{i}")
    hist = mem.history("a")
    assert [t.text for t in hist] == ["q1", "r1", "q2", "r2"]
    now[0] = 11
    assert mem.history("a") == []


def test_memory_sessions_isolated():
    mem = ConversationMemory()
    mem.append("a", "hola", "hola!")
    assert mem.history("b") == []
    mem.reset("a")
    assert mem.history("a") == []


# --------------------------------------------------------------- motor
def test_first_local_backend_wins_and_partials_emitted():
    a = FakeBackend("a", BackendAnswer("Uno. Dos.", "happy", "basic_qa"))
    b = FakeBackend("b", BackendAnswer("no", "x", "rag_local"))
    eng = CognitiveEngine([a, b])
    parts = []
    r = eng.think(req("hola"), on_partial=lambda s, i: parts.append((i, s)))
    assert (r.text, r.source, r.emotion) == ("Uno. Dos.", "basic_qa", "happy")
    assert parts == [(0, "Uno."), (1, "Dos.")]
    assert b.calls == []
    assert r.backends_tried == ["a"]


def test_not_ready_or_failing_backend_is_skipped():
    a = FakeBackend("rag", None, ready=False)
    broken = FakeBackend("broken", raises=True)
    c = FakeBackend("basic", BackendAnswer("Hola", source="basic_qa"))
    r = CognitiveEngine([a, broken, c]).think(req("hola"))
    assert r.source == "basic_qa"
    assert r.backends_tried == ["rag", "broken", "basic"]


def test_fallback_when_nobody_answers():
    r = CognitiveEngine([FakeBackend("a", None)]).think(req("xyz"))
    assert (r.text, r.source) == (FALLBACK_TEXT, "fallback")


def test_empty_text_does_not_touch_backends_or_memory():
    a = FakeBackend("a", BackendAnswer("x"))
    eng = CognitiveEngine([a])
    r = eng.think(req("  "))
    assert r.source == "fallback" and a.calls == []
    assert eng.memory.history("s1") == []


def test_delegate_without_remote_keeps_local_text():
    a = FakeBackend("rag", BackendAnswer("No tengo ese dato.", "sorry", "rag_local", delegate=True))
    r = CognitiveEngine([a]).think(req("¿quién ganó el mundial?"))
    assert (r.text, r.source) == ("No tengo ese dato.", "rag_local")


def test_delegate_goes_to_remote_with_history():
    a = FakeBackend("rag", BackendAnswer("No sé.", "sorry", "rag_local", delegate=True))
    remote = FakeBackend(
        "llm", BackendAnswer("España. En 2010.", "happy", "llm_server", model_id="qwen"),
        partials=("España.", "En 2010."),
    )
    eng = CognitiveEngine([a], remote=remote)
    eng.memory.append("s1", "hola", "hola!")
    parts = []
    r = eng.think(req("¿quién ganó?"), on_partial=lambda s, i: parts.append((i, s)))
    assert (r.source, r.model_id) == ("llm_server", "qwen")
    assert parts == [(0, "España."), (1, "En 2010.")]  # no se duplican
    assert [t.text for t in remote.calls[0][1]] == ["hola", "hola!"]


def test_remote_failure_falls_back_to_local():
    a = FakeBackend("rag", BackendAnswer("No sé.", "sorry", "rag_local", delegate=True))
    remote = FakeBackend("llm", None)
    r = CognitiveEngine([a], remote=remote).think(req("¿y eso?"))
    assert (r.text, r.source) == ("No sé.", "rag_local")


def test_non_delegated_local_answer_skips_remote():
    a = FakeBackend("rag", BackendAnswer("Horario 9-14.", source="rag_local"))
    remote = FakeBackend("llm", BackendAnswer("x", source="llm_server"))
    r = CognitiveEngine([a], remote=remote).think(req("horario"))
    assert r.source == "rag_local" and remote.calls == []


def test_memory_records_turns():
    eng = CognitiveEngine([FakeBackend("a", BackendAnswer("Hola!"))])
    eng.think(req("hola"))
    assert [t.text for t in eng.memory.history("s1")] == ["hola", "Hola!"]


def test_cancel_before_answer_is_not_stored():
    tok = CancelToken()
    a = FakeBackend("a", None, on_call=lambda c: tok.cancel())
    b = FakeBackend("b", BackendAnswer("tarde"))
    eng = CognitiveEngine([a, b])
    parts = []
    r = eng.think(req("hola"), cancel=tok, on_partial=lambda s, i: parts.append(s))
    assert r.cancelled and b.calls == [] and parts == []
    assert eng.memory.history("s1") == []


def test_warmup_async_marks_backends_ready():
    a = FakeBackend("a", ready=False)
    eng = CognitiveEngine([a])
    eng.warmup_async().join(timeout=2)
    assert eng.status() == {"a": True}


# --------------------------------------------------------------- mapeo legado
@pytest.mark.parametrize(
    ("src", "expected", "delegate"),
    [
        ("basic_qa", "basic_qa", False),
        ("fun_joke", "basic_qa", False),
        ("knowledge_horarios", "rag_local", False),
        ("fixed_udit_address", "rag_local", False),
        ("rag", "rag_local", False),
        ("rag_no_results", "rag_local", False),
        ("gpt", "rag_local", True),
    ],
)
def test_map_legacy_result(src, expected, delegate):
    ans = map_legacy_result({"answer": "texto", "emotion": "happy", "source": src})
    assert ans is not None
    assert (ans.source, ans.delegate, ans.detail) == (expected, delegate, src)


def test_map_legacy_error_is_none():
    assert map_legacy_result({"answer": "Lo siento", "source": "error"}) is None
    assert map_legacy_result({"answer": "", "source": "rag"}) is None


def test_remote_receives_local_answer_with_context():
    ctx = [{"source": "normativa:ACC:7", "title": "Acceso, artículo 7", "text": "traducción jurada"}]
    a = FakeBackend("normativa", BackendAnswer("Según el artículo 7...", source="rag_local", delegate=True, context=ctx))
    remote = FakeBackend("llm", BackendAnswer("Sí, con traducción jurada.", source="llm_server"))
    r = CognitiveEngine([a], remote=remote).think(req("¿traducción?"))
    assert r.source == "llm_server"
    assert remote.local_seen is not None and remote.local_seen.context == ctx


def test_scope_guard_only_for_udit_questions():
    from cognitive_language.core.backends import ScopeGuardBackend
    from cognitive_language.core.backends.scope import mentions_udit

    assert mentions_udit("¿Hay cafetería en la universidad?")
    assert mentions_udit("¿Cuánto cuesta la matrícula?")
    assert not mentions_udit("¿Qué es un agujero negro?")
    assert not mentions_udit("¿Qué tiempo hará mañana?")
    remote = FakeBackend("llm", BackendAnswer("Hay un comedor universitario...", source="llm_server"))
    eng = CognitiveEngine([FakeBackend("normativa", None), ScopeGuardBackend()], remote=remote)
    r = eng.think(req("¿Hay cafetería en la universidad?"))
    assert (r.source, r.detail) == ("fallback", "scope_guard") and remote.calls == []
    r = eng.think(req("¿Qué es un agujero negro?"))
    assert r.source == "llm_server"
