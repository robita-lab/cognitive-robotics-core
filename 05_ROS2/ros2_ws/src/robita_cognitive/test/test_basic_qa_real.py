"""Integración con el Q&A fijo real del repo (solo stdlib, sin modelos)."""

from __future__ import annotations

import pytest

from robita_cognitive.core import CognitiveEngine, ThinkRequest
from robita_cognitive.core.backends import BasicQaBackend
from robita_cognitive.core.paths import find_repo_root

try:
    find_repo_root()
except FileNotFoundError:  # paquete instalado fuera del repo
    pytest.skip("repo no localizable (define ROBITA_REPO_ROOT)", allow_module_level=True)


def test_greeting_answered_by_basic_qa():
    eng = CognitiveEngine([BasicQaBackend()])
    r = eng.think(ThinkRequest(session_id="t", text="hola"))
    assert r.source == "basic_qa"
    assert r.text


def test_academic_question_not_answered_by_basic_qa():
    eng = CognitiveEngine([BasicQaBackend()])
    r = eng.think(ThinkRequest(session_id="t", text="¿cuáles son los requisitos de admisión del máster?"))
    assert r.source == "fallback"
