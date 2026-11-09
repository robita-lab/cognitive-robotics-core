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
    "Hablas en voz alta con visitantes y estudiantes: responde en español, en una a tres frases cortas, "
    "con tono cálido y natural. Nada de listas, viñetas, markdown, emojis ni enlaces largos."
)

TURN_GROUNDED = (
    "Responde a la pregunta usando SOLO la información de los fragmentos de normativa de UDIT que hay abajo. "
    "Si los fragmentos no contienen la respuesta, di que no tienes ese dato y sugiere preguntar en Secretaría. "
    "No inventes cifras, plazos ni requisitos. Si mencionas de dónde sale, usa el nombre del documento "
    "tal como aparece entre paréntesis en el fragmento que uses.\n\nFragmentos:\n"
)

TURN_OPEN = (
    "Si te preguntan datos concretos de UDIT que no conoces (precios, profesores, servicios, fechas), "
    "di con naturalidad que no tienes ese dato y sugiere la web udit punto es o Secretaría; no los inventes. "
    "Para la conversación general, responde con naturalidad."
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
