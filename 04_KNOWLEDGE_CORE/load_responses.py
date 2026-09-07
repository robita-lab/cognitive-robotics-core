"""Carga textos hablados de UDITO desde 04_KNOWLEDGE_CORE/responses/."""

from __future__ import annotations

import json
import os
import random
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

_CORE = Path(os.getenv("ROBITA_KNOWLEDGE_CORE", str(Path(__file__).resolve().parent)))
_agent: dict[str, Any] | None = None
_conversation: dict[str, Any] | None = None
_qa: dict[str, Any] | None = None
_pre_search: dict[str, Any] | None = None
_fun_notes: dict[str, Any] | None = None
_face_commands: list[dict[str, Any]] | None = None


def knowledge_core() -> Path:
    return _CORE


def responses_dir() -> Path:
    return _CORE / "responses"


def knowledge_text_dir() -> Path:
    return _CORE / "knowledge-text"


def read_knowledge_file(name: str) -> str:
    path = knowledge_text_dir() / name
    if not path.is_file():
        return ""
    raw = path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("#")]
    return "\n".join(lines).strip()


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_agent(force: bool = False) -> dict[str, Any]:
    global _agent
    if _agent is None or force:
        _agent = _read_json(responses_dir() / "agent.json")
    return _agent


def load_conversation(force: bool = False) -> dict[str, Any]:
    global _conversation
    if _conversation is None or force:
        _conversation = _read_json(responses_dir() / "conversation.json")
    return _conversation


def load_qa_file(force: bool = False) -> dict[str, Any]:
    global _qa
    if _qa is None or force:
        _qa = _read_json(responses_dir() / "qa.json")
    return _qa


def load_pre_search_phrases(force: bool = False) -> dict[str, Any]:
    global _pre_search
    if _pre_search is None or force:
        _pre_search = _read_json(responses_dir() / "pre_search_phrases.json")
    return _pre_search


def load_fun_notes(force: bool = False) -> dict[str, Any]:
    global _fun_notes
    if _fun_notes is None or force:
        _fun_notes = _read_json(responses_dir() / "fun_notes.json")
    return _fun_notes


def random_pre_search_phrase() -> tuple[str, str]:
    """Frase mientras se consulta RAG; devuelve (texto, emoción)."""
    data = load_pre_search_phrases()
    phrases = data.get("phrases") or []
    emotion = str(data.get("emotion", "thinking"))
    if not phrases:
        return ("Déjame mirar mis registros...", emotion)
    return random.choice(phrases), emotion


FunRequestKind = Literal["curious_fact", "joke"]

# Eco típico del saludo TTS en la transcripción Whisper
_STT_BLEED_EXTRA = (
    "en que te puedo ayudar",
    "en que puedo ayudarte",
    "que te puedo ayudar",
    "hola en que",
    "udito",
)


def stt_bleed_phrases() -> list[str]:
    phrases = list(_STT_BLEED_EXTRA)
    g = load_agent().get("greeting", "").strip()
    if g:
        phrases.append(g)
    return phrases


def _is_stt_bleed_segment(segment: str) -> bool:
    n = _norm(segment)
    if not n or len(n) < 4:
        return True
    for phrase in stt_bleed_phrases():
        p = _norm(phrase)
        if not p:
            continue
        if n == p or p in n or n in p:
            return True
    return False


