"""Respaldo conversacional vía llm-engine (01_SERVICES/llm-engine) — opcional.

Solo se activa si ROBITA_LLM_URL está definida. Sin ella, UDITO se comporta
exactamente igual que en modo offline puro (RAG + reglas).

  ROBITA_LLM_URL              p. ej. http://localhost:8080 (Jetson) o http://<pc-gpu>:8080
  ROBITA_LLM_TIMEOUT          segundos de espera máxima (defecto 6)
  ROBITA_LLM_MAX_TOKENS       tope de tokens por respuesta (defecto 80)
  ROBITA_LLM_FALLBACK_SOURCES fuentes del RAG que se delegan al LLM (defecto "gpt")
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid

log = logging.getLogger("udito.llm_fallback")


class LLMFallback:
  def __init__(self) -> None:
    self.url = os.getenv("ROBITA_LLM_URL", "").strip().rstrip("/")
    self.timeout = float(os.getenv("ROBITA_LLM_TIMEOUT", "6"))
    self.max_tokens = int(os.getenv("ROBITA_LLM_MAX_TOKENS", "80"))
    raw = os.getenv("ROBITA_LLM_FALLBACK_SOURCES", "gpt")
    self.sources = {s.strip() for s in raw.split(",") if s.strip()}
    self.conversation_id = ""
    self.new_conversation()

  @property
  def enabled(self) -> bool:
    return bool(self.url)

  def new_conversation(self) -> None:
    """Memoria por sesión de wakeword: cada «udito» empieza conversación limpia."""
    self.conversation_id = f"udito-{uuid.uuid4().hex[:12]}"

  def handles(self, source: str) -> bool:
    return self.enabled and source in self.sources

  def reply(self, user_text: str) -> str | None:
    """Respuesta del LLM, o None si falla (el llamador conserva la del RAG)."""
    body = json.dumps({
      "conversation_id": self.conversation_id,
      "user_text": user_text,
      "max_tokens": self.max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
      f"{self.url}/v1/chat",
      data=body,
      headers={"Content-Type": "application/json"},
      method="POST",
    )
    try:
      with urllib.request.urlopen(req, timeout=self.timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
      log.warning("llm-engine no disponible (%s): %s", self.url, exc)
      return None
    text = (data.get("reply") or "").strip()
    return text or None
