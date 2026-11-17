"""Guarda de ámbito: no dejar que el LLM invente datos de UDIT.

Va al final de la cadena local. Si nadie local ha sabido contestar (las
reglas no aplican y la normativa se ha abstenido) y la pregunta es claramente
sobre la universidad, el robot dice que no tiene ese dato en vez de pasar la
pregunta al LLM sin contexto: un modelo pequeño se inventa cafeterías,
precios o profesores aunque se le pida que no lo haga (visto con qwen2.5 3B).

Las preguntas generales ("¿qué es un agujero negro?") siguen yendo al LLM.
Coste: alguna pregunta general que mencione estas palabras ("¿qué es un
máster?") recibe "no tengo ese dato". Se desactiva con scope_guard=False.
"""

from __future__ import annotations

import re
import unicodedata

from ..types import BackendAnswer, CancelToken, PartialCallback, ThinkRequest, Turn

UDIT_TERMS = (
    "udit", "universidad", "uni", "campus", "facultad", "secretaria", "matricula", "matriculas", "asignatura",
    "asignaturas", "profesor", "profesora", "profesores", "grado", "grados", "master", "masters", "carrera",
    "beca", "becas", "cafeteria", "comedor", "residencia", "alumnos", "alumnas", "estudiantes", "examen",
    "examenes", "convocatoria", "convocatorias", "creditos", "ects", "tfg", "tfm", "titulacion", "titulo",
    "aula", "aulas", "biblioteca", "rector", "decano", "coordinador", "tutor", "practicas", "erasmus",
)

ANSWER = ("No tengo ese dato. Te recomiendo preguntarlo en Secretaría o mirarlo en la web, udit punto es.")


def _fold(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def mentions_udit(text: str) -> bool:
    words = set(re.findall(r"[a-zñ]+", _fold(text)))
    return any(t in words for t in UDIT_TERMS)


class ScopeGuardBackend:
    name = "scope_guard"
    ready = True

    def warmup(self) -> None:
        pass

    def answer(self, req: ThinkRequest, history: list[Turn], cancel: CancelToken,
               on_partial: PartialCallback | None = None) -> BackendAnswer | None:
        if mentions_udit(req.text):
            return BackendAnswer(ANSWER, "sorry", "fallback", detail="scope_guard")
        return None
