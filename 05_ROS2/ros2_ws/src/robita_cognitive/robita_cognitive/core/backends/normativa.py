"""Backend de normativa: búsqueda en el índice + respuesta extractiva citada.

Sin LLM en el robot, la respuesta es la frase de la normativa que mejor
contesta, elegida entre los 3 chunks más parecidos, y se cita el artículo:
"Según el artículo 8 de la normativa de acceso y admisión: ...".
Con el LLM del servidor (P2) estos mismos chunks serán su contexto.

Si la confianza del mejor chunk no llega al umbral (min_score del manifest),
devuelve None: el robot no responde con texto que no viene al caso.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import numpy as np

from ..embeddings import MODELS, OnnxEmbedder
from ..knowledge import Hit, KnowledgeIndex, answer_sentences
from ..paths import find_repo_root
from ..types import BackendAnswer, CancelToken, PartialCallback, ThinkRequest, Turn

log = logging.getLogger("robita_cognitive.normativa")

def cite(unit: str, title: str) -> str:
    code, _, n = unit.partition(":")
    if n and n != "0" and code in {"ACC", "RAC", "CON"}:
        return f"Según el artículo {n} de la {title}"
    return f"Según la {title}"


def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in (". ", "; ", ", ", " "):
        i = cut.rfind(sep)
        if i > max_chars * 0.6:
            return cut[:i].rstrip(",;: ") + "…"
    return cut + "…"


class NormativaBackend:
    name = "rag_local"

    def __init__(self, index_dir: str | os.PathLike | None = None, repo_root: str | os.PathLike | None = None,
                 embedder: OnnxEmbedder | None = None, min_score: float | None = None,
                 mode: str | None = None, max_chars: int = 320, top_k: int = 3) -> None:
        self._index_dir = index_dir
        self._repo_root = repo_root
        self._embedder = embedder
        self._min_score = min_score
        self._mode = mode
        self.max_chars = max_chars
        self.top_k = top_k
        self.index: KnowledgeIndex | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self.load_error = ""

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    @property
    def min_score(self) -> float:
        if self._min_score is not None:
            return self._min_score
        return float(self.index.manifest.get("min_score", 0.84)) if self.index else 0.84

    def warmup(self) -> None:
        with self._lock:
            if self._ready.is_set():
                return
            try:
                d = Path(self._index_dir) if self._index_dir else \
                    find_repo_root(self._repo_root) / "04_KNOWLEDGE_CORE" / "indexes" / "normativa"
                index = KnowledgeIndex.load(d)
                emb = self._embedder or OnnxEmbedder(MODELS[index.model])
                if emb.name != index.model:
                    raise ValueError(f"el índice se hizo con {index.model} y el embedder es {emb.name}")
                emb.load()
                self.index, self._embedder = index, emb
                self._mode = self._mode or index.manifest.get("search_mode", "dense")
                self._ready.set()
                log.info("normativa lista: índice %s (%d chunks)", index.version, len(index.chunks))
            except Exception as exc:  # noqa: BLE001 — sin índice seguimos con el resto de backends
                self.load_error = f"{type(exc).__name__}: {exc}"
                log.error("normativa no disponible: %s", self.load_error)

    # ------------------------------------------------------------------
    def embed_query(self, text: str) -> np.ndarray:
        return self._embedder.encode_queries([text])[0]

    def retrieve(self, text: str, q: np.ndarray | None = None) -> list[Hit]:
        q = self.embed_query(text) if q is None else q
        return self.index.search(q, text, k=self.top_k, mode=self._mode)

    def compose(self, text: str, hits: list[Hit], q: np.ndarray | None = None) -> tuple[str, Hit]:
        """Mejor frase entre los chunks recuperados (+ la siguiente si se queda corta)."""
        q = self.embed_query(text) if q is None else q
        cands: list[tuple[Hit, int, list[str]]] = []
        vec_blocks = []
        for h in hits:
            sents = h.chunk.sentences or answer_sentences(h.chunk.text)
            pre = self.index.chunk_sentence_vectors(h.pos) if h.chunk.sentences and h.pos >= 0 else None
            vec_blocks.append(pre if pre is not None and len(pre) else
                              (self._embedder.encode_passages(sents) if sents else None))
            cands.extend((h, i, sents) for i in range(len(sents)))
        if not cands:
            return _shorten(hits[0].chunk.text, self.max_chars), hits[0]
        vecs = np.vstack([v for v in vec_blocks if v is not None])
        # Pequeño sesgo a favor del chunk mejor recuperado: desempata frases parecidas.
        bonus = np.array([0.01 * (len(hits) - c[0].rank) for c in cands], dtype=np.float32)
        best = int(np.argmax(vecs @ q + bonus))
        hit, i, sents = cands[best]
        answer = sents[i]
        if (len(answer) < 140 or answer.endswith(":")) and i + 1 < len(sents):
            answer = f"{answer} {sents[i + 1]}"
        answer = answer[0].upper() + answer[1:]
        return f"{cite(hit.chunk.unit, hit.chunk.title)}: {_shorten(answer, self.max_chars)}", hit

    def answer(self, req: ThinkRequest, history: list[Turn], cancel: CancelToken,
               on_partial: PartialCallback | None = None) -> BackendAnswer | None:
        if not self._ready.is_set():
            return None
        q = self.embed_query(req.text)
        hits = self.retrieve(req.text, q)
        if not hits or hits[0].score < self.min_score:
            log.info("normativa: confianza %.3f < %.2f, me abstengo", hits[0].score if hits else 0, self.min_score)
            return None
        if cancel.cancelled:
            return None
        text, hit = self.compose(req.text, hits, q)
        return BackendAnswer(
            text=text, emotion="helpful", source="rag_local",
            detail=f"normativa:{hit.chunk.unit}@{self.index.manifest.get('fingerprint', '')}",
        )
