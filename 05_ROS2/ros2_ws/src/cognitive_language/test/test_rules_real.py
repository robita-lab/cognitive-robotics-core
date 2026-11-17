"""Reglas locales (Q&A fijo, chiste, dato curioso, identidad, dirección) con datos reales del repo.

Las frases «no deben» salen de los logs del piloto en la Jetson (2026-11-12/13): con el micro
abierto, una tele y transcripciones con errores disparaban respuestas enlatadas por una
palabra suelta.
"""

from __future__ import annotations

import pytest

from cognitive_language.core import CancelToken, ThinkRequest
from cognitive_language.core.backends import BasicQaBackend, RulesBackend
from cognitive_language.core.paths import find_repo_root

try:
    find_repo_root()
except FileNotFoundError:  # paquete instalado fuera del repo
    pytest.skip("repo no localizable (define COGNITIVE_REPO_ROOT)", allow_module_level=True)


@pytest.fixture(scope="module")
def rules():
    b = RulesBackend()
    b.warmup()
    return b


def ask(backend, text):
    return backend.answer(ThinkRequest(session_id="t", text=text), [], CancelToken())


@pytest.mark.parametrize("text", [
    # Q&A fijo por subcadena o por clave genérica
    "En qué direcciones se imparten en clases de tolerabilidad, pudididad.",  # «parte» en «imparten»
    "¿Qué es un marado oficial?",                                              # «oficial»
    "UDITO QUERES",                                                            # «udit» en «udito»
    "Un robot más reservado, eliminándose a desearle lo mejor en sus nuevos proyectos hoy.",
    "Los robots en la cauda de la jefe de la jefe de la jefe de la jefe de la jefe",
    "Ah, vale, vale, si tí, de robotos.",
    "Y, como lo hicieron, lo hicieron, lo hicieron, lo hicieron, lo hicieron",  # «hicieron»
    "Es esperado para no dejar a la opinión con la imagen de sus protagonistas, muriendo. "
    "Los fans, sí creo que es el final.",                                      # «creo»
    "El YouTube Show Gossop es un autor real en mi sí contra todo, a un escritor fantasma",  # «autor»
    # chiste / dato curioso en frases largas
    "La primera broma de emergencia, literalmente un pecaron, al final, una escena de 30 segundos grabada.",
    "La bomba de la alcunismes espacio durante todo el día. Llegamos a abrir de 2016 y tras los fans.",
    "Amor eterno, detrás de las cámaras, si estaba licuando un enquiel ráquite en el rino, sabías que nos propon.",
    # identidad por oír «UDITO»
    "UDITO, ¿qué es un másteroficial?",
    "¡Judito! Qué es un mástero jifrán.",
    # dirección por «dónde está» suelto
    "Le Cape Records, donde está Gatig, en Probalesalán, la energía cambió, se dice.",
])
def test_pilot_false_positives_get_no_canned_answer(rules, text):
    r = ask(rules, text)
    assert r is None, f"respuesta enlatada inesperada: {r.detail} → {r.text!r}"


@pytest.mark.parametrize(("text", "detail"), [
    ("hola", "basic_qa"),
    ("Hola, buenos días", "basic_qa"),
    ("¿Quién eres?", "basic_qa"),
    ("¿Cómo te llamas?", "basic_qa"),
    ("¿Quién te creó?", "basic_qa"),
    ("¿Quién te diseñó?", "basic_qa"),
    ("¿Eres inteligente?", "basic_qa"),
    ("¿Eres una IA?", "basic_qa"),
    ("¿Qué día es hoy?", "basic_qa"),
    ("¿Qué puedes hacer?", "basic_qa"),
    ("UDITO, cuéntame un chiste", "fun_joke"),
    ("Dime un dato curioso", "fun_fact"),
    ("¿Qué sedes tiene UDIT en Madrid?", "knowledge_address"),
    ("¿Dónde está la universidad?", "knowledge_address"),
    ("¿Cuál es la dirección?", "knowledge_address"),
])
def test_genuine_short_questions_still_answered_locally(rules, text, detail):
    r = ask(rules, text)
    assert r is not None and r.detail == detail, f"{text!r} → {r and (r.detail, r.text)}"
    assert r.text


def test_basic_qa_backend_uses_the_same_strict_matching():
    b = BasicQaBackend()
    assert ask(b, "¿Qué es un marado oficial?") is None
    assert ask(b, "hola").source == "basic_qa"
