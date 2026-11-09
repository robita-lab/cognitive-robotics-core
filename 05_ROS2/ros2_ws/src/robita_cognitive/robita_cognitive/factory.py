"""Construye el motor a partir de una configuración plana (parámetros ROS o CLI)."""

from __future__ import annotations

from dataclasses import dataclass

from .core import CognitiveEngine, ConversationMemory
from .core.backends import BasicQaBackend, LegacyRagBackend


@dataclass
class EngineConfig:
    repo_root: str = ""          # vacío = autodetectar / $ROBITA_REPO_ROOT
    use_rag: bool = True         # False = solo respuestas fijas (arranque instantáneo)
    rag_config: str = ""         # vacío = $ROBITA_RAG_CONFIG o rag_config.json
    rag_rebuild: bool = False
    memory_turns: int = 8
    memory_ttl_s: float = 300.0


def build_engine(cfg: EngineConfig) -> CognitiveEngine:
    root = cfg.repo_root or None
    local = []
    if cfg.use_rag:
        # El RAG ya consulta el Q&A fijo por dentro; basic_qa va detrás para
        # cubrir el arranque (el RAG tarda minutos en cargar) y si el RAG falla.
        local.append(
            LegacyRagBackend(root, config_path=cfg.rag_config or None, force_rebuild=cfg.rag_rebuild)
        )
    local.append(BasicQaBackend(root))
    memory = ConversationMemory(max_turns=cfg.memory_turns, ttl_s=cfg.memory_ttl_s)
    return CognitiveEngine(local=local, remote=None, memory=memory)
