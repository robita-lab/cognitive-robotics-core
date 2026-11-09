"""Construye el motor a partir de una configuración plana (parámetros ROS o CLI)."""

from __future__ import annotations

from dataclasses import dataclass

from .core import CognitiveEngine, ConversationMemory
from .core.backends import BasicQaBackend, LegacyRagBackend, NormativaBackend, RulesBackend


@dataclass
class EngineConfig:
    repo_root: str = ""          # vacío = autodetectar / $ROBITA_REPO_ROOT
    # Búsqueda en documentos:
    #   "normativa" (por defecto): reglas + índice e5-small ONNX por artículos (sin torch)
    #   "legacy": RAGSystem completo de 01_SERVICES/rag-engine (torch + faiss + PyPDF2)
    #   "none": solo reglas / respuestas fijas
    rag_backend: str = "normativa"
    index_dir: str = ""          # vacío = 04_KNOWLEDGE_CORE/indexes/normativa
    rag_config: str = ""         # solo legacy: vacío = $ROBITA_RAG_CONFIG o rag_config.json
    rag_rebuild: bool = False    # solo legacy
    memory_turns: int = 8
    memory_ttl_s: float = 300.0
    use_rag: bool = True         # compatibilidad: False equivale a rag_backend="none"


def build_engine(cfg: EngineConfig) -> CognitiveEngine:
    root = cfg.repo_root or None
    mode = cfg.rag_backend if cfg.use_rag else "none"
    if mode == "legacy":
        # El RAGSystem ya consulta el Q&A fijo por dentro; basic_qa va detrás para
        # cubrir el arranque (tarda minutos en cargar) y si falla.
        local = [LegacyRagBackend(root, config_path=cfg.rag_config or None, force_rebuild=cfg.rag_rebuild),
                 BasicQaBackend(root)]
    elif mode == "normativa":
        local = [RulesBackend(root), NormativaBackend(cfg.index_dir or None, repo_root=root)]
    elif mode == "none":
        local = [RulesBackend(root)]
    else:
        raise ValueError(f"rag_backend desconocido: {cfg.rag_backend!r} (normativa | legacy | none)")
    memory = ConversationMemory(max_turns=cfg.memory_turns, ttl_s=cfg.memory_ttl_s)
    return CognitiveEngine(local=local, remote=None, memory=memory)
