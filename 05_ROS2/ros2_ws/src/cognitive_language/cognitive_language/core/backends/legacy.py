"""Backends que envuelven el rag-engine actual (01_SERVICES/rag-engine).

Es el mismo código que usa hoy la demo `./UDITO` y el `cognitive_node` de
Danilo, así que con él tenemos paridad desde el primer día. Se sustituirá por
un RAG propio cuando cambiemos los embeddings (P1, segundo paso).

- BasicQaBackend: respuestas fijas (saludos, identidad, preguntas UDIT
  frecuentes). Solo stdlib: carga en milisegundos.
- LegacyRagBackend: RAGSystem completo (Q&A fijo, chistes, sedes, horarios,
  FAISS sobre la normativa). Necesita sentence-transformers + faiss y tarda
  en cargar; mientras no está listo el motor lo salta.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from ..paths import add_to_syspath, find_repo_root
from ..types import BackendAnswer, CancelToken, PartialCallback, Source, ThinkRequest, Turn

log = logging.getLogger("cognitive_language.legacy")

# Fuentes del RAGSystem → `source` de Think.
_SOURCE_MAP: dict[str, Source] = {
    "basic_qa": "basic_qa",
    "fun_fact": "basic_qa",
    "fun_joke": "basic_qa",
    "knowledge_address": "rag_local",
    "fixed_udit_address": "rag_local",
    "rag": "rag_local",
    "rag_low_confidence": "rag_local",
    "rag_no_results": "rag_local",
}
# Fuentes que el RAGSystem marca como "pregunta general": las responde mejor un LLM.
_DELEGATE_SOURCES = {"gpt"}


def map_legacy_result(result: dict) -> BackendAnswer | None:
    """Traduce el dict de RAGSystem.process_query a BackendAnswer."""
    src = str(result.get("source", ""))
    text = str(result.get("answer") or "").strip()
    emotion = str(result.get("emotion") or "helpful")
    if src == "error":
        return None
    if src in _DELEGATE_SOURCES:
        return BackendAnswer(text=text, emotion=emotion, source="rag_local", delegate=True, detail=src)
    if not text:
        return None
    if src.startswith("knowledge_"):
        mapped: Source = "rag_local"
    else:
        mapped = _SOURCE_MAP.get(src, "rag_local")
    return BackendAnswer(text=text, emotion=emotion, source=mapped, detail=src)


class BasicQaBackend:
    name = "basic_qa"

    def __init__(self, repo_root: str | os.PathLike | None = None) -> None:
        self._repo_root = repo_root
        self._mgr = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._mgr is not None

    def warmup(self) -> None:
        with self._lock:
            if self._mgr is not None:
                return
            root = find_repo_root(self._repo_root)
            add_to_syspath(root / "01_SERVICES" / "rag-engine")
            from basic_qa_manager import BasicQAManager  # type: ignore[import-not-found]

            self._mgr = BasicQAManager(
                qa_file_path=str(root / "04_KNOWLEDGE_CORE" / "responses" / "qa.json")
            )

    def answer(
        self,
        req: ThinkRequest,
        history: list[Turn],
        cancel: CancelToken,
        on_partial: PartialCallback | None = None,
    ) -> BackendAnswer | None:
        if self._mgr is None:
            self.warmup()
        r = strict_basic_answer(self._mgr, req.text)
        if not r or not r.get("answer"):
            return None
        text = r["answer"]
        try:
            text = self._mgr.format_answer(text)
        except Exception:  # noqa: BLE001 — plantilla rara: usamos el texto tal cual
            pass
        return BackendAnswer(
            text=text, emotion=r.get("emotion", "helpful"), source="basic_qa", detail="basic_qa"
        )


import re as _re
import unicodedata as _ud


def _fold(t: str) -> str:
    return "".join(c for c in _ud.normalize("NFD", t.lower()) if _ud.category(c) != "Mn")


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    """Palabra o expresión completa (las reglas antiguas usan subcadenas: "hora" casaba con "horas")."""
    t = _fold(text)
    return any(_re.search(rf"\b{_re.escape(_fold(w))}\b", t) for w in words)


def _has_word_prefix(text: str, words: tuple[str, ...]) -> bool:
    """Como _has_word, pero las claves de más de 3 letras pueden ser comienzo de palabra:
    «quien te cre» casa con «quién te creó», y «parte» ya no casa dentro de «imparten»."""
    t = _fold(text)
    for w in words:
        f = _re.escape(_fold(w))
        if _re.search(rf"\b{f}" if len(w) > 3 else rf"\b{f}\b", t):
            return True
    return False


def _n_words(text: str) -> int:
    return len(_re.findall(r"\w+", text))


# Respuestas enlatadas (Q&A fijo, chiste, dato curioso, identidad) solo para frases cortas:
# con el micro abierto, frases largas de una tele o de una conversación cercana las
# disparaban por una palabra suelta (piloto en la Jetson, 2026-11-13).
MAX_CANNED_WORDS = 10
# Claves de qa.json demasiado genéricas para disparar solas una respuesta fija:
# «creo que…», «lo hicieron», «es un autor», «se imparten», «un robot», «máster oficial»…
_LOOSE_KEYWORDS = frozenset(_fold(w) for w in (
    "creo", "creó", "hicieron", "autor", "nombre", "parte", "robot", "máquina", "oficial",
    "institución", "listo", "sabio", "pensar", "artificial", "universidad", "udit",
))
# La identidad de knowledge-text se disparaba con solo oír «UDITO».
_ID_WORDS = ("quien eres", "que eres", "como te llamas", "tu nombre", "que es udito", "quien es udito")


def strict_basic_answer(bqa, text: str) -> dict | None:
    """BasicQAManager.find_basic_answer con palabras completas, sin claves genéricas y solo
    para frases cortas. Mismo orden: saludos → identidad → UDIT → preguntas generales."""
    if _n_words(text) > MAX_CANNED_WORDS:
        return None
    low = text.lower().strip()
    if bqa._is_academic_query(low):
        return None
    for section in ("greetings", "identity_questions", "udit_specific"):
        for entry in bqa.qa_data.get(section, []):
            kws = tuple(k for k in entry.get("keywords", []) if _fold(k) not in _LOOSE_KEYWORDS)
            if kws and _has_word_prefix(text, kws):
                return entry
    for entry in bqa.qa_data.get("questions", []):
        if bqa._matches_question(low, entry["question"]):
            return entry
    return None


# Mismas listas que load_responses.match_knowledge_text, pero exigiendo palabra completa.
# «dónde está» solo cuenta junto a UDIT/universidad: «…, donde está Gatig, …» (una tele)
# era a la vez palabra de dirección y de pregunta y daba la dirección de las sedes.
_ADDRESS_WORDS = ("direccion", "sede", "sedes", "ubicacion", "campus", "calle", "avenida", "domicilio")
_ADDRESS_WEAK = ("donde esta", "donde queda")
_UNI_WORDS = ("universidad", "udit", "facultad", "centro")
_WHERE_WORDS = ("cual", "donde", "que es", "dime")
_SCHEDULE_WORDS = ("horario", "horarios", "hora", "abre", "abren", "cierra", "cierran", "atencion",
                   "biblioteca", "secretaria", "administrativo", "administrativa", "administracion")


class RulesBackend:
    """Las reglas del RAGSystem que van ANTES de buscar en documentos, sin cargar modelos.

    Mismo orden que RAGSystem.process_query: Q&A fijo → dato curioso / chiste →
    dirección de las sedes → textos de 04_KNOWLEDGE_CORE/knowledge-text (horarios,
    contacto, identidad). Solo stdlib: arranca en milisegundos y no necesita
    torch, faiss ni PyPDF2. La búsqueda en documentos la hace NormativaBackend.
    """

    name = "rules"

    def __init__(self, repo_root: str | os.PathLike | None = None) -> None:
        self._repo_root = repo_root
        self._lock = threading.Lock()
        self._bqa = None
        self._lr = None
        self._conv = None

    @property
    def ready(self) -> bool:
        return self._bqa is not None

    def warmup(self) -> None:
        with self._lock:
            if self._bqa is not None:
                return
            root = find_repo_root(self._repo_root)
            add_to_syspath(root / "01_SERVICES" / "rag-engine", root / "04_KNOWLEDGE_CORE")
            import load_responses as lr  # type: ignore[import-not-found]
            from basic_qa_manager import BasicQAManager  # type: ignore[import-not-found]
            from conversational_answer import conversational_from_context  # type: ignore[import-not-found]

            self._lr, self._conv = lr, conversational_from_context
            self._bqa = BasicQAManager(qa_data=lr.qa_data())

    def answer(
        self,
        req: ThinkRequest,
        history: list[Turn],
        cancel: CancelToken,
        on_partial: PartialCallback | None = None,
    ) -> BackendAnswer | None:
        if self._bqa is None:
            self.warmup()
        lr, q = self._lr, req.text
        short = _n_words(q) <= MAX_CANNED_WORDS
        basic = strict_basic_answer(self._bqa, q)
        if basic and basic.get("answer"):
            try:
                text = self._bqa.format_answer(basic["answer"])
            except Exception:  # noqa: BLE001
                text = basic["answer"]
            return BackendAnswer(text, basic.get("emotion", "helpful"), "basic_qa", detail="basic_qa")
        fun = lr.match_fun_request(q) if short else None
        if fun == "curious_fact":
            return BackendAnswer(lr.random_fun_fact(), "happy", "basic_qa", detail="fun_fact")
        if fun == "joke":
            return BackendAnswer(lr.random_joke(), "happy", "basic_qa", detail="fun_joke")
        is_address = (_has_word(q, _ADDRESS_WORDS) and _has_word(q, _UNI_WORDS + _WHERE_WORDS)) or (
            _has_word(q, _ADDRESS_WEAK) and _has_word(q, _UNI_WORDS)
        )
        if is_address:
            addr = lr.spoken_udit_address()
            if addr:
                return BackendAnswer(addr, "informative", "rag_local", detail="knowledge_address")
        know = lr.match_knowledge_text(q)
        if know and know[1] == "knowledge_address" and not is_address:
            know = None  # "¿cuánto cuesta el parking del campus?" no es una pregunta por la dirección
        if know and know[1] == "knowledge_udito" and not (short and _has_word(q, _ID_WORDS)):
            know = None  # «UDITO, ¿qué es un máster oficial?» no pregunta quién es UDITO
        if know and know[1] == "knowledge_horarios" and not _has_word(q, _SCHEDULE_WORDS):
            know = None  # "¿cuántas horas es un crédito?" no es una pregunta de horarios
        if know:
            text, src = know
            if src == "knowledge_horarios":
                body = lr.read_knowledge_file("udit_horarios.txt")
                text = self._conv(q, body) if body else ""
            if text:
                emotion = "informative" if "address" in src else "helpful"
                return BackendAnswer(text, emotion, "rag_local", detail=src)
        return None


class LegacyRagBackend:
    name = "rag_local"

    def __init__(
        self,
        repo_root: str | os.PathLike | None = None,
        config_path: str | None = None,
        force_rebuild: bool = False,
    ) -> None:
        self._repo_root = repo_root
        self._config_path = config_path
        self._force_rebuild = force_rebuild
        self._rag = None
        self._ready = threading.Event()
        self._load_lock = threading.Lock()
        self._query_lock = threading.Lock()  # RAGSystem no es thread-safe
        self.load_error: str = ""

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def warmup(self) -> None:
        with self._load_lock:
            if self._ready.is_set():
                return
            try:
                root = find_repo_root(self._repo_root)
                engine_dir = root / "01_SERVICES" / "rag-engine"
                add_to_syspath(engine_dir, root / "04_KNOWLEDGE_CORE")
                cfg = self._config_path or os.getenv(
                    "ROBITA_RAG_CONFIG", str(engine_dir / "config" / "rag_config.json")
                )
                # La config del rag-engine usa rutas relativas a su carpeta
                # ("../../04_KNOWLEDGE_CORE/..."): hay que cambiar el cwd del
                # proceso, igual que hacen ./UDITO y el cognitive_node actual.
                os.chdir(engine_dir)
                from rag_system import RAGSystem  # type: ignore[import-not-found]

                rag = RAGSystem(
                    config_path=str(Path(cfg).resolve()),
                    settings_path=str(engine_dir / "config" / "settings.json"),
                )
                rag.initialize(force_rebuild=self._force_rebuild)
                self._rag = rag
                self._ready.set()
                log.info("RAG local listo (%s)", cfg)
            except Exception as exc:  # noqa: BLE001 — sin RAG seguimos con basic_qa
                self.load_error = f"{type(exc).__name__}: {exc}"
                log.error("RAG local no disponible: %s", self.load_error)

    def answer(
        self,
        req: ThinkRequest,
        history: list[Turn],
        cancel: CancelToken,
        on_partial: PartialCallback | None = None,
    ) -> BackendAnswer | None:
        if not self._ready.is_set():
            return None
        with self._query_lock:
            if cancel.cancelled:
                return None
            result = self._rag.process_query(req.text) or {}
        return map_legacy_result(result)
