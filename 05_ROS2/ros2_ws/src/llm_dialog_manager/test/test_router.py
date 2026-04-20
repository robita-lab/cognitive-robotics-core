"""Pure-Python unit tests for the router.

Runs without ROS; `pytest test/test_router.py` from the package root works.
"""

from llm_dialog_manager.router import RoutingDecision, route


def test_empty_goes_local():
    d = route("")
    assert d.tier == "local"
    assert d.intent == "empty"


def test_greeting_goes_local():
    for utterance in ["Hola", "hola udito", "¡Hola!", "Buenos días", "hasta luego"]:
        d = route(utterance)
        assert d.tier == "local", utterance
        assert d.intent == "greeting", utterance


def test_acknowledgement_goes_local():
    for utterance in ["sí", "Vale.", "Gracias", "de acuerdo"]:
        d = route(utterance)
        assert d.tier == "local", utterance
        assert d.intent == "acknowledgement", utterance


def test_backchannel_goes_local():
    d = route("mmm")
    assert d.tier == "local"
    assert d.intent == "backchannel"


def test_emotion_goes_local():
    d = route("Estoy triste")
    assert d.tier == "local"
    assert d.intent == "emotion_expression"


def test_factual_query_goes_server():
    for utterance in [
        "¿Qué es un robot social?",
        "Quién fundó ROBITA-LAB",
        "Cómo funciona el motor",
        "Dime cuánto pesa UDITO",
    ]:
        d = route(utterance)
        assert d.tier == "server", utterance
        assert d.intent == "factual_query", utterance


def test_long_utterance_goes_server():
    utterance = "cuéntame algo interesante porque quiero aprender más sobre ti hoy mismo"
    d = route(utterance)
    assert d.tier == "server"
    assert d.intent == "long_utterance"


def test_multi_turn_continuation_sticks_to_server():
    prev = RoutingDecision(tier="server", intent="factual_query")
    d = route("y entonces?", last_decision=prev)
    assert d.tier == "server"
    assert d.intent == "multi_turn_continuation"


def test_unknown_short_default_goes_server():
    d = route("xyzzy", last_decision=None)
    assert d.tier == "server"
    assert d.intent == "unknown"


def test_punctuation_stripping():
    d = route("¿¿¿Hola??? ")
    assert d.tier == "local"
    assert d.intent == "greeting"
