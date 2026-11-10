"""Mide la recuperación de un índice con un banco de preguntas etiquetadas.

  python -m cognitive_language.tools.eval_index [--index DIR] [--questions FILE] [--mode dense|hybrid] [-v]

Métricas:
  hit@1 / hit@3   el artículo correcto sale el primero / entre los tres primeros
  MRR             media de 1/posición del artículo correcto
  AUC¬            separación entre preguntas respondibles y no respondibles por la
                  confianza del primer resultado (1.0 = umbral perfecto)
  acc@umbral      aciertos de "respondo / no respondo" con el min_score del manifest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..core.embeddings import MODELS, OnnxEmbedder
from ..core.knowledge import KnowledgeIndex
from ..core.paths import find_repo_root


def evaluate(index: KnowledgeIndex, questions: list[dict], embedder: OnnxEmbedder, mode: str, verbose=False) -> dict:
    thr = index.manifest.get("min_score", 0.0)
    q_emb = embedder.encode_queries([q["q"] for q in questions])
    h1 = h3 = mrr = 0.0
    pos, neg, decisions = [], [], 0
    for q, v in zip(questions, q_emb):
        hits = index.search(v, q["q"], k=10, mode=mode)
        top = hits[0].score
        gold = set(q["gold"])
        answered = top >= thr
        if not gold:
            neg.append(top)
            decisions += not answered
            if verbose:
                print(f"  {'ok ' if not answered else 'MAL'} [{top:.3f}] (no respondible) {q['q']}  → {hits[0].chunk.unit}")
            continue
        pos.append(top)
        decisions += answered
        rank = next((h.rank for h in hits if h.chunk.unit in gold), None)
        if rank is not None:
            h1 += rank == 0
            h3 += rank < 3
            mrr += 1 / (rank + 1)
        if verbose:
            mark = "ok " if rank == 0 else ("~  " if rank is not None and rank < 3 else "MAL")
            print(f"  {mark} [{top:.3f}] {q['q']}  → {hits[0].chunk.unit} (esperado {', '.join(sorted(gold))})")
    n = len(pos)
    auc = float(np.mean([p > x for p in pos for x in neg])) if pos and neg else float("nan")
    return {"hit@1": h1 / n, "hit@3": h3 / n, "mrr": mrr / n, "auc_ans": auc,
            "acc_thr": decisions / len(questions), "min_score": thr, "n_pos": n, "n_neg": len(neg)}


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=root / "04_KNOWLEDGE_CORE/indexes/normativa")
    ap.add_argument("--questions", type=Path, default=root / "04_KNOWLEDGE_CORE/indexes/normativa.eval.json")
    ap.add_argument("--mode", default="", help="dense|hybrid (por defecto, el del manifest)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    index = KnowledgeIndex.load(a.index)
    emb = OnnxEmbedder(MODELS[index.model])
    qs = json.loads(a.questions.read_text(encoding="utf-8"))["questions"]
    r = evaluate(index, qs, emb, a.mode or index.manifest.get("search_mode", "dense"), a.verbose)
    print(f"índice {index.version} · {index.model} · {r['n_pos']} respondibles + {r['n_neg']} no respondibles")
    print(f"hit@1 {r['hit@1']:.2f} · hit@3 {r['hit@3']:.2f} · MRR {r['mrr']:.2f} · "
          f"AUC¬ {r['auc_ans']:.2f} · acc@{r['min_score']:.2f} {r['acc_thr']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
