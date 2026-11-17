"""Tests del índice de normativa y su backend (sin modelo: embedder falso por hashing)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from cognitive_language.core import CancelToken, ThinkRequest
from cognitive_language.core.backends import NormativaBackend
from cognitive_language.core.backends.legacy import _has_word
from cognitive_language.core.backends.normativa import cite
from cognitive_language.core.knowledge import BM25, Chunk, KnowledgeIndex, answer_sentences, tokenize
from cognitive_language.tools.build_index import clean_pages, split_long, split_units


class HashEmbedder:
    """Bolsa de palabras con hashing: parecido léxico ≈ parecido "semántico". Determinista."""

    name = "fake/hash"
    dim = 256

    def load(self):
        pass

    def _vec(self, text):
        v = np.zeros(self.dim, np.float32)
        for w in tokenize(text):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode_queries(self, texts):
        return np.vstack([self._vec(t) for t in texts])

    encode_passages = encode_queries


CHUNKS = [
    Chunk("ACC:7#0", "ACC", "ACC:7", "ARTÍCULO 7. Requisitos documentales", "normativa de acceso",
          "ARTÍCULO 7. Requisitos documentales. Todos los documentos expedidos en idioma extranjero deberán "
          "acompañarse de su traducción jurada al español. No se exige legalización en la Unión Europea."),
    Chunk("RAC:4#0", "RAC", "RAC:4", "ARTÍCULO 4. Reconocimiento por actividades deportivas", "normativa del RAC",
          "ARTÍCULO 4. Reconocimiento por actividades deportivas. Se podrán reconocer un máximo de 2 ECTS por "
          "curso académico por actividades deportivas."),
    Chunk("EXT:5#0", "EXT", "EXT:5", "", "normativa de extinción",
          "5. En ninguna se concederá convocatoria de gracia en titulaciones a extinguir."),
]


def make_index(min_score=0.3, with_sentences=True):
    emb = HashEmbedder()
    chunks = [Chunk(**{**c.__dict__, "sentences": answer_sentences(c.text)}) if with_sentences else c for c in CHUNKS]
    sent = emb.encode_passages([s for c in chunks for s in c.sentences]) if with_sentences else None
    manifest = {"embedding_model": emb.name, "min_score": min_score, "fingerprint": "abc", "search_mode": "dense"}
    return KnowledgeIndex(chunks, emb.encode_passages([c.text for c in chunks]), manifest, sent), emb


def backend(tmp_path, **kw):
    index, emb = make_index(**kw)
    index.save(tmp_path / "idx")
    b = NormativaBackend(tmp_path / "idx", embedder=emb)
    b.warmup()
    assert b.ready, b.load_error
    return b


# ------------------------------------------------------------------ texto
def test_tokenize_folds_accents_and_stems():
    assert tokenize("¿Qué TRADUCCIÓN jurada?") == ["traduc", "jurada"]


def test_answer_sentences_strip_heading():
    s = answer_sentences(CHUNKS[0].text)
    assert not any("ARTÍCULO" in x for x in s)
    assert s[0].startswith("Todos los documentos")  # "Requisitos documentales." es corta y se descarta


def test_bm25_prefers_matching_doc():
    bm = BM25([c.text for c in CHUNKS])
    assert int(np.argmax(bm.scores("convocatoria de gracia"))) == 2


def test_clean_pages_removes_headers_and_page_numbers():
    pages = [f"Normativa X {i}\n{i}\nTexto de la página {i}." for i in range(1, 5)]
    out = clean_pages(pages)
    assert "Normativa X" not in out and "\n2\n" not in out
    assert "Texto de la página 3." in out


def test_split_units_articles_and_points():
    arts = split_units("Preámbulo largo del documento.\nARTÍCULO 1. Objeto\nbla.\nARTÍCULO 2. Otro\nble.", "ACC", "articulos")
    assert [u[0] for u in arts] == ["ACC:0", "ACC:1", "ACC:2"]
    pts = split_units("Edición 1 Marzo 2021\n1. Primero algo.\n2. Segundo algo.\n7. Suelto.", "EXT", "puntos")
    assert [u[0] for u in pts] == ["EXT:0", "EXT:1", "EXT:2"]  # el "7." fuera de secuencia no corta


def test_split_long_respects_max():
    parts = split_long("Frase uno es larga. " * 30, 120)
    assert all(len(p) <= 120 for p in parts) and len(parts) > 1


def test_cite():
    assert cite("ACC:7", "normativa de acceso") == "Según el artículo 7 de la normativa de acceso"
    assert cite("EXT:5", "normativa de extinción") == "Según la normativa de extinción"
    assert cite("ACC:0", "normativa de acceso") == "Según la normativa de acceso"


def test_rules_whole_word():
    assert _has_word("¿A qué hora abre?", ("hora",))
    assert not _has_word("¿Cuántas horas es un crédito?", ("hora",))
    assert _has_word("¿Dónde está la universidad?", ("donde esta",))


# ------------------------------------------------------------------ índice
def test_index_roundtrip(tmp_path):
    index, _ = make_index()
    index.save(tmp_path / "i")
    back = KnowledgeIndex.load(tmp_path / "i")
    assert [c.id for c in back.chunks] == [c.id for c in index.chunks]
    assert back.sentence_embeddings.shape == index.sentence_embeddings.shape
    assert back.chunk_sentence_vectors(1).shape[0] == len(back.chunks[1].sentences)


# ------------------------------------------------------------------ backend
def test_answers_with_citation(tmp_path):
    b = backend(tmp_path)
    ans = b.answer(ThinkRequest("s", "¿Tengo que presentar traducción jurada de documentos en idioma extranjero?"),
                   [], CancelToken())
    assert ans is not None
    assert ans.text.startswith("Según el artículo 7 de la normativa de acceso:")
    assert "traducción jurada" in ans.text
    assert ans.detail == "normativa:ACC:7@abc"


def test_answers_without_precomputed_sentences(tmp_path):
    b = backend(tmp_path, with_sentences=False)
    ans = b.answer(ThinkRequest("s", "convocatoria de gracia titulaciones a extinguir"), [], CancelToken())
    assert ans is not None and "gracia" in ans.text


def test_abstains_below_threshold(tmp_path):
    b = backend(tmp_path, min_score=0.3)
    assert b.answer(ThinkRequest("s", "¿Quién ganó el mundial de fútbol?"), [], CancelToken()) is None


def test_model_mismatch_is_reported(tmp_path):
    index, _ = make_index()
    index.save(tmp_path / "idx")

    class Other(HashEmbedder):
        name = "other/model"

    b = NormativaBackend(tmp_path / "idx", embedder=Other())
    b.warmup()
    assert not b.ready and "other/model" in b.load_error


def test_not_ready_returns_none(tmp_path):
    b = NormativaBackend(tmp_path / "no_existe", embedder=HashEmbedder())
    b.warmup()
    assert not b.ready
    assert b.answer(ThinkRequest("s", "hola"), [], CancelToken()) is None


@pytest.mark.parametrize("mode", ["dense", "hybrid"])
def test_search_modes(mode):
    index, emb = make_index()
    hits = index.search(emb.encode_queries(["actividades deportivas ECTS"])[0], "actividades deportivas ECTS", k=2, mode=mode)
    assert hits[0].chunk.unit == "RAC:4" and hits[0].pos == 1
