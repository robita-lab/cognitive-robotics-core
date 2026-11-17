"""Pure-Python intent router.

Decides which tier (local on-robot, server GPU) should handle a given user
utterance. No ROS imports — safe to use from a plain CLI, unit tests, or a
web handler.

The classifier is deliberately simple (regex / keyword) for v1. Replace with
a small classifier in v2 once transcripts are available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Tier = Literal["local", "server"]
Intent = str


@dataclass(frozen=True)
class RoutingDecision:
    tier: Tier
    intent: Intent


_NORMALISE = re.compile(r"[¿?¡!.,;:]")


def _normalise(text: str) -> str:
    return _NORMALISE.sub("", text.strip().lower())


_GREETINGS = {
    "hola", "buenas", "buenos dias", "buenos días", "buenas tardes",
    "buenas noches", "hola udito", "qué tal", "que tal", "hey",
    "adios", "adiós", "hasta luego", "hasta pronto", "chao", "chau",
}

_ACKS = {
    "si", "sí", "no", "vale", "ok", "okey", "de acuerdo", "perfecto",
    "gracias", "muchas gracias", "por favor", "claro",
}

_BACKCHANNELS = {
    "mm", "mmm", "ajá", "aja", "ya", "uf", "eh", "ah",
}

_EMOTION_PREFIXES = (
    "estoy ", "me siento ", "me aburro", "me gusta", "te quiero",
    "me alegro", "tengo miedo", "te odio",
)

_FACTUAL_PREFIXES = (
    "que ", "qué ", "quien ", "quién ", "cuando ", "cuándo ",
    "donde ", "dónde ", "por que ", "por qué ", "porque ",
    "como ", "cómo ", "cuanto ", "cuánto ", "cuantos ", "cuántos ",
    "cual ", "cuál ", "cuales ", "cuáles ",
    "puedes decirme ", "sabes ", "dime ", "explícame ", "explicame ",
)

_LONG_UTTERANCE_WORD_THRESHOLD = 8


def route(user_text: str, last_decision: RoutingDecision | None = None) -> RoutingDecision:
    """Return a RoutingDecision for the given utterance.

    Rules, first match wins:

    1. Empty -> local/empty.
    2. Greeting / ack / backchannel / emotion expression -> local.
    3. Factual-query prefix -> server.
    4. Long utterance (>_LONG_UTTERANCE_WORD_THRESHOLD words) -> server.
    5. Multi-turn continuation when previous turn was server -> server.
    6. Default -> server (safer than guessing wrong locally).
    """
    text = _normalise(user_text)
    if not text:
        return RoutingDecision(tier="local", intent="empty")

    if text in _GREETINGS:
        return RoutingDecision(tier="local", intent="greeting")
    if text in _ACKS:
        return RoutingDecision(tier="local", intent="acknowledgement")
    if text in _BACKCHANNELS:
        return RoutingDecision(tier="local", intent="backchannel")
    if text.startswith(_EMOTION_PREFIXES):
        return RoutingDecision(tier="local", intent="emotion_expression")

    if text.startswith(_FACTUAL_PREFIXES):
        return RoutingDecision(tier="server", intent="factual_query")

    if len(text.split()) > _LONG_UTTERANCE_WORD_THRESHOLD:
        return RoutingDecision(tier="server", intent="long_utterance")

    if last_decision is not None and last_decision.tier == "server":
        return RoutingDecision(tier="server", intent="multi_turn_continuation")

    return RoutingDecision(tier="server", intent="unknown")
