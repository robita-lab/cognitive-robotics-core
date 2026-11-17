"""Evalúa el motor completo con un LLM del servidor: datos clave, estilo de voz y latencias.

  COGNITIVE_LLM_API_KEY=... python -m cognitive_language.tools.eval_llm --url http://servidor:8080 --label qwen3-4b
  python -m cognitive_language.tools.eval_llm --label local            # sin LLM (referencia)

Cada pregunta lleva el dato que debe aparecer en la respuesta. La comprobación
es automática y aproximada: revisa siempre las respuestas (--out guarda JSONL
con todo) antes de sacar conclusiones. Resultados de 2026-11-09 en
docs/RAG_NORMATIVA.md §8.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
import unicodedata

from ..core import ThinkRequest
from ..factory import EngineConfig, build_engine

QUESTIONS: list[tuple[str, list[str]]] = [
    ("¿Tengo que traducir mis documentos si están en otro idioma?", ["jurada"]),
    ("¿Hace falta legalizar los títulos extranjeros?", ["union europea", "eees", "espacio europeo", "apostilla"]),
    ("¿Qué nivel de inglés me piden?", ["b2"]),
    ("¿Hay plazas reservadas para personas con discapacidad?", ["5 %", "5%", "cinco por ciento"]),
    ("¿Cuántos créditos me pueden reconocer como máximo por actividades?", ["6 ", "seis"]),
    ("¿Cuántas horas equivalen a un crédito ECTS?", ["25", "veinticinco"]),
    ("¿Me reconocen créditos por hacer deporte?", ["ects", "credito"]),
    ("¿Los créditos reconocidos cuentan para la nota media?",
     ["apto", "comput", "no cuenta", "no se tiene en cuenta", "no se tendra en cuenta", "no afecta", "no se incluyen"]),
    ("¿Me devuelven el dinero de la matrícula si me echo atrás?",
     ["no es reembolsable", "no se devuelve", "no reembolsable", "no te devuelven", "no se reembolsa"]),
    ("¿Cuándo se paga la renovación de la matrícula?", ["julio"]),
    ("¿La matrícula incluye seguro escolar?", ["28", "veintiocho"]),
    ("¿Cuántas convocatorias tengo si mi título se extingue?", ["cuatro", "4 convocatorias"]),
    ("¿Hay convocatoria de gracia en titulaciones a extinguir?",
     ["no se concede", "no hay", "ninguna", "no se concedera", "no existe", "no tendras", "no tienes"]),
    ("¿Cuál es la misión de la universidad?", ["diseno", "innovacion", "tecnologia"]),
    ("¿Qué necesito para entrar en un grado si tengo bachillerato?", ["evau", "ebau", "pau", "selectividad", "prueba"]),
    ("¿Qué es un agujero negro?", ["gravedad", "gravit"]),
    ("¿Quién escribió el Quijote?", ["cervantes"]),
    ("¿Cuál es la capital de Australia?", ["canberra"]),
]
N_NORMATIVA = 15


def fold(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def run(label: str, url: str) -> list[dict]:
    engine = build_engine(EngineConfig(llm_url=url))
    for b in engine.local:
        b.warmup()
    if engine.remote:  # cargar el modelo en el servidor antes de medir
        engine.think(ThinkRequest(session_id="warmup", text="¿Qué es la fotosíntesis?"))
    rows = []
    for i, (q, keys) in enumerate(QUESTIONS):
        t0, first = time.monotonic(), []
        r = engine.think(ThinkRequest(session_id=f"{label}-{i}", turn_id=str(i), text=q),
                         on_partial=lambda s, idx: first.append(time.monotonic() - t0) if not first else None)
        rows.append({
            "label": label, "q": q, "ok": any(fold(k) in fold(r.text) for k in keys),
            "style": not any(m in r.text for m in ("*", "#", "http", "[", "\n")),
            "source": r.source, "detail": r.detail, "model": r.model_id,
            "first_ms": round(first[0] * 1000) if first else None, "total_ms": round(r.latency_ms), "text": r.text,
        })
    return rows


def summary(rows: list[dict]) -> str:
    n, g = rows[:N_NORMATIVA], rows[N_NORMATIVA:]
    llm = [x for x in rows if x["source"] == "llm_server"]
    fm = sorted(x["first_ms"] for x in llm if x["first_ms"])
    pct = lambda a, q: f"{a[min(len(a) - 1, int(q * len(a)))]} ms" if a else "-"
    return (f"{rows[0]['label']}: normativa {sum(x['ok'] for x in n)}/{len(n)} · general {sum(x['ok'] for x in g)}/{len(g)}"
            f" · estilo voz {sum(x['style'] for x in rows)}/{len(rows)} · por LLM {len(llm)}/{len(rows)}"
            f" · 1ª frase p50 {pct(fm, .5)} p90 {pct(fm, .9)} · total p50 {st.median(x['total_ms'] for x in rows):.0f} ms")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="", help="llm-engine (vacío = solo local)")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="", help="JSONL con todas las respuestas")
    ap.add_argument("-v", "--verbose", action="store_true", help="imprime cada respuesta")
    a = ap.parse_args(argv)
    rows = run(a.label or (a.url or "local"), a.url)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if a.verbose:
        for r in rows:
            print(f"{'✓' if r['ok'] else '✗'}{'' if r['style'] else ' [estilo]'} {r['q']}\n    [{r['detail']}] {r['text']}")
    print(summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
