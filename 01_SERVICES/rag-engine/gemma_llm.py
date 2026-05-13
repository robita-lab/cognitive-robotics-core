#!/usr/bin/env python3
"""
Gemma 2B LLM Integration para UDIT
Proporciona capacidades de generación de lenguaje natural
"""

import os
import logging
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Optional
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GemmaLLM")

class GemmaLLM:
    def __init__(self, model_name: str = "google/gemma-2b-it"):
        """Inicializa el LLM Gemma 2B"""
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        self.is_initialized = False
        
        # Cargar token de Hugging Face
        self.hf_token = self._load_hf_token()
        
        logger.info(f"Inicializando Gemma LLM: {model_name} en {self.device}")
        self._load_model()
    
    def _load_hf_token(self) -> Optional[str]:
        """Carga el token de Hugging Face desde archivo"""
        try:
            token_file = Path("config/huggingface_token.txt")
            if token_file.exists():
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                logger.info("✅ Token de Hugging Face cargado desde archivo")
                return token
            else:
                logger.warning("⚠️ Archivo de token no encontrado, usando variable de entorno")
                return os.environ.get('HUGGING_FACE_HUB_TOKEN')
        except Exception as e:
            logger.error(f"Error al cargar token: {e}")
            return os.environ.get('HUGGING_FACE_HUB_TOKEN')
    
    def _load_model(self):
        """Carga el modelo y tokenizer de Gemma"""
        try:
            logger.info("Cargando tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                padding_side="left",
                token=self.hf_token
            )
            
            # Configurar padding token si no existe
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Cargando modelo...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                token=self.hf_token
            )
            
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            
            self.is_initialized = True
            logger.info("Modelo Gemma 2B cargado exitosamente")
            
        except Exception as e:
            logger.error(f"Error al cargar modelo Gemma: {e}")
            raise
    
    def generate_response(self, query: str, context: str, max_length: int = 120) -> str:
        """Genera una respuesta usando Gemma 2B optimizado para velocidad"""
        try:
            if not self.is_initialized:
                raise ValueError("Modelo no inicializado")
            
            # OPTIMIZACIÓN: Cache de respuestas frecuentes
            cache_key = f"{query[:50]}_{hash(context[:100])}"
            if hasattr(self, 'response_cache') and cache_key in self.response_cache:
                logger.info("✅ Respuesta obtenida desde cache")
                return self.response_cache[cache_key]
            
            # Construir prompt optimizado para velocidad
            prompt = self._build_optimized_prompt(query, context)
            
            # Tokenizar entrada optimizada
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024,  # Reducido para velocidad
                padding=True
            )
            
            if self.device == "cpu":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # OPTIMIZACIÓN: Parámetros de generación para velocidad
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_length,  # Reducido para velocidad
                    temperature=0.6,  # Más determinístico
                    do_sample=True,
                    top_p=0.8,  # Reducido para velocidad
                    repetition_penalty=1.05,  # Reducido
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    num_beams=1,  # Sin beam search para velocidad
                    early_stopping=True  # Parar cuando sea necesario
                )
            
            # Decodificar SOLO los tokens nuevos para evitar truncados/corrupción
            try:
                input_len = inputs["input_ids"].shape[1]
                generated_ids = outputs[0][input_len:]
                response = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
            except Exception:
                # Fallback seguro
                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            
            # OPTIMIZACIÓN: Cachear respuesta
            if not hasattr(self, 'response_cache'):
                self.response_cache = {}
            self.response_cache[cache_key] = response
            
            logger.info(f"⚡ Respuesta generada rápidamente: {len(response)} caracteres")
            return response
            
        except Exception as e:
            logger.error(f"Error al generar respuesta optimizada: {e}")
            return "Lo siento, tuve un problema al generar la respuesta."
    
    def _build_optimized_prompt(self, query: str, context: str) -> str:
        """Prompt humanizado: asistente real, respuesta corta y resumida para voz."""
        safe_context = context[:1200]
        prompt = (
            f"<start_of_turn>user\n"
            f"Eres UDI, un asistente humano de la universidad. Hablas por voz: responde siempre en UNA o DOS frases cortas, "
            f"como si hablaras con alguien en persona. Conoces la información de abajo; respóndela con naturalidad, sin leer ni repetir textos largos. "
            f"Si hay mucha información, resúmela en una frase clara. No digas 'según los documentos' ni hagas listas o párrafos. "
            f"Responde en el mismo idioma de la pregunta. Si no sabes la respuesta, di solo: No lo tengo.\n\n"
            f"Información que conoces:\n{safe_context}\n\n"
            f"Pregunta: {query}\n\n"
            f"Respuesta:\n<end_of_turn>\n<start_of_turn>model\n"
        )
        return prompt
    
    def get_model_info(self) -> dict:
        """Obtiene información del modelo"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "is_initialized": self.is_initialized,
            "parameters": sum(p.numel() for p in self.model.parameters()) if self.model else 0,
            "model_type": "Gemma 2B Instruction Tuned"
        }

def create_gemma_llm(model_name: str = "google/gemma-2b-it", device: str = None) -> GemmaLLM:
    """Función de conveniencia para crear una instancia de GemmaLLM"""
    return GemmaLLM(model_name, device)

if __name__ == "__main__":
    # Prueba del módulo
    print("🧪 Probando módulo Gemma LLM...")
    
    try:
        llm = GemmaLLM()
        info = llm.get_model_info()
        print(f"✅ Modelo cargado: {info}")
        
        # Prueba de generación
        test_query = "¿Cuáles son los horarios de la universidad?"
        test_context = "La universidad UDIT abre de lunes a viernes de 8:00 a 18:00 horas. La secretaría atiende en el mismo horario."
        
        response = llm.generate_response(test_query, test_context)
        print(f"📝 Respuesta de prueba: {response}")
        
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
