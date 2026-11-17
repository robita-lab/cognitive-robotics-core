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
        """Devuelve las frases que ya están completas; el resto queda en el búfer tal cual.

        Se corta sobre el texto en bruto (sin normalizar espacios) para no
        pegar palabras: "Estoy " + "en" debe seguir siendo "Estoy en".
        """
        self._buf += chunk
        cut = None
        for m in _SPLIT.finditer(self._buf):
            before = self._buf[:m.start()].rstrip("\"»)]")
            if not any(before.endswith(f"{a}.") for a in _ABBREV):
                cut = m
        if cut is None:
            return []
        head, self._buf = self._buf[:cut.start()], self._buf[cut.end():]
        return split_sentences(head)

    def flush(self) -> list[str]:
        rest = split_sentences(self._buf)
        self._buf = ""
        return rest
