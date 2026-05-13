import json
import logging
from typing import Dict, Any, Optional
import datetime
import os
from pathlib import Path
import requests
from datetime import datetime

class BasicSkills:
    def __init__(self, config_path: str = "config/settings.json"):
        self.config = self._load_config(config_path)
        self.logger = logging.getLogger("BasicSkills")
        self.logger.setLevel(logging.getLevelName(self.config['system']['log_level']))
        self.load_basic_qa()
        
    def _load_config(self, config_path: str) -> dict:
        """Cargar configuración"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            raise
            
    def load_basic_qa(self):
        """Cargar preguntas y respuestas básicas"""
        try:
            qa_path = Path(__file__).resolve().parents[2] / "04_KNOWLEDGE_CORE" / "responses" / "qa.json"
            with open(qa_path, 'r', encoding='utf-8') as f:
                self.basic_qa = json.load(f)
            self.logger.info("Basic QA loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading basic QA: {e}")
            self.basic_qa = {"questions": []}
            
    def get_time(self) -> Dict[str, Any]:
        """Obtener la hora actual"""
        try:
            now = datetime.now()
            response = {
                "answer": f"Son las {now.hour}:{now.minute:02d} horas",
                "emotion": "neutral",
                "type": "time"
            }
            return response
        except Exception as e:
            self.logger.error(f"Error getting time: {e}")
            return {
                "answer": "Lo siento, no pude obtener la hora",
                "emotion": "neutral",
                "type": "error"
            }
            
    def get_date(self) -> Dict[str, Any]:
        """Obtener la fecha actual"""
        try:
            now = datetime.now()
            months = [
                "enero", "febrero", "marzo", "abril",
                "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"
            ]
            
            response = {
                "answer": f"Hoy es {now.day} de {months[now.month-1]} de {now.year}",
                "emotion": "neutral",
                "type": "date"
            }
            return response
        except Exception as e:
            self.logger.error(f"Error getting date: {e}")
            return {
                "answer": "Lo siento, no pude obtener la fecha",
                "emotion": "neutral",
                "type": "error"
            }
            
    def get_weather(self) -> Dict[str, Any]:
        """Obtener el clima"""
        try:
            # Aquí implementar la llamada a la API de clima
            # Por ahora devolvemos un clima falso
            response = {
                "answer": "El clima actual es soleado con una temperatura de 25 grados",
                "emotion": "neutral",
                "type": "weather"
            }
            return response
        except Exception as e:
            self.logger.error(f"Error getting weather: {e}")
            return {
                "answer": "Lo siento, no pude obtener el clima",
                "emotion": "neutral",
                "type": "error"
            }
            
    def do_math(self, operation: str) -> Dict[str, Any]:
        """Realizar operación matemática básica"""
        try:
            # Evaluamos la operación de manera segura
            try:
                result = eval(operation, {}, {})
                response = {
                    "answer": f"El resultado es {result}",
                    "emotion": "happy",
                    "type": "math"
                }
                return response
            except:
                return {
                    "answer": "Lo siento, no pude realizar la operación",
                    "emotion": "neutral",
                    "type": "error"
                }
        except Exception as e:
            self.logger.error(f"Error doing math: {e}")
            return {
                "answer": "Lo siento, hubo un error con la operación",
                "emotion": "neutral",
                "type": "error"
            }
            
    def match_basic_qa(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Buscar coincidencia en preguntas básicas
        
        Args:
            query: Pregunta del usuario
            
        Returns:
            Respuesta si hay coincidencia, None si no
        """
        try:
            for qa in self.basic_qa["questions"]:
                # Normalizar texto
                query_lower = query.lower()
                question_lower = qa["question"].lower()
                
                # Buscar coincidencias parciales
                if (query_lower in question_lower or 
                    question_lower in query_lower):
                    
                    # Reemplazar variables si es necesario
                    answer = qa["answer"]
                    if qa["type"] == "time":
                        now = datetime.now()
                        answer = answer.format(
                            hour=now.hour,
                            minutes=now.minute
                        )
                    elif qa["type"] == "date":
                        now = datetime.now()
                        months = [
                            "enero", "febrero", "marzo", "abril",
                            "mayo", "junio", "julio", "agosto",
                            "septiembre", "octubre", "noviembre", "diciembre"
                        ]
                        answer = answer.format(
                            day=now.day,
                            month=months[now.month-1],
                            year=now.year
                        )
                    
                    return {
                        "answer": answer,
                        "emotion": qa["emotion"],
                        "type": qa["type"]
                    }
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error matching basic QA: {e}")
            return None
