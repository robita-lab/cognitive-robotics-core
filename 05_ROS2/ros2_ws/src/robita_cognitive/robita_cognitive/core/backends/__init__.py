from .base import Backend
from .legacy import BasicQaBackend, LegacyRagBackend, RulesBackend, map_legacy_result
from .normativa import NormativaBackend

__all__ = ["Backend", "BasicQaBackend", "LegacyRagBackend", "NormativaBackend", "RulesBackend", "map_legacy_result"]
