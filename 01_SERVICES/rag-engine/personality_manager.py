#!/usr/bin/env python3
"""
Gestor de Personalidad para UDIT
Maneja respuestas básicas, personalidad y clasificación de preguntas
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import re
from datetime import datetime

logger = logging.getLogger("PersonalityManager")

class PersonalityManager:
    def __init__(self, personality_config_path: str = "config/udi_personality.json",
                 basic_qa_path: str | None = None):
        """Inicializa el gestor de personalidad de UDI"""
        self.personality_config_path = personality_config_path
        _default_qa = Path(__file__).resolve().parents[2] / "04_KNOWLEDGE_CORE" / "responses" / "qa.json"
        self.basic_qa_path = basic_qa_path or str(_default_qa)
        
        # Cargar configuraciones
        self.personality_config = self._load_personality_config()
        self.basic_qa = self._load_basic_qa()
        
        # Compilar patrones de activación
        self.activation_patterns = self._compile_activation_patterns()
        
        logger.info("Gestor de personalidad UDI inicializado")
    
    def _load_personality_config(self) -> Dict[str, Any]:
        """Carga la configuración de personalidad"""
        try:
            with open(self.personality_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al cargar configuración de personalidad: {e}")
            return {}
    
    def _load_basic_qa(self) -> Dict[str, Any]:
        """Carga las respuestas básicas"""
        try:
            with open(self.basic_qa_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al cargar respuestas básicas: {e}")
            return {}
    
    def _compile_activation_patterns(self) -> List[re.Pattern]:
        """Compila patrones de activación"""
        patterns = []
        if 'activation_commands' in self.personality_config:
            commands = self.personality_config['activation_commands']
            
            # Patrones primarios
            for command in commands.get('primary', []):
                pattern = re.compile(rf'\b{re.escape(command)}\b', re.IGNORECASE)
                patterns.append(pattern)
            
            # Patrones secundarios
            for command in commands.get('secondary', []):
                pattern = re.compile(rf'\b{re.escape(command)}\b', re.IGNORECASE)
                patterns.append(pattern)
        
        return patterns
    
    def is_activation_command(self, text: str) -> bool:
        """Verifica si el texto es un comando de activación"""
        text_lower = text.lower().strip()
        
        for pattern in self.activation_patterns:
            if pattern.search(text_lower):
                return True
        
        return False
    
    def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Clasifica una consulta para determinar el tipo de respuesta
        
        Returns:
            Dict con clasificación y metadatos
        """
        query_lower = query.lower().strip()
        
        # 1. Verificar si es pregunta de identidad
        identity_match = self._match_identity_question(query_lower)
        if identity_match:
            return {
                "query_type": "identity",
                "confidence": 0.9,
                "response_type": "personality",
                "matched_question": identity_match,
                "query": query
            }
        
        # 2. Verificar si es saludo
        greeting_match = self._match_greeting(query_lower)
        if greeting_match:
            return {
                "query_type": "greeting",
                "confidence": 0.8,
                "response_type": "personality",
                "matched_question": greeting_match,
                "query": query
            }
        
        # 3. Verificar si es pregunta básica
        basic_match = self._match_basic_question(query_lower)
        if basic_match:
            return {
                "query_type": "basic",
                "confidence": 0.7,
                "response_type": "basic_qa",
                "matched_question": basic_match,
                "query": query
            }
        
        # 4. Verificar si es pregunta específica de UDIT
        udit_match = self._match_udit_question(query_lower)
        if udit_match:
            return {
                "query_type": "udit_specific",
                "confidence": 0.8,
                "response_type": "personality",
                "matched_question": udit_match,
                "query": query
            }
        
        # 5. Clasificación por palabras clave (sistema existente)
        return self._classify_by_keywords(query_lower, query)
    
    def _match_identity_question(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """Busca coincidencias con preguntas de identidad"""
        if 'identity_questions' not in self.basic_qa:
            return None
        
        for question_data in self.basic_qa['identity_questions']:
            question = question_data['question'].lower()
            keywords = question_data.get('keywords', [])
            
            # Verificar coincidencia exacta o por palabras clave
            if (query_lower in question or question in query_lower or
                any(keyword in query_lower for keyword in keywords)):
                return question_data
        
        return None
    
    def _match_greeting(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """Busca coincidencias con saludos"""
        if 'greetings' not in self.basic_qa:
            return None
        
        for greeting_data in self.basic_qa['greetings']:
            question = greeting_data['question'].lower()
            keywords = greeting_data.get('keywords', [])
            
            # Verificar coincidencia exacta o por palabras clave
            if (query_lower in question or question in query_lower or
                any(keyword in query_lower for keyword in keywords)):
                return greeting_data
        
        return None
    
    def _match_basic_question(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """Busca coincidencias con preguntas básicas"""
        if 'questions' not in self.basic_qa:
            return None
        
        for question_data in self.basic_qa['questions']:
            question = question_data['question'].lower()
            
            # Verificar coincidencia exacta
            if query_lower in question or question in query_lower:
                return question_data
        
        return None
    
    def _match_udit_question(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """Busca coincidencias con preguntas específicas de UDIT"""
        if 'udit_specific' not in self.basic_qa:
            return None
        
        for question_data in self.basic_qa['udit_specific']:
            question = question_data['question'].lower()
            keywords = question_data.get('keywords', [])
            
            # Verificar coincidencia exacta o por palabras clave
            if (query_lower in question or question in query_lower or
                any(keyword in query_lower for keyword in keywords)):
                return question_data
        
        return None
    
    def _classify_by_keywords(self, query_lower: str, original_query: str) -> Dict[str, Any]:
        """Clasificación por palabras clave (sistema existente mejorado)"""
        # Palabras clave que indican preguntas sobre la universidad
        university_keywords = [
            'universidad', 'udit', 'carrera', 'titulación', 'grado', 'máster',
            'doctorado', 'matrícula', 'inscripción', 'admisión', 'acceso',
            'normativa', 'reglamento', 'política', 'calidad', 'medio ambiente',
            'extinción', 'rac', 'condiciones', 'horarios', 'servicios',
            'sede', 'campus', 'facultad', 'departamento', 'profesor',
            'estudiante', 'alumno', 'examen', 'evaluación', 'nota',
            'crédito', 'asignatura', 'materia', 'curso', 'semestre',
            'académico', 'académica', 'docente', 'administrativo',
            'secretaría', 'decano', 'rector', 'vicerrector',
            'trabajo fin', 'tfg', 'tfm', 'tesis', 'proyecto',
            'prácticas', 'internship', 'erasmus', 'intercambio',
            'beca', 'ayuda', 'subvención', 'precio', 'coste',
            'pago', 'factura', 'recibo', 'certificado', 'diploma',
            'expediente', 'historial', 'calificaciones', 'notas',
            'convocatoria', 'examen', 'evaluación', 'calificación'
        ]
        
        # Palabras clave que indican preguntas generales
        general_keywords = [
            'clima', 'tiempo', 'fecha', 'hora', 'distancia', 'luna',
            'capital', 'país', 'ciudad', 'historia', 'ciencia',
            'matemáticas', 'cálculo', 'suma', 'resta', 'multiplicación',
            'división', 'juego', 'adivina', 'chiste', 'curiosidad',
            'deporte', 'música', 'película', 'libro', 'arte',
            'cocina', 'receta', 'viaje', 'turismo', 'hotel',
            'restaurante', 'comida', 'bebida', 'salud', 'medicina',
            'ejercicio', 'deporte', 'fútbol', 'baloncesto', 'tenis'
        ]
        
        # Contar coincidencias
        university_score = sum(1 for keyword in university_keywords if keyword in query_lower)
        general_score = sum(1 for keyword in general_keywords if keyword in query_lower)
        
        # Determinar tipo de consulta
        if university_score > 0:
            query_type = "university"
            confidence = min((university_score + 0.5) / 2.0, 1.0)
        elif general_score > 0:
            query_type = "general"
            confidence = min((general_score + 0.5) / 2.0, 1.0)
        else:
            # Clasificación por contexto
            if any(word in query_lower for word in ['qué', 'cuál', 'cómo', 'dónde', 'cuándo', 'por qué']):
                query_type = "university"
                confidence = 0.6
            else:
                query_type = "unknown"
                confidence = 0.3
        
        return {
            "query_type": query_type,
            "confidence": confidence,
            "university_score": university_score,
            "general_score": general_score,
            "response_type": "rag_or_gpt",
            "query": original_query
        }
    
    def get_response(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Genera la respuesta apropiada basada en la clasificación"""
        query_type = classification.get('query_type')
        response_type = classification.get('response_type')
        matched_question = classification.get('matched_question')
        
        if response_type == "personality" and matched_question:
            # Respuesta de personalidad
            return {
                "answer": matched_question['answer'],
                "emotion": matched_question.get('emotion', 'neutral'),
                "source": "personality",
                "confidence": classification.get('confidence', 0.8)
            }
        
        elif response_type == "basic_qa" and matched_question:
            # Respuesta básica
            answer = matched_question['answer']
            
            # Procesar variables dinámicas
            if '{hour}' in answer or '{minutes}' in answer:
                now = datetime.now()
                answer = answer.replace('{hour}', str(now.hour))
                answer = answer.replace('{minutes}', str(now.minute))
            
            if '{day}' in answer or '{month}' in answer or '{year}' in answer:
                now = datetime.now()
                answer = answer.replace('{day}', str(now.day))
                answer = answer.replace('{month}', str(now.month))
                answer = answer.replace('{year}', str(now.year))
            
            return {
                "answer": answer,
                "emotion": matched_question.get('emotion', 'neutral'),
                "source": "basic_qa",
                "confidence": classification.get('confidence', 0.7)
            }
        
        else:
            # Respuesta por defecto para clasificaciones RAG/GPT
            return {
                "answer": "Entiendo tu pregunta. Déjame procesarla con el sistema de información universitaria.",
                "emotion": "helpful",
                "source": "classification_only",
                "confidence": classification.get('confidence', 0.5)
            }
    
    def get_personality_info(self) -> Dict[str, Any]:
        """Obtiene información de la personalidad de UDI"""
        return self.personality_config.get('personality', {})
    
    def get_voice_characteristics(self) -> Dict[str, Any]:
        """Obtiene características de voz de UDI"""
        return self.personality_config.get('voice_characteristics', {})
    
    def get_activation_commands(self) -> List[str]:
        """Obtiene comandos de activación"""
        commands = self.personality_config.get('activation_commands', {})
        return commands.get('primary', []) + commands.get('secondary', []) 