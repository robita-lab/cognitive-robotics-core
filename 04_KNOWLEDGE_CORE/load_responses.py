"""Carga textos hablados de UDITO desde 04_KNOWLEDGE_CORE/responses/."""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path
from typing import Any

_CORE = Path(os.getenv("ROBITA_KNOWLEDGE_CORE", str(Path(__file__).resolve().parent)))
_agent: dict[str, Any] | None = None
_conversation: dict[str, Any] | None = None
_qa: dict[str, Any] | None = None


def knowledge_core() -> Path:
    return _CORE


def responses_dir() -> Path:
    return _CORE / "responses"


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


def fixed_answer(key: str) -> str | None:
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
