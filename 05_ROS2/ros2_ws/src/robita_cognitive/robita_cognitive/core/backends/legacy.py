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

log = logging.getLogger("robita_cognitive.legacy")

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
        r = self._mgr.find_basic_answer(req.text)
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
