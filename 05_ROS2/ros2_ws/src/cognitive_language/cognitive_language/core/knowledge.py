"""Índice de conocimiento documental (normativa) y su búsqueda.

El índice se construye FUERA del robot con `cognitive_language.tools.build_index`
y se versiona en git (04_KNOWLEDGE_CORE/indexes/<nombre>/):

  manifest.json    modelo de embeddings + revisión, versión del chunker, hash de cada fuente
  chunks.jsonl     un chunk por línea: id, doc, unit, heading, text, title
  embeddings.npy   float32 (n_chunks, dim), normalizados

En el robot solo se carga (sin parsear PDF) y se busca: denso (e5) y,
opcionalmente, híbrido con BM25 (palabras exactas: "RAC", "TFG", "B2").
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

CHUNKER_VERSION = "articulos-v2"  # v2: frases con embeddings precalculados


@dataclass(frozen=True)
class Chunk:
    id: str
    doc: str        # código de documento (ACC, RAC...)
    unit: str       # unidad citable: "ACC:4" = artículo 4; "EXT:3" = punto 3; "POL:0" = documento entero
    heading: str    # "ARTÍCULO 4. Vías para el acceso..."
    title: str      # título del documento para decirlo en voz alta
    text: str       # texto del chunk (sin el prefijo de contexto)
    sentences: list[str] = field(default_factory=list)  # candidatas a respuesta extractiva


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float    # coseno denso (0..1): es la confianza que se compara con el umbral
    rank: int
    pos: int = -1   # posición del chunk en el índice


# ------------------------------------------------------------------ BM25
_STOP = {
    "a", "al", "algo", "ante", "antes", "con", "contra", "cual", "cuales", "de", "del", "desde", "donde",
    "el", "ella", "ellas", "ellos", "en", "entre", "era", "es", "esa", "ese", "eso", "esta", "este", "esto",
    "estos", "estas", "fue", "ha", "han", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi",
    "mis", "muy", "ni", "no", "nos", "o", "os", "para", "pero", "por", "que", "quien", "se", "segun", "ser",
    "si", "sin", "sobre", "son", "su", "sus", "te", "tiene", "tu", "tus", "un", "una", "unas", "uno", "unos",
    "y", "ya", "yo", "puedo", "puede", "pueden", "tengo", "hace", "como", "cuando",
}


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    """Minúsculas, sin tildes, sin palabras vacías y truncado a 6 letras (stemming barato)."""
    return [w[:6] for w in re.findall(r"[a-zñ0-9]+", fold(text)) if w not in _STOP and len(w) > 1]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.75) -> None:
        self.tf = [Counter(tokenize(d)) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0.0
        self.df = Counter(w for t in self.tf for w in t)
        self.n, self.k1, self.b = len(docs), k1, b

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float32)
        for w in set(tokenize(query)):
            if w not in self.df:
                continue
            idf = math.log(1 + (self.n - self.df[w] + 0.5) / (self.df[w] + 0.5))
            for i, tf in enumerate(self.tf):
                f = tf.get(w)
                if f:
                    norm = self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
                    out[i] += idf * f * (self.k1 + 1) / (f + norm)
        return out


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    acc: Counter[int] = Counter()
    for r in rankings:
        for pos, idx in enumerate(r):
            acc[idx] += 1.0 / (k + pos + 1)
    return [i for i, _ in acc.most_common()]


_SENT_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-ZÁÉÍÓÚÑ¿¡•(\d])|\s+(?=•)")
_HEADING = re.compile(r"^ART[ÍI]CULO\s+\d+\.\s*")


def answer_sentences(text: str, min_chars: int = 25) -> list[str]:
    """Frases de un chunk que pueden servir de respuesta (sin el "ARTÍCULO N." inicial)."""
    out = []
    for s in _SENT_SPLIT.split(_HEADING.sub("", text)):
        s = s.strip(" •")
        if len(s) >= min_chars:
            out.append(s)
    return out


def passage_text(c: Chunk) -> str:
    """Lo que se embebe: título del documento + encabezado + texto (da contexto a trozos sueltos)."""
    head = c.heading if c.heading and not c.text.startswith(c.heading[:20]) else ""
    return " ".join(p for p in (f"{c.title}.", head, c.text) if p)


# ------------------------------------------------------------------ índice
class KnowledgeIndex:
    def __init__(self, chunks: list[Chunk], embeddings: np.ndarray, manifest: dict,
                 sentence_embeddings: np.ndarray | None = None) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks y embeddings no cuadran")
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.manifest = manifest
        self._bm25: BM25 | None = None
        # Frases: embeddings en un solo array; offset[i] = primera frase del chunk i.
        self.offsets = np.cumsum([0] + [len(c.sentences) for c in chunks])
        if sentence_embeddings is not None and len(sentence_embeddings) != self.offsets[-1]:
            raise ValueError("frases y sentence_embeddings no cuadran")
        self.sentence_embeddings = sentence_embeddings

    def chunk_sentence_vectors(self, chunk_pos: int) -> np.ndarray | None:
        if self.sentence_embeddings is None:
            return None
        return self.sentence_embeddings[self.offsets[chunk_pos]:self.offsets[chunk_pos + 1]]

    @property
    def model(self) -> str:
        return self.manifest.get("embedding_model", "")

    @property
    def version(self) -> str:
        return self.manifest.get("version", "")

    @classmethod
    def load(cls, directory: str | Path) -> "KnowledgeIndex":
        d = Path(directory)
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        chunks = [Chunk(**json.loads(line)) for line in (d / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        sent = d / "sentence_embeddings.npy"
        return cls(chunks, np.load(d / "embeddings.npy"), manifest, np.load(sent) if sent.is_file() else None)

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with open(d / "chunks.jsonl", "w", encoding="utf-8") as f:
            for c in self.chunks:
                f.write(json.dumps(c.__dict__, ensure_ascii=False) + "\n")
        np.save(d / "embeddings.npy", self.embeddings)
        if self.sentence_embeddings is not None:
            np.save(d / "sentence_embeddings.npy", self.sentence_embeddings.astype(np.float32))

    def search(self, query_vec: np.ndarray, query_text: str = "", k: int = 3, mode: str = "dense") -> list[Hit]:
        dense = self.embeddings @ query_vec.astype(np.float32)
        order = list(np.argsort(-dense))
        if mode == "hybrid" and query_text:
            if self._bm25 is None:
                self._bm25 = BM25([passage_text(c) for c in self.chunks])
            order = rrf([order, list(np.argsort(-self._bm25.scores(query_text)))])
        return [Hit(self.chunks[i], float(dense[i]), r, int(i)) for r, i in enumerate(order[:k])]
