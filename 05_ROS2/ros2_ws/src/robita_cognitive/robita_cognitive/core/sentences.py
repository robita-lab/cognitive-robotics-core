"""Troceo en frases para el feedback de Think (el TTS empieza con la primera)."""

from __future__ import annotations

import re

# Corta tras . ! ? … (y su cierre opcional de comillas/paréntesis) seguido de espacio.
# No corta en abreviaturas frecuentes ni en números decimales ("3.5").
_ABBREV = ("Sr", "Sra", "Dr", "Dra", "etc", "p. ej", "pág", "núm", "aprox", "Avda", "Av", "C")
_SPLIT = re.compile(r"(?<=[.!?…])[\"»)\]]?\s+(?=[\"«¿¡(\[A-ZÁÉÍÓÚÑ0-9])")


def split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    parts: list[str] = []
    buf = ""
    for piece in _SPLIT.split(text):
        buf = f"{buf} {piece}".strip() if buf else piece.strip()
        if any(buf.endswith(f"{a}.") for a in _ABBREV):
            continue
        parts.append(buf)
        buf = ""
    if buf:
        parts.append(buf)
    return parts


class SentenceAccumulator:
    """Acumula tokens de un stream y devuelve frases completas (para P2)."""

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, chunk: str) -> list[str]:
        self._buf += chunk
        sentences = split_sentences(self._buf)
        if len(sentences) <= 1:
            return []
        self._buf = sentences[-1]
        return sentences[:-1]

    def flush(self) -> list[str]:
        rest = split_sentences(self._buf)
        self._buf = ""
        return rest
