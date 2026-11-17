"""Limpieza de lo que el LLM va a decir en voz alta, frase a frase.

- Quita marcas internas de los fragmentos: "[1]", "[1] y [3]", "(2)",
  "según el fragmento 2", "el documento [2]".
- Quita markdown que el TTS leería: *cursiva*, **negrita**, `código`, "# ",
  guiones de lista y direcciones web.
- Quita emojis (qwen3 los mete a veces pese al prompt). Solo símbolos desde
  U+2600, para no perder "°", "©" ni "€".
- Corta si aparece escritura no latina (chino, cirílico, árabe...): visto con
  qwen2.5 7B, que a mitad de respuesta saltó a "转让协议" y siguió en inglés.
  El llamador cierra el stream y se queda con lo dicho hasta ahí.
"""

from __future__ import annotations

import re
import unicodedata

_NUM = r"\[?\d+\]?"
_NUMS = rf"{_NUM}(?:\s*(?:,|y|e)\s*{_NUM})*"
_MARKERS = [
    # "Según el fragmento [1] y [3], ..." / "Según [2], ..." al principio de la frase
    re.compile(rf"^\s*(?:según|como (?:indica|dice))\s+(?:(?:el|los)\s+(?:fragmento|documento)s?\s+)?{_NUMS}\s*,?\s*",
               re.IGNORECASE),
    # "..., según el fragmento 2 y 3." en medio o al final
    re.compile(rf",?\s*(?:según|como (?:indica|dice))\s+(?:el|los)\s+(?:fragmento|documento)s?\s+{_NUMS}",
               re.IGNORECASE),
    re.compile(r"\s*\[\d+\]"),     # [1] suelto
    re.compile(r"\s*\(\d+\)"),     # (2)
    re.compile(r"(?:https?://|www\.)\S+|\b[\w.-]+\.(?:es|com|org)/\S*"),  # URLs
]
_MARKDOWN = re.compile(r"[*_`#]+")
_LIST_DASH = re.compile(r"(?:^|(?<=[:.]))\s*[-•]\s+")


def _is_foreign_letter(ch: str) -> bool:
    if not unicodedata.category(ch).startswith("L"):
        return False
    try:
        return not unicodedata.name(ch).startswith("LATIN")
    except ValueError:
        return True


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return cp in (0x200D, 0xFE0F) or (cp >= 0x2600 and unicodedata.category(ch) in ("So", "Sk"))


def clean_sentence(sentence: str) -> tuple[str, bool]:
    """(frase limpia, cortada_por_otro_alfabeto)."""
    cut = False
    for i, ch in enumerate(sentence):
        if _is_foreign_letter(ch):
            sentence, cut = sentence[:i], True
            break
    for pat in _MARKERS:
        sentence = pat.sub("", sentence)
    sentence = "".join(ch for ch in sentence if not _is_emoji(ch))
    sentence = _MARKDOWN.sub("", sentence)
    sentence = _LIST_DASH.sub(" ", sentence)
    sentence = re.sub(r"\s+([,.;:!?])", r"\1", " ".join(sentence.split()))
    sentence = re.sub(r"^[,;:\s]+", "", sentence)
    if sentence[:1].islower():
        sentence = sentence[0].upper() + sentence[1:]
    if cut:
        # lo que quede antes del salto suele ser media palabra o media frase
        sentence = sentence.rsplit(" ", 1)[0] if " " in sentence else ""
        sentence = sentence.rstrip(",;: ")
        if sentence and sentence[-1] not in ".!?…":
            sentence += "."
        if len(sentence.split()) < 3:
            sentence = ""
    return sentence, cut
