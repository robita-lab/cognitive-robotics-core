"""Arquitectura híbrida - UDITO · Rutas del repo y acceso a los motores de 01_SERVICES.

Los nodos ROS 2 NO duplican los motores (Whisper, Piper, RAG): los importan
desde el repo. Los módulos de voz, rostro y audio que usan las habilidades
viven en 01_SERVICES/voice-face-engine.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/opt/cognitive-robotics-core")


def repo_root() -> Path:
    env = os.getenv("ROBITA_ROOT")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "01_SERVICES").is_dir() and (p / "05_ROS2").is_dir():
            return p
    return DEFAULT_ROOT


ROOT = repo_root()
SERVICES = ROOT / "01_SERVICES"
MODULES = ROOT / "01_SERVICES" / "voice-face-engine"
ADAPTER = MODULES  # nombre anterior, se mantiene por compatibilidad
KNOWLEDGE = ROOT / "04_KNOWLEDGE_CORE"
RESPONSES = KNOWLEDGE / "responses"


def add_engine_paths(*services: str) -> None:
    """Añade al sys.path los módulos del robot, el knowledge core y los servicios pedidos."""
    for p in [MODULES, KNOWLEDGE, *[SERVICES / s for s in services]]:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
