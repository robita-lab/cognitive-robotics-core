"""Construye el motor a partir de una configuración plana (parámetros ROS o CLI)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .core import CognitiveEngine, ConversationMemory
from .core.backends import (
    BasicQaBackend,
    LegacyRagBackend,
    LlmServerBackend,
    NormativaBackend,
    RulesBackend,
    ScopeGuardBackend,
)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


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
    # LLM del servidor (P2). Vacío = sin backend remoto (todo local).
    # La clave es mejor pasarla por entorno (ROBITA_LLM_API_KEY) que por parámetro.
    llm_url: str = field(default_factory=lambda: os.getenv("ROBITA_LLM_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("ROBITA_LLM_API_KEY", ""))
    llm_first_token_timeout_s: float = field(default_factory=lambda: _env_float("ROBITA_LLM_TIMEOUT", 8.0))
    llm_max_tokens: int = field(default_factory=lambda: int(_env_float("ROBITA_LLM_MAX_TOKENS", 120)))
    llm_retry_after_s: float = 30.0
    # Preguntas sobre UDIT sin respuesta local → "no tengo ese dato" (no al LLM, que inventaría).
    scope_guard: bool = True


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
    if cfg.scope_guard:
        local.append(ScopeGuardBackend())
    memory = ConversationMemory(max_turns=cfg.memory_turns, ttl_s=cfg.memory_ttl_s)
    remote = None
    if cfg.llm_url:
        remote = LlmServerBackend(
            cfg.llm_url, api_key=cfg.llm_api_key, first_token_timeout=cfg.llm_first_token_timeout_s,
            max_tokens=cfg.llm_max_tokens, max_history=2 * cfg.memory_turns, retry_after_s=cfg.llm_retry_after_s,
        )
    return CognitiveEngine(local=local, remote=remote, memory=memory)
