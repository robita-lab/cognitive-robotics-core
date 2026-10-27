"""Arquitectura 3T - UDITO · Rutas del repo y acceso a los motores de 01_SERVICES.

Los nodos ROS 2 NO duplican los motores (Whisper, Piper, RAG): los importan
directamente desde el repo. Así el mismo código sirve con o sin ROS 2.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    env = os.getenv("ROBITA_ROOT")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "01_SERVICES").is_dir() and (p / "04_KNOWLEDGE_CORE").is_dir():
            return p
    return Path("/opt/robita-lab")


ROOT = repo_root()
SERVICES = ROOT / "01_SERVICES"
ADAPTER = ROOT / "03_ADAPTERS" / "robot-udit-physical"
KNOWLEDGE = ROOT / "04_KNOWLEDGE_CORE"
RESPONSES = KNOWLEDGE / "responses"


def add_engine_paths(*services: str) -> None:
    """Añade al sys.path el adaptador, el knowledge core y los servicios pedidos."""
    for p in [ADAPTER, KNOWLEDGE, *[SERVICES / s for s in services]]:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
