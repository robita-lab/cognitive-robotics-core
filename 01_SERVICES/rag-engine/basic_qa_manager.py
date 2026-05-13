#!/usr/bin/env python3
"""
Gestor de Respuestas Básicas para UDIT
Maneja respuestas predefinidas para preguntas comunes
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import re
from datetime import datetime

logger = logging.getLogger("BasicQAManager")

class BasicQAManager:
    def __init__(self, qa_file_path: str | None = None, qa_data: dict | None = None):
        _default = Path(__file__).resolve().parents[2] / "04_KNOWLEDGE_CORE" / "responses" / "qa.json"
        self.qa_file_path = qa_file_path or str(_default)
        if qa_data is not None:
            self.qa_data = qa_data
            logger.info("✅ Respuestas básicas cargadas desde knowledge core")
        else:
            self.qa_data = {}
            self._load_qa_data()
    
    def _load_qa_data(self):
        """Carga los datos de respuestas básicas desde el archivo JSON"""
        try:
            if Path(self.qa_file_path).exists():
                with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                    self.qa_data = json.load(f)
                logger.info(f"✅ Respuestas básicas cargadas: {len(self.qa_data.get('questions', []))} preguntas")
            else:
                logger.warning(f"Archivo de respuestas básicas no encontrado: {self.qa_file_path}")
                self.qa_data = {"questions": [], "identity_questions": [], "udit_specific": [], "greetings": []}
        except Exception as e:
            logger.error(f"Error al cargar respuestas básicas: {e}")
            self.qa_data = {"questions": [], "identity_questions": [], "udit_specific": [], "greetings": []}
    
    def find_basic_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Busca una respuesta básica para la consulta
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Dict con respuesta y metadatos, o None si no encuentra
        """
        query_lower = query.lower().strip()
        
        if self._is_academic_query(query_lower):
            return None
        
        # Buscar en saludos primero
        for greeting in self.qa_data.get("greetings", []):
            if self._matches_keywords(query_lower, greeting.get("keywords", [])):
                return {
                    "answer": greeting["answer"],
                    "type": greeting["type"],
                    "emotion": greeting["emotion"],
                    "source": "basic_qa"
                }
        
        # Buscar en preguntas de identidad
        for identity_q in self.qa_data.get("identity_questions", []):
            if self._matches_keywords(query_lower, identity_q.get("keywords", [])):
                return {
                    "answer": identity_q["answer"],
                    "type": identity_q["type"],
                    "emotion": identity_q["emotion"],
                    "source": "basic_qa"
                }
        
        # Buscar en preguntas específicas de UDIT (pero no horarios)
        for udit_q in self.qa_data.get("udit_specific", []):
            if self._matches_keywords(query_lower, udit_q.get("keywords", [])):
                return {
                    "answer": udit_q["answer"],
                    "type": udit_q["type"],
                    "emotion": udit_q["emotion"],
                    "source": "basic_qa"
                }
        
        # Buscar en preguntas generales
        for question in self.qa_data.get("questions", []):
            if self._matches_question(query_lower, question["question"]):
                return {
                    "answer": question["answer"],
                    "type": question["type"],
                    "emotion": question["emotion"],
                    "source": "basic_qa"
                }
        
        return None
    
    def _is_academic_query(self, query_lower: str) -> bool:
        """Evita Q&A fijo en consultas documentales; «udit» no coincide dentro de «pudito»."""
        word_boundary = {"udit", "rac", "tfg", "tfm"}
        academic_exclude = [
            "titulación", "titulacion", "vías", "vias", "normativa", "normativas",
            "matrícula", "matricula", "admisión", "admission", "acceso", "horario", "horarios",
            "política", "politica", "calidad", "medio ambiente", "condiciones", "extinción",
            "rac", "reglamento", "procedimiento", "requisitos", "trámite", "tramite",
            "graduación", "graduacion", "tfg", "tfm", "créditos", "creditos", "asignatura",
            "plazo", "inscripción", "secretaría", "secretaria", "biblioteca", "atención", "atencion",
            "universidad", "udit", "estudios", "grado", "máster", "master", "posgrado", "cuándo", "cuando",
        ]
        for word in academic_exclude:
            if word in word_boundary:
                if re.search(rf"\b{re.escape(word)}\b", query_lower):
                    return True
            elif word in query_lower:
                return True
        return False
    
    def _matches_keywords(self, query: str, keywords: List[str]) -> bool:
        """Verifica si la consulta coincide con palabras clave"""
        if not keywords:
            return False
        
        for keyword in keywords:
            if keyword.lower() in query:
                return True
        return False
    
    def _matches_question(self, query: str, question: str) -> bool:
        """Verifica si la consulta coincide con una pregunta"""
        # Extraer palabras clave de la pregunta
        question_words = re.findall(r'\b\w+\b', question.lower())
        query_words = re.findall(r'\b\w+\b', query.lower())
        
        # Calcular similitud simple
        matches = 0
        for word in question_words:
            if word in query_words and len(word) > 2:  # Ignorar palabras muy cortas
                matches += 1
        
        # Si al menos 2 palabras coinciden, considerar como match
        return matches >= 2
    
    def format_answer(self, answer_template: str, **kwargs) -> str:
        """Formatea una respuesta con variables dinámicas"""
        try:
            # Reemplazar variables comunes
            now = datetime.now()
            
            replacements = {
                "{hour}": str(now.hour),
                "{minutes}": str(now.minute).zfill(2),
                "{day}": str(now.day),
                "{month}": now.strftime("%B"),
                "{year}": str(now.year),
                **kwargs
            }
            
            formatted_answer = answer_template
            for key, value in replacements.items():
                formatted_answer = formatted_answer.replace(key, str(value))
            
            return formatted_answer
        except Exception as e:
            logger.error(f"Error al formatear respuesta: {e}")
            return answer_template