def collapse_stt_repetitions(text: str) -> str:
    """Quita repeticiones típicas de Whisper tiny en silencio/ruido."""
    if not text:
        return text
    # «es el honor, es el honor, es el honor» → una sola vez
    t = re.sub(
        r"(.{3,40}?)(?:\s*[,.]?\s*\1){2,}",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", t).strip()


def repair_stt_garbled(text: str) -> str:
    """Corrige errores típicos de Whisper tiny en español."""
    if not text or not text.strip():
        return text
    t = text
    subs = (
        (r"\blongu[eé]rcia\b", "universidad"),
        (r"\blonguercia\b", "universidad"),
        (r"\blongueria\b", "universidad"),
        (r"\blonguecia\b", "universidad"),
        (r"\blongue\s*rcia\b", "universidad"),
        (r"\buniversida\b", "universidad"),
        (r"\budito\b", "udit"),
        (r"\buito\b", "udit"),
    )
    for pat, repl in subs:
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    return t.strip()


def transcript_seems_unusable(text: str, audio_sec: float) -> bool:
    """True si conviene pedir que repita (audio corto o texto sin sentido)."""
    t = _norm(text)
    if not t or len(t) < 6:
        return True
    if audio_sec < 0.75 and len(t) < 20:
        return True
    # Solo ruido / eco del saludo
    if t in ("dime", "udito", "hola", "si", "sí"):
        return True
    return False


def sanitize_user_transcript(text: str) -> str:
    """Quita el saludo del robot y ruido STT; deja solo lo que dijo el usuario."""
    if not text or not text.strip():
        return ""
    out = repair_stt_garbled(text.strip())
    parts = [p.strip() for p in re.split(r"[.!?]+\s*", out) if p.strip()]
    if len(parts) >= 2 and _is_stt_bleed_segment(parts[0]):
        out = parts[-1]
    elif len(parts) == 1 and _is_stt_bleed_segment(parts[0]):
        return ""
    for phrase in stt_bleed_phrases():
        if not phrase:
            continue
        out = re.sub(re.escape(phrase), " ", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip(" \t\n\r,;:.!?")
    return collapse_stt_repetitions(out)


def _stt_sounds_like_joke(t: str) -> bool:
    """Whisper tiny confunde «cuéntame un chiste» con frases como «cuanto me entiste»."""
    if "chist" in t or "gracios" in t or "broma" in t:
        return True
    if re.search(r"cuant|cuent", t) and re.search(
        r"chist|gracios|broma|reir|rir|entiste|entend", t
    ):
        return True
    if "cuanto me entiste" in t or "cuentame un chiste" in t.replace(" ", ""):
        return True
    if "cuentame" in t and len(t) < 40:
        return True
    return False


def match_fun_request(text: str) -> FunRequestKind | None:
    """Detecta petición de dato curioso o chiste (no usa RAG). Tolera errores STT."""
    t = _norm(text)
    if not t:
        return None
    data = load_fun_notes()
    kw = data.get("request_keywords") or {}
    for phrase in kw.get("joke") or []:
        if _norm(phrase) in t:
            return "joke"
    for phrase in kw.get("curious_fact") or []:
        if _norm(phrase) in t:
            return "curious_fact"
    if _stt_sounds_like_joke(t):
        return "joke"
    # Palabras sueltas (Whisper: «melato curioso», «un chiste», etc.)
    joke_tokens = (
        "chiste", "chistes", "gracioso", "graciosa", "broma", "bromas",
        "hazme reir", "reirme", "rir",
    )
    if any(tok in t for tok in joke_tokens):
        return "joke"
    fact_tokens = ("curios", "curiosa", "curioso", "sabias que", "sorprend")
    fact_hints = ("dato", "dame", "dim", "cuenta", "cuentame", "algo", "un ", "una ")
    if any(tok in t for tok in fact_tokens):
        if any(h in t for h in fact_hints) or "melato" in t:
            return "curious_fact"
    return None


def random_fun_fact() -> str:
    data = load_fun_notes()
    facts = data.get("curious_facts") or []
    if not facts:
        return "¿Sabías que los pulpos tienen tres corazones?"
    item = random.choice(facts)
    intro_key = str(item.get("intro", "sabias_que"))
    body = str(item.get("body", "")).strip()
    templates = data.get("intro_templates") or {}
    tpl = templates.get(intro_key) or templates.get("sabias_que") or "¿Sabías que {body}?"
    if "{body}" in tpl:
        return tpl.format(body=body)
    return f"{tpl} {body}".strip()


def random_joke() -> str:
    data = load_fun_notes()
    jokes = data.get("jokes") or []
    if not jokes:
        return "¿Qué hace un pez cuando está aburrido? Nada."
    item = random.choice(jokes)
    return str(item.get("text", item)).strip()


def random_laugh_line() -> str:
    data = load_fun_notes()
    lines = data.get("laugh_lines") or ["Ja, ja, ja."]
    return random.choice(lines)


def should_pre_search_before_rag(text: str) -> bool:
    """True si conviene decir frase de espera antes de process_query (RAG lento)."""
    if match_fun_request(text):
        return False
    t = _norm(text)
    quick = (
        "hola", "buenos dias", "buenas tardes", "buenas noches", "que tal",
        "como estas", "quien eres", "como te llamas", "gracias", "adios",
    )
    if any(t == q or t.startswith(q + " ") for q in quick):
        return False
    return True


def message(key: str, default: str = "") -> str:
    if key == "greeting":
        return load_agent().get("greeting", default)
    return load_conversation().get(key, default)


def goodbye_keywords() -> list[str]:
    return list(load_conversation().get("goodbye_keywords", []))


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def is_goodbye(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    for kw in goodbye_keywords():
        if _norm(kw) in t:
            return True
    return False


def qa_data() -> dict[str, Any]:
    data = load_qa_file()
    return {
        "questions": data.get("questions", []),
        "identity_questions": data.get("identity_questions", []),
        "udit_specific": data.get("udit_specific", []),
        "greetings": data.get("greetings", []),
    }


def spoken_udit_address() -> str:
    """Dirección y sedes — solo texto curado (sin Barcelona ni URLs leídas letra a letra)."""
    custom = read_knowledge_file("udit_sedes_contacto.txt")
    if custom:
        return (
            "UDIT está en Madrid. El campus de diseño está en la Avenida de Alfonso Trece, "
            "número noventa y siete. El campus de tecnología, en la calle Alcalá, quinientos seis. "
            "También hay formación en línea. Más datos en la web udit punto es."
        )
    return (
        load_qa_file().get("fixed_answers", {}).get("udit_address")
        or "UDIT está en Madrid; consulta udit punto es."
    )


def match_knowledge_text(query: str) -> tuple[str, str] | None:
    """
    Respuestas rápidas desde knowledge-text/ (no RAG PDF).
    Devuelve (texto, source) o None.
    """
    t = _norm(query)
    if not t:
        return None

    addr_kw = (
        "direccion", "dirección", "sede", "sedes", "donde esta", "donde queda",
        "ubicacion", "ubicación", "campus", "calle", "avenida", "domicilio",
    )
    uni_kw = ("universidad", "udit", "facultad", "centro", "longuer")
    if any(k in t for k in addr_kw):
        if any(k in t for k in uni_kw) or any(
            q in t for q in ("cual", "donde", "que es", "dime")
        ):
            return spoken_udit_address(), "knowledge_address"

    hor_kw = (
        "horario", "horarios", "hora", "abre", "cierra", "atencion", "atención",
        "biblioteca", "secretaria", "secretaría", "administrativ",
    )
    if any(k in t for k in hor_kw):
        if read_knowledge_file("udit_horarios.txt"):
            return "", "knowledge_horarios"

    id_kw = ("quien eres", "quién eres", "que eres", "qué eres", "udito", "como te llamas")
    if any(k in t for k in id_kw):
        body = read_knowledge_file("udito_identidad.txt")
        if body:
            line = body.split("\n")[0].lstrip("- ").strip()
            return line or "Soy UDITO, asistente de voz de la universidad UDIT.", "knowledge_udito"
    return None


def fixed_answer(key: str) -> str | None:
    if key == "udit_address":
        return spoken_udit_address()
    return load_qa_file().get("fixed_answers", {}).get(key)


def shorten_for_voice(text: str, max_sentences: int = 2, max_chars: int = 220) -> str:
    import re

    if not text or not text.strip():
        return text
    text = text.strip()
    if len(text) <= max_chars:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    total = 0
    for p in parts:
        if len(out) >= max_sentences or total + len(p) > max_chars:
            break
        out.append(p)
        total += len(p)
    result = " ".join(out).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(maxsplit=1)[0]
        if result and result[-1] not in ".!?":
            result += "."
    return result or text[:max_chars]


def load_face_commands(force: bool = False) -> list[dict[str, Any]]:
    global _face_commands
    if _face_commands is None or force:
        data = _read_json(responses_dir() / "face_commands.json")
        _face_commands = list(data.get("expressions") or [])
    return _face_commands


FACE_DEMO_KEYWORDS = (
    "muestrame expresiones",
    "muestra expresiones",
    "muestra las expresiones",
    "muestrame las expresiones",
    "haz un ciclo de expresiones",
    "ciclo de expresiones",
    "demo de expresiones",
    "ensename expresiones",
    "enseñame expresiones",
    "ensename las expresiones",
    "enseñame las expresiones",
)

FACE_DEMO_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("happy", "Sonrío."),
    ("wink", "Guiño un ojo."),
    ("surprised", "¡Sorpresa!"),
    ("laugh", "Jaja."),
    ("tongue", "Lengua fuera."),
    ("idle", "Listo."),
)


def match_face_demo_cycle(text: str) -> list[tuple[str, str]] | None:
    """Comando «muéstrame expresiones» → secuencia sincronizada en pantalla."""
    t = _norm(text)
    if not t:
        return None
    for phrase in FACE_DEMO_KEYWORDS:
        if _norm(phrase) in t:
            return list(FACE_DEMO_SEQUENCE)
    return None


def match_face_command(text: str) -> tuple[str, str] | None:
    """Comando directo a la pantalla (sin RAG). Coincidencia exacta por keywords."""
    t = _norm(text)
    if not t:
        return None
    best: tuple[str, str] | None = None
    best_len = 0
    for expr in load_face_commands():
        eid = str(expr.get("id", "")).strip()
        if not eid:
            continue
        reply = str(expr.get("reply", "De acuerdo.")).strip()
        for phrase in expr.get("keywords") or []:
            p = _norm(str(phrase))
            if p and p in t and len(p) > best_len:
                best_len = len(p)
                best = (eid, reply)
    return best
