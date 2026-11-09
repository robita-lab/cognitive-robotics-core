"""Prueba el motor cognitivo sin ROS.

  python -m robita_cognitive.cli "¿quién eres?"          # una pregunta
  python -m robita_cognitive.cli                          # modo interactivo
  python -m robita_cognitive.cli --no-rag "hola"          # solo reglas / respuestas fijas
  python -m robita_cognitive.cli --rag legacy "..."       # RAGSystem antiguo (torch)
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

from .core import ThinkRequest
from .factory import EngineConfig, build_engine


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="*", help="pregunta; sin argumentos = interactivo")
    ap.add_argument("--rag", default="normativa", choices=["normativa", "legacy", "none"],
                    help="búsqueda en documentos (por defecto normativa)")
    ap.add_argument("--no-rag", action="store_true", help="atajo de --rag none")
    ap.add_argument("--repo-root", default="")
    ap.add_argument("--rag-config", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    engine = build_engine(
        EngineConfig(repo_root=args.repo_root, rag_backend="none" if args.no_rag else args.rag,
                     rag_config=args.rag_config)
    )
    # En la CLI cargamos todo antes de preguntar (en el nodo es en segundo plano).
    for b in engine.local:
        b.warmup()
    print(f"backends: {engine.status()}", file=sys.stderr)

    session = f"cli-{uuid.uuid4().hex[:8]}"
    questions = [" ".join(args.question)] if args.question else None
    turn = 0
    while True:
        if questions is not None:
            if not questions:
                return 0
            q = questions.pop()
        else:
            try:
                q = input("tú> ")
            except EOFError:
                return 0
            if q.strip() in {"salir", "exit", "quit"}:
                return 0
        turn += 1
        r = engine.think(
            ThinkRequest(session_id=session, turn_id=str(turn), text=q),
            on_partial=lambda s, i: print(f"  [{i}] {s}", file=sys.stderr) if args.verbose else None,
        )
        print(f"udito> {r.text}")
        print(f"       ({r.source}/{r.detail}, {r.emotion}, {r.latency_ms:.0f} ms)", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
