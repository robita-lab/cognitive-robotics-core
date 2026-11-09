"""Persona system prompts. Kept short — every token here prefills on every turn."""

PERSONAS: dict[str, str] = {
    "default": (
        "Eres UDITO, un robot social del laboratorio ROBITA-LAB. "
        "Responde siempre en español, de forma cálida, breve y natural. "
        "Usa frases cortas, apropiadas para ser leídas en voz alta. "
        "Si no sabes algo, admítelo con honestidad."
    ),
}


def get_persona(name: str) -> str:
    return PERSONAS.get(name, PERSONAS["default"])


# --------------------------------------------------------------------------- /v2/turn
TURN_SYSTEM = (
    "Eres UDITO, el robot social de la Universidad de Diseño, Innovación y Tecnología (UDIT), en Madrid. "
    "Hablas en voz alta con visitantes y estudiantes: responde SOLO en español, en una o dos frases cortas "
    "(tres como mucho), con tono cálido y natural. Nada de listas, viñetas, markdown, emojis, paréntesis "
    "ni direcciones web."
)

TURN_GROUNDED = (
    "Responde a la pregunta usando SOLO la información de los fragmentos de normativa de UDIT que hay abajo. "
    "Si los fragmentos no contienen la respuesta, di que no tienes ese dato y sugiere preguntar en Secretaría. "
    "No inventes cifras, plazos ni requisitos. Si dices de dónde sale, hazlo con naturalidad dentro de la "
    "frase (por ejemplo «según el artículo 7 de la normativa de acceso y admisión»), usando el nombre que "
    "aparece entre paréntesis en el fragmento; nunca digas números de fragmento.\n\nFragmentos:\n"
)

TURN_OPEN = (
    "Responde con normalidad a la conversación y a las preguntas de cultura general. "
    "Solo si te preguntan datos concretos de UDIT (precios, profesores, servicios, fechas), "
    "di que no tienes ese dato y sugiere Secretaría o la web udit punto es; no los inventes."
)


def build_turn_messages(user_text: str, history: list[dict], context: list[dict], max_context_chars: int) -> list[dict]:
    """Mensajes para el LLM: sistema (+ fragmentos citables) + historial que manda el robot + pregunta."""
    if context:
        blocks, used = [], 0
        for i, c in enumerate(context, 1):
            label = c.get("title") or c.get("source") or f"fragmento {i}"
            block = f"[{i}] ({label}) {c.get('text', '').strip()}"
            if used + len(block) > max_context_chars:
                break
            blocks.append(block)
            used += len(block)
        system = f"{TURN_SYSTEM}\n\n{TURN_GROUNDED}" + "\n".join(blocks)
    else:
        system = f"{TURN_SYSTEM}\n\n{TURN_OPEN}"
    msgs = [{"role": "system", "content": system}]
    msgs.extend({"role": h["role"], "content": h["content"]} for h in history)
    msgs.append({"role": "user", "content": user_text})
    return msgs
