"""Núcleo cognitivo de ROBITA en Python puro (sin ROS).

Se puede usar y probar sin ROS: `python -m robita_cognitive.cli "hola"`.
El nodo ROS (robita_cognitive.think_server) es solo una capa fina encima.
"""

from .engine import EMPTY_TEXT, FALLBACK_TEXT, CognitiveEngine
from .memory import ConversationMemory
from .sentences import SentenceAccumulator, split_sentences
from .types import BackendAnswer, CancelToken, ThinkRequest, ThinkResult, Turn

__all__ = [
    "BackendAnswer",
    "CancelToken",
    "CognitiveEngine",
    "ConversationMemory",
    "EMPTY_TEXT",
    "FALLBACK_TEXT",
    "SentenceAccumulator",
    "ThinkRequest",
    "ThinkResult",
    "Turn",
    "split_sentences",
]
