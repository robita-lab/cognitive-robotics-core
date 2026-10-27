"""Arquitectura 3T - UDITO · Carga y reconocimiento de órdenes (config/intents.yaml).

Lo usan el C.C. (para decidir), el STT (para orientar a Whisper con el
vocabulario de órdenes) y la consola (para listarlas).
"""
from __future__ import annotations

import difflib
import os
import unicodedata
from pathlib import Path

import yaml


def intents_file() -> Path:
    env = os.getenv("UDITO_INTENTS")
    if env:
        return Path(env)
    try:
        from ament_index_python.packages import get_package_share_directory

        return Path(get_package_share_directory("udito_ros")) / "config" / "intents.yaml"
    except Exception:  # noqa: BLE001
        return Path(__file__).resolve().parents[1] / "config" / "intents.yaml"


def load() -> dict:
    data = yaml.safe_load(intents_file().read_text(encoding="utf-8")) or {}
    data.setdefault("intents", [])
    data.setdefault("unknown", {"say": "No conozco esa orden.", "face": "confused"})
    return data


def norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = "".join(c if c.isalnum() or c.isspace() else " " for c in t)
    return " ".join(t.split())


def match(text: str, intents: list[dict], threshold: float = 0.72) -> tuple[dict | None, float]:
    """Devuelve (orden, puntuación 0-1). Tolera errores típicos del reconocimiento de voz."""
    t = norm(text)
    if not t:
        return None, 0.0
    words = t.split()
    padded = f" {t} "
    best, best_score = None, 0.0
    for it in intents:
        for ph in it.get("phrases", []):
            p = norm(ph)
            if not p:
                continue
            # 1) la frase aparece tal cual (las de una palabra solo en órdenes cortas)
            if f" {p} " in padded and (len(p.split()) > 1 or len(words) <= 3):
                score = 1.0
            else:
                # 2) parecido aproximado (STT que entiende «cuánta me lo hiciste» por «cuéntame un chiste»)
                score = difflib.SequenceMatcher(None, t, p).ratio()
            if score > best_score:
                best, best_score = it, score
    return (best, best_score) if best_score >= threshold else (None, best_score)


def vocabulary_prompt(intents: list[dict]) -> str:
    """Frase guía para Whisper: mejora mucho el acierto con órdenes cortas."""
    labels = [it.get("label", "") for it in intents if it.get("label")]
    return "Órdenes a un robot: " + ", ".join(labels) + "."
