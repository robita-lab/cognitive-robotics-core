"""Construye un índice de conocimiento a partir de documentos (PDF/TXT).

  python -m cognitive_language.tools.build_index 04_KNOWLEDGE_CORE/indexes/normativa.sources.json

Se ejecuta FUERA del robot (portátil o servidor), una vez por cambio de
documentos; el resultado (04_KNOWLEDGE_CORE/indexes/<nombre>/) se commitea.
Así el robot no parsea PDF nunca.

Pasos: extraer texto (pypdf) → quitar cabeceras/pies repetidos y números de
página → partir en unidades citables (artículos, puntos numerados o el
documento entero) → trocear las largas por frases (≤ max_chars) → embeddings
(e5-small ONNX, mismo código que en el robot) → guardar con manifest.

Dependencias de construcción: pypdf, numpy, onnxruntime, tokenizers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from ..core.embeddings import MODELS, E5_SMALL, OnnxEmbedder
from ..core.knowledge import CHUNKER_VERSION, Chunk, KnowledgeIndex, answer_sentences, passage_text
from ..core.paths import find_repo_root

PATTERNS = {
    "articulos": re.compile(r"(?m)^\s*ART[ÍI]CULO\s+(\d+)\.?"),
    "puntos": re.compile(r"(?m)^\s*(\d{1,2})\.\s+(?=[A-ZÁÉÍÓÚ])"),
}


# ------------------------------------------------------------------ texto
def read_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        import pypdf

        return [p.extract_text() or "" for p in pypdf.PdfReader(str(path)).pages]
    return [path.read_text(encoding="utf-8")]


def clean_pages(pages: list[str]) -> str:
    """Quita números de página y líneas que se repiten en muchas páginas (cabeceras/pies)."""
    def key(line: str) -> str:
        return re.sub(r"\s*\d+\s*$", "", " ".join(line.split()))

    lines_per_page = [[ln for ln in p.splitlines()] for p in pages]
    repeated: set[str] = set()
    if len(pages) >= 3:
        cnt = Counter(k for lines in lines_per_page for k in {key(ln) for ln in lines if key(ln)})
        repeated = {k for k, n in cnt.items() if n >= max(3, len(pages) // 2) and len(k) < 120}
    kept = []
    for lines in lines_per_page:
        for ln in lines:
            s = ln.strip()
            if not s or re.fullmatch(r"\d{1,3}", s) or key(s) in repeated:
                continue
            kept.append(re.sub(r"[ \t]+", " ", s))
    return "\n".join(kept)


def split_units(text: str, code: str, structure: str) -> list[tuple[str, str, str]]:
    """[(unit_id, heading, cuerpo)]. La unidad 0 es el preámbulo (o el documento entero)."""
    pat = PATTERNS.get(structure)
    marks = [(int(m.group(1)), m.start()) for m in pat.finditer(text)] if pat else []
    if structure == "puntos":  # sólo la secuencia 1, 2, 3... (evita "1 Marzo 2021")
        seq, want = [], 1
        for n, s in marks:
            if n == want:
                seq.append((n, s))
                want += 1
        marks = seq
    units = []
    first = marks[0][1] if marks else len(text)
    pre = " ".join(text[:first].split())
    if pre:
        units.append((f"{code}:0", "", pre))
    for i, (n, s) in enumerate(marks):
        e = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        body = " ".join(text[s:e].split())
        heading = " ".join(body.split()[:12]) if structure == "articulos" else ""
        units.append((f"{code}:{n}", heading, body))
    return units


def split_long(body: str, max_chars: int) -> list[str]:
    pieces = re.split(r"(?<=[.;:])\s+|\s+(?=•)|\s+(?=\d{1,2}\.\s)", body)
    parts, buf = [], ""
    for p in pieces:
        if buf and len(buf) + len(p) + 1 > max_chars:
            parts.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        parts.append(buf)
    return parts


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ build
def build(sources_file: Path, out_dir: Path | None = None, repo_root: Path | None = None,
          embedder: OnnxEmbedder | None = None) -> KnowledgeIndex:
    spec = json.loads(sources_file.read_text(encoding="utf-8"))
    root = repo_root or find_repo_root()
    max_chars = int(spec.get("max_chars", 900))
    model = MODELS[spec.get("embedding_model", E5_SMALL.name)]
    embedder = embedder or OnnxEmbedder(model)

    chunks: list[Chunk] = []
    sources = []
    for d in spec["documents"]:
        path = root / d["path"]
        pages = read_pages(path)
        text = clean_pages(pages)
        units = split_units(text, d["code"], d.get("structure", "entero"))
        n_before = len(chunks)
        for uid, heading, body in units:
            if len(body) < 40:
                continue
            for j, part in enumerate(split_long(body, max_chars)):
                chunks.append(Chunk(id=f"{uid}#{j}", doc=d["code"], unit=uid, heading=heading,
                                    title=d["title"], text=part, sentences=answer_sentences(part)))
        sources.append({"code": d["code"], "path": d["path"], "sha256": sha256(path), "pages": len(pages),
                        "units": len(units), "chunks": len(chunks) - n_before})
        print(f"  {d['code']}: {len(pages)} págs → {len(units)} unidades → {len(chunks) - n_before} chunks", file=sys.stderr)

    emb = embedder.encode_passages([passage_text(c) for c in chunks])
    sent_emb = embedder.encode_passages([s for c in chunks for s in c.sentences])
    fingerprint = hashlib.sha256(
        json.dumps([sources, CHUNKER_VERSION, model.name, model.revision, max_chars], sort_keys=True).encode()
    ).hexdigest()[:10]
    manifest = {
        "name": spec["name"],
        "version": f"{date.today().isoformat()}-{fingerprint}",
        "fingerprint": fingerprint,
        "embedding_model": model.name,
        "model_revision": model.revision,
        "dim": int(emb.shape[1]),
        "chunker": CHUNKER_VERSION,
        "max_chars": max_chars,
        "min_score": float(spec.get("min_score", 0.84)),
        "search_mode": spec.get("search_mode", "dense"),
        "n_chunks": len(chunks),
        "n_sentences": int(len(sent_emb)),
        "sources": sources,
    }
    index = KnowledgeIndex(chunks, emb, manifest, sent_emb)
    out = out_dir or (sources_file.parent / spec["name"])
    old = out / "manifest.json"
    if old.is_file() and json.loads(old.read_text()).get("fingerprint") == fingerprint:
        print(f"sin cambios (fingerprint {fingerprint}); no reescribo {out}", file=sys.stderr)
        return KnowledgeIndex.load(out)
    index.save(out)
    print(f"índice {manifest['version']}: {len(chunks)} chunks → {out}", file=sys.stderr)
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", type=Path, help="fichero *.sources.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--repo-root", type=Path, default=None)
    a = ap.parse_args(argv)
    build(a.sources, a.out, a.repo_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
