"""
Convierte fragmentos de documentos en respuestas habladas naturales (sin leer la guía literal).
"""

from __future__ import annotations

import re
from typing import Optional


def _period(hour: int) -> str:
    if hour == 0 or hour == 24:
        return "medianoche"
    if hour == 12:
        return "mediodía"
    if hour < 12:
        return "mañana"
    return "tarde"


def _hour12(h: int) -> int:
    if h == 0:
        return 12
    if h > 12:
        return h - 12
    return h


def time_to_speech(token: str) -> str:
    """8:00 AM → las 8 de la mañana; 10:00 PM → las 10 de la noche."""
    token = token.strip().upper().replace(".", "")
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", token)
    if not m:
        return token.lower()
    h, mi, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").upper()
    if ampm == "AM":
        h24 = 0 if h == 12 else h
    elif ampm == "PM":
        h24 = 12 if h == 12 else h + 12
    else:
        h24 = h
    if mi == 0:
        if h24 in (0, 24):
            return "medianoche"
        if h24 == 12:
            return "mediodía"
        return f"las {_hour12(h24)} de la {_period(h24)}"
    return f"las {_hour12(h24)} y {mi} minutos de la {_period(h24)}"


def _parse_range(text: str) -> Optional[tuple[str, str]]:
    m = re.search(
        r"(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1), m.group(2)


def _weekdays_phrase(text: str) -> str:
    t = text.lower()
    if "lunes a viernes" in t or "lunes-viernes" in t:
        return "de lunes a viernes"
    if "sábados" in t or "sabados" in t:
        return "los sábados"
    if "domingos" in t:
        return "los domingos"
    if "lunes" in t and "viernes" in t:
        return "de lunes a viernes"
    return ""


def _service_from_line(line: str) -> tuple[str, str]:
    """Devuelve (servicio, resto del texto)."""
    if ":" in line:
        name, rest = line.split(":", 1)
        return name.strip().lower(), rest.strip()
    return "", line.strip()


def _line_to_phrase(line: str) -> Optional[str]:
    line = line.lstrip("-•* ").strip()
    if not line or line.upper().startswith("NOTAS"):
        return None
    service, rest = _service_from_line(line)
    days = _weekdays_phrase(rest)
    rng = _parse_range(rest)
    if not rng:
        if "cerrado" in rest.lower():
            return f"el {service} está cerrado" if service else "está cerrado"
        return None
    t1, t2 = rng
    desde_hasta = f"desde {time_to_speech(t1)}, hasta {time_to_speech(t2)}"
    if service:
        label = service.replace("horarios ", "").strip()
        if "biblioteca" in label:
            return f"la biblioteca abre {days} {desde_hasta}".strip()
        if "secretaría" in label or "secretaria" in label:
            return f"la secretaría atiende {days} {desde_hasta}".strip()
        if "administrativ" in label:
            return f"la atención administrativa es {days} {desde_hasta}".strip()
        if "tesorer" in label:
            return f"tesorería abre {days} {desde_hasta}".strip()
        if "admision" in label or "admisión" in label:
            return f"admisiones atiende {days} {desde_hasta}".strip()
        return f"{label} {days} {desde_hasta}".strip()
    return f"{days} {desde_hasta}".strip()


def answer_schedules(query: str, context: str) -> Optional[str]:
    q = query.lower()
    if not any(k in q for k in ("horario", "horarios", "hora", "abre", "cierra", "atiende")):
        return None

    phrases: list[str] = []
    for raw in context.split("\n"):
        line = raw.strip()
        if line.startswith("Documento ") and ":" in line:
            line = line.split(":", 1)[1].strip()
        p = _line_to_phrase(line)
        if p:
            phrases.append(p)

    if not phrases:
        return None

    target = None
    if "biblioteca" in q:
        target = next((p for p in phrases if "biblioteca" in p), None)
    elif "secretar" in q:
        target = next((p for p in phrases if "secretar" in p), None)
    elif "laboratorio" in q:
        target = next((p for p in phrases if "laboratorio" in p), None)
    elif "clase" in q or "clases" in q:
        target = next((p for p in phrases if "clases" in p), None)
    elif "administrativ" in q:
        target = next((p for p in phrases if "administrativ" in p), None)
    elif "matricula" in q or "matrícula" in q:
        target = next((p for p in phrases if "matrícula" in p or "matricula" in p), None)

    if target:
        return f"Claro, {target}."
    if len(phrases) == 1:
        return f"Claro, {phrases[0]}."
    intro = "Claro, te resumo los horarios que tengo:"
    body = ", ".join(phrases[:4])
    return f"{intro} {body}."

def answer_general(query: str, context: str) -> str:
    """Respuesta conversacional breve a partir de líneas del documento."""
    lines: list[str] = []
    for raw in context.split("\n"):
        line = raw.strip()
        if not line or line.upper().startswith("NOTAS"):
            continue
        if line.startswith("Documento ") and ":" in line:
            line = line.split(":", 1)[1].strip()
        if line.startswith("HORARIOS") and line.endswith(":"):
            continue
        lines.append(line)

    if not lines:
        return "No tengo ese dato en los documentos de la universidad."

    q = query.lower()
    picked: list[str] = []
    for line in lines:
        words = [w for w in re.findall(r"\b\w+\b", q) if len(w) > 3]
        if any(w in line.lower() for w in words):
            picked.append(line.lstrip("-•* "))

    body_lines = picked[:3] if picked else lines[:3]
    body = ". ".join(l.lstrip("-•* ") for l in body_lines)
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > 320:
        body = body[:320].rsplit(" ", 1)[0] + "."

    starters = ("Claro.", "Te cuento.", "Según la información de la universidad,")
    if any(k in q for k in ("donde", "dónde", "direccion", "dirección", "sede")):
        return f"Te cuento: {body}"
    return f"{starters[0]} {body}"


def conversational_from_context(query: str, context: str) -> str:
    sched = answer_schedules(query, context)
    if sched:
        return sched
    return answer_general(query, context)
