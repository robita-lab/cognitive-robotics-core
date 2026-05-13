#!/usr/bin/env python3
"""
TinyLlama LLM para UDIT RAG.
Uso local, más ligero que Gemma. Compatible con la interfaz de GemmaLLM.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TinyLlamaLLM")

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


class TinyLlamaLLM:
    """LLM TinyLlama para respuestas RAG (interfaz compatible con GemmaLLM)."""

    def __init__(
        self,
        model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device: Optional[str] = None,
        local_path: Optional[str] = None,
    ):
        """
        model_name: nombre en HuggingFace o ruta local.
        device: "cuda" o "cpu". Si None, se elige automáticamente.
        local_path: si está definido, se usa como carpeta del modelo (local).
        """
        self.model_name = local_path or model_name
        self.device = device or ("cuda" if _HAS_TORCH and torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
        self.is_initialized = False
        logger.info("Inicializando TinyLlama: %s en %s", self.model_name, self.device)
        if _HAS_TORCH:
            self._load_model()
        else:
            logger.error("PyTorch/transformers no disponibles para TinyLlama")

    def _load_model(self):
        try:
            logger.info("Cargando tokenizer TinyLlama...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            logger.info("Cargando modelo TinyLlama...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            self.model = self.model.to(self.device)

            self.is_initialized = True
            logger.info("TinyLlama cargado correctamente")
        except Exception as e:
            logger.error("Error al cargar TinyLlama: %s", e)
            raise

    def generate_response(self, query: str, context: str, max_length: int = 120) -> str:
        """Genera respuesta dado el contexto RAG (misma firma que GemmaLLM)."""
        try:
            if not self.is_initialized:
                return "Lo siento, el modelo no está listo."
            import torch
            prompt = self._build_prompt(query, context)
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
                padding=True,
            )
            # Asegurar que inputs estén en el mismo dispositivo que el modelo (evita cuda/cpu mismatch)
            model_device = next(self.model.parameters()).device
            inputs = {k: v.to(model_device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_length,
                    temperature=0.6,
                    do_sample=True,
                    top_p=0.9,
                    repetition_penalty=1.1,
                    pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            input_len = inputs["input_ids"].shape[1]
            generated_ids = outputs[0][input_len:]
            response = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
            if response.lower().startswith("respuesta:"):
                response = response.split(":", 1)[1].strip()
            return response
        except Exception as e:
            logger.error("Error generando con TinyLlama: %s", e)
            return "Lo siento, no pude generar la respuesta."

    def _build_prompt(self, query: str, context: str) -> str:
        """Prompt humanizado: asistente real, respuesta corta y resumida para voz."""
        safe_ctx = context[:1500]
        return (
            "<|system|>\n"
            "Eres UDI, un asistente humano de la universidad. Hablas por voz: responde siempre en UNA o DOS frases cortas, "
            "como si hablaras con alguien en persona. Conoces la información de abajo; respóndela con naturalidad, sin leer ni repetir textos largos. "
            "Si hay mucha información, resúmela en una frase clara. No digas 'según los documentos' ni hagas listas o párrafos. "
            "Responde en el mismo idioma de la pregunta. Si no sabes la respuesta, di solo: No lo tengo.\n"
            "<|user|>\n"
            f"Información que conoces:\n{safe_ctx}\n\nPregunta: {query}\n"
            "<|assistant|>\n"
        )

    def get_model_info(self) -> dict:
        info = {
            "model_name": self.model_name,
            "device": self.device,
            "is_initialized": self.is_initialized,
        }
        if self.model is not None:
            info["parameters"] = sum(p.numel() for p in self.model.parameters())
        info["model_type"] = "TinyLlama"
        return info
