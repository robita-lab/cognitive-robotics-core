#!/usr/bin/env python3
"""
Sistema RAG Integrado para UDI
Combina procesamiento de documentos, vector store y clasificación de preguntas
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
import time
import sys

_KNOWLEDGE = Path(__file__).resolve().parents[2] / "04_KNOWLEDGE_CORE"
if str(_KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE))
from load_responses import qa_data as _qa_from_config, fixed_answer as _fixed_answer

from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_manager import RAGManager
from memory import MemoryManager
from gemma_llm import GemmaLLM
from basic_qa_manager import BasicQAManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RAGSystem")


class RAGSystem:
    def __init__(self, config_path: str = "config/rag_config.json", settings_path: str = None):
        """Inicializa el sistema RAG integrado.
        settings_path: opcional; si no se pasa, se usa config_path/../settings.json
        """
        self.config_path = config_path
        cfg = Path(config_path).resolve()
        _settings = settings_path
        if _settings is None or _settings == "":
            _settings = str(cfg.parent / "settings.json")
        else:
            _settings = str(Path(_settings).resolve())
        
        # Inicializar componentes
        self.document_processor = DocumentProcessor(config_path)
        self.vector_store = VectorStore(config_path)
        self.rag_manager = RAGManager(config_path)
        self.memory_manager = MemoryManager(_settings)
        
        # Inicializar LLM Gemma
        self.llm = None
        self._initialize_llm()
        
        # Inicializar gestor de respuestas básicas
        self.basic_qa_manager = BasicQAManager(qa_data=_qa_from_config())
        
        # Estado del sistema
        self.is_initialized = False
        self.last_update_check = 0
        
        logger.info("Sistema RAG inicializado")
    
    def _initialize_llm(self):
        """Inicializa el LLM según config: tinyllama o gemma"""
        try:
            config = {}
            if Path(self.config_path).exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            llm_cfg = config.get("llm", {})
            backend = (llm_cfg.get("backend") or "gemma").lower()
            if backend == "tinyllama":
                from tiny_llm import TinyLlamaLLM
                model_name = llm_cfg.get("tinyllama_model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
                local_path = llm_cfg.get("tinyllama_local_path")
                logger.info("Inicializando TinyLlama...")
                self.llm = TinyLlamaLLM(model_name=model_name, local_path=local_path)
                logger.info("✅ TinyLlama inicializado correctamente")
            else:
                logger.info("Inicializando LLM Gemma 2B...")
                self.llm = GemmaLLM()
                logger.info("✅ LLM Gemma 2B inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar LLM: {e}")
            self.llm = None
    
    def initialize(self, force_rebuild: bool = False):
        """
        Inicializa el sistema RAG
        
        Args:
            force_rebuild: Si True, reconstruye todo el sistema
        """
        try:
            logger.info("Inicializando sistema RAG...")
            
            if force_rebuild:
                logger.info("Forzando reconstrucción del sistema")
                self.document_processor.clear_cache()
                self.vector_store.clear()
            
            # Verificar si hay cambios en los documentos
            if self.rag_manager.check_for_updates() or force_rebuild:
                logger.info("Detectados cambios en documentos, procesando...")
                
                # Procesar todos los documentos
                all_chunks = self.document_processor.process_all_documents()
                
                # Agregar chunks al vector store
                for category, chunks in all_chunks.items():
                    if chunks:
                        self.vector_store.add_chunks(chunks)
                        logger.info(f"Categoría {category}: {len(chunks)} chunks agregados")
                
                # Guardar vector store
                self.vector_store.save()
                
                logger.info("Sistema RAG reconstruido exitosamente")
            else:
                # Cargar vector store existente
                try:
                    self.vector_store.load()
                    logger.info("Vector store cargado desde cache")
                except Exception as e:
                    logger.warning(f"No se pudo cargar vector store: {e}")
                    # Reconstruir si no se puede cargar
                    self.initialize(force_rebuild=True)
                    return
            
            self.is_initialized = True
            self.last_update_check = time.time()
            
            # Mostrar estadísticas
            stats = self.vector_store.get_stats()
            logger.info(f"Sistema RAG listo: {stats['total_chunks']} chunks, {len(stats['categories'])} categorías")
            
        except Exception as e:
            logger.error(f"Error al inicializar sistema RAG: {e}")
            raise
    
    def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Clasifica una consulta para determinar si usar RAG o GPT
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Dict con clasificación y metadatos
        """
        try:
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
            
            query_lower = query.lower()
            
            # Contar coincidencias
            university_score = sum(1 for keyword in university_keywords if keyword in query_lower)
            general_score = sum(1 for keyword in general_keywords if keyword in query_lower)
            
            # Determinar tipo de consulta con umbral más bajo
            if university_score > 0:  # Cualquier palabra universitaria
                query_type = "university"
                confidence = min((university_score + 0.5) / 2.0, 1.0)  # Boost inicial
            elif general_score > 0:  # Cualquier palabra general
                query_type = "general"
                confidence = min((general_score + 0.5) / 2.0, 1.0)
            else:
                # Si no hay palabras clave, intentar clasificar por contexto
                if any(word in query_lower for word in ['qué', 'cuál', 'cómo', 'dónde', 'cuándo', 'por qué']):
                    # Preguntas con interrogantes suelen ser universitarias en este contexto
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
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Error al clasificar consulta: {e}")
            return {
                "query_type": "unknown",
                "confidence": 0.0,
                "university_score": 0,
                "general_score": 0,
                "query": query
            }
    
    @staticmethod
    def _query_has_word(text: str, word: str) -> bool:
        import re
        return bool(re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE))

    @classmethod
    def _query_has_academic_intent(cls, query_lower: str, keywords: list[str]) -> bool:
        import re
        word_boundary = {"udit", "rac", "tfg", "tfm"}
        for kw in keywords:
            if kw in word_boundary:
                if cls._query_has_word(query_lower, kw):
                    return True
            elif kw in query_lower:
                return True
        return False
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Procesa una consulta usando el sistema RAG.
        Prioridad: 1) Q&A fijo (saludo/identidad). 2) Documentos universitarios (RAG). 3) Resto → LLM.
        """
        try:
            if not self.is_initialized:
                logger.warning("Sistema RAG no inicializado, inicializando...")
                self.initialize()
            
            query_lower = query.lower().strip()

            basic_answer = self.basic_qa_manager.find_basic_answer(query)
            if basic_answer:
                logger.info("Respuesta básica (saludo/identidad): %s", basic_answer.get("type"))
                formatted_answer = self.basic_qa_manager.format_answer(basic_answer["answer"])
                return {
                    "answer": formatted_answer,
                    "emotion": basic_answer["emotion"],
                    "source": "basic_qa",
                    "classification": {"query_type": basic_answer["type"], "confidence": 1.0},
                }

            # Palabras que indican pregunta académica/universitaria → ir al RAG documental
            academic_keywords = [
                'titulación', 'titulacion', 'vías', 'vias', 'normativa', 'normativas',
                'matrícula', 'matricula', 'admisión', 'admission', 'acceso', 'horario', 'horarios',
                'política', 'politica', 'calidad', 'medio ambiente', 'condiciones', 'extinción',
                'rac', 'reglamento', 'documentos', 'procedimiento', 'requisitos', 'trámite', 'tramite',
                'graduación', 'graduacion', 'tfg', 'tfm', 'trabajo fin', 'créditos', 'creditos',
                'asignatura', 'curso', 'curso académico', 'plazo', 'fecha', 'inscripción',
                'secretaría', 'secretaria', 'biblioteca', 'atención', 'atencion', 'universidad',
                'udit', 'académic', 'academic', 'estudios', 'grado', 'máster', 'master', 'posgrado'
            ]
            is_academic_query = self._query_has_academic_intent(query_lower, academic_keywords)

            if (
                self._query_has_word(query_lower, "udit")
                and any(
                    p in query_lower
                    for p in ("direccion", "dirección", "sede", "sedes", "donde esta", "dónde está")
                )
            ):
                addr = _fixed_answer("udit_address")
                if addr:
                    return {
                        "answer": addr,
                        "emotion": "neutral",
                        "source": "fixed_udit_address",
                        "classification": {"query_type": "university", "confidence": 1.0},
                    }
            
            # Clasificar y usar RAG para todo lo demás
            classification = self.classify_query(query)
            logger.info("Consulta clasificada como: %s (confianza: %.2f)", classification['query_type'], classification['confidence'])
            
            query_embedding = self.vector_store.get_embedding(query)
            memory_context = self.memory_manager.get_context(query, query_embedding)
            
            # Preguntas universitarias o con palabras académicas → RAG
            use_rag = (
                is_academic_query or
                (classification['query_type'] == "university" and classification['confidence'] > 0.1)
            )
            
            if use_rag:
                logger.info("Usando RAG para pregunta universitaria/académica")
                
                # Detectar si la pregunta es sobre horarios o servicios específicos
                query_lower = query.lower()
                is_schedule_query = any(word in query_lower for word in [
                    'horario', 'horarios', 'hora', 'abre', 'cierra', 'atención', 
                    'administrativa', 'biblioteca', 'secretaría', 'matrícula',
                    'servicios', 'atención al público', 'cuándo', 'a qué hora'
                ])
                
                # Buscar en vector store
                search_results = self.vector_store.search(query)
                
                if search_results:
                    # Si es pregunta sobre horarios, priorizar información de horarios
                    if is_schedule_query:
                        # Buscar específicamente en la categoría de horarios
                        schedule_results = self.vector_store.search_by_category(query, "university_schedules", top_k=5)
                        
                        # Combinar resultados, priorizando horarios
                        if schedule_results:
                            # Agregar resultados de horarios al inicio
                            combined_results = schedule_results + search_results
                            # Eliminar duplicados manteniendo el orden
                            seen = set()
                            unique_results = []
                            for result in combined_results:
                                result_id = f"{result['source_file']}_{result['chunk_id']}"
                                if result_id not in seen:
                                    seen.add(result_id)
                                    unique_results.append(result)
                            search_results = unique_results[:10]  # Mantener solo los primeros 10
                            
                            logger.info(f"Pregunta sobre horarios detectada, priorizando información de horarios")
                    
                    # Construir contexto
                    context_text = "\n".join([
                        f"Documento {i+1} ({result['category_name']}): {result['text']}"
                        for i, result in enumerate(search_results[:3])
                    ])
                    
                    # Generar respuesta usando el contexto
                    response = self._generate_rag_response(query, context_text, memory_context)
                    response['source'] = 'rag'
                    response['search_results'] = search_results
                    
                else:
                    # No se encontró información relevante en los documentos → respuesta amable
                    response = {
                        "answer": "No encontré información específica sobre eso en los documentos que tengo. Te recomiendo consultar en Secretaría o en la web de la universidad para detalles sobre trámites y normativa. ¿Quieres que busque otro tema?",
                        "emotion": "neutral",
                        "source": "rag_no_results",
                        "search_results": []
                    }
                    
            else:
                # Usar GPT para preguntas generales
                logger.info("Usando GPT para pregunta general")
                response = self._generate_gpt_response(query, memory_context)
                response['source'] = 'gpt'
            
            # Actualizar memoria
            self.memory_manager.add_memory(query, response['answer'], query_embedding)
            
            # Agregar metadatos de clasificación
            response['classification'] = classification
            
            return response
            
        except Exception as e:
            logger.error(f"Error al procesar consulta: {e}")
            return {
                "answer": "Lo siento, tuve un problema al procesar tu pregunta. ¿Podrías intentarlo de nuevo?",
                "emotion": "neutral",
                "source": "error",
                "classification": {"query_type": "error", "confidence": 0.0}
            }
    
    def _generate_rag_response(self, query: str, context: str, memory_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Genera respuesta usando RAG con el LLM configurado (TinyLlama o Gemma)."""
        try:
            # Si tenemos LLM disponible, usarlo para generar respuesta natural
            if self.llm and self.llm.is_initialized:
                llm_name = getattr(self.llm, "get_model_info", lambda: {})().get("model_type", "LLM")
                logger.info("Generando respuesta con LLM %s", llm_name)
                
                # Construir contexto de memoria
                memory_text = ""
                if memory_context:
                    memory_text = "\n\nContexto previo:\n" + "\n".join([
                        f"- {item['query']}: {item['answer']}"
                        for item in memory_context[:2]
                    ])
                
                # Combinar contexto RAG con memoria
                full_context = context + memory_text
                
                # Generar respuesta con el LLM configurado
                response_text = self.llm.generate_response(query, full_context)
                
                logger.info("Respuesta generada exitosamente con LLM")
                
            else:
                # Fallback: respuesta mejorada y más amigable
                logger.warning("LLM no disponible, usando respuesta mejorada")
                
                # Construir contexto de memoria
                memory_text = ""
                if memory_context:
                    memory_text = "\n\nContexto previo:\n" + "\n".join([
                        f"- {item['query']}: {item['answer']}"
                        for item in memory_context[:2]
                    ])
                
                # Detectar si es pregunta sobre horarios
                query_lower = query.lower()
                is_schedule_query = any(word in query_lower for word in [
                    'horario', 'horarios', 'hora', 'abre', 'cierra', 'atención', 
                    'administrativa', 'biblioteca', 'secretaría', 'matrícula',
                    'servicios', 'atención al público', 'cuándo', 'a qué hora'
                ])
                
                # Analizar el contexto para generar una respuesta más específica
                context_lines = context.split('\n')
                relevant_info = []
                
                # Buscar información más relevante basada en palabras clave de la consulta
                query_words = query.lower().split()
                
                for line in context_lines:
                    # Calcular relevancia de la línea
                    relevance_score = sum(1 for word in query_words if word in line.lower())
                    if relevance_score > 0:
                        relevant_info.append((line, relevance_score))
                
                # Ordenar por relevancia
                relevant_info.sort(key=lambda x: x[1], reverse=True)
                
                if relevant_info:
                    # Usar las líneas más relevantes
                    top_relevant = [line for line, score in relevant_info[:5]]
                    specific_context = "\n".join(top_relevant)
                    
                    # Generar respuesta más natural y amigable
                    if is_schedule_query:
                        response_text = self._generate_friendly_schedule_response(query_lower, specific_context)
                    else:
                        response_text = self._generate_friendly_general_response(query_lower, specific_context)
                        
                else:
                    # Usar todo el contexto si no hay coincidencias específicas
                    response_text = f"Te ayudo con la información que tengo disponible sobre la universidad:\n\n{context}\n\n¿Hay algo específico que te gustaría saber?"
            
            response = {
                "answer": response_text,
                "emotion": "helpful",
                "llm_used": self.llm is not None and self.llm.is_initialized
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error al generar respuesta RAG: {e}")
            return {
                "answer": "Lo siento, tuve un problema al generar la respuesta.",
                "emotion": "neutral",
                "llm_used": False
            }
    
    def _generate_friendly_schedule_response(self, query_lower: str, context: str) -> str:
        """Genera respuesta amigable para preguntas sobre horarios"""
        # Extraer horas del contexto
        import re
        
        # Buscar patrones de horas
        time_patterns = [
            r'(\d{1,2}):(\d{2})',  # 8:00, 18:00
            r'(\d{1,2})\.(\d{2})',  # 8.00, 18.00
            r'(\d{1,2})h',          # 8h, 18h
            r'(\d{1,2}) horas',     # 8 horas
            r'(\d{1,2}) AM',        # 8 AM
            r'(\d{1,2}) PM',        # 6 PM
        ]
        
        hours = []
        for pattern in time_patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    hour = int(match[0])
                    minute = int(match[1])
                    hours.append((hour, minute))
                else:
                    hour = int(match[0])
                    hours.append((hour, 0))
        
        # Ordenar horas
        hours.sort()
        
        if hours:
            # Formatear horas de manera amigable
            time_texts = []
            for hour, minute in hours:
                if minute == 0:
                    time_texts.append(f"{hour} cero cero")
                else:
                    time_texts.append(f"{hour} {minute:02d}")
            
            # Generar respuesta contextual
            if any(word in query_lower for word in ['administrativa', 'administración']):
                response = f"¡Perfecto! Te cuento sobre los horarios administrativos de la universidad:\n\n"
                if len(time_texts) >= 2:
                    response += f"La atención administrativa está disponible desde las {time_texts[0]} hasta las {time_texts[-1]}."
                else:
                    response += f"La atención administrativa está disponible a las {time_texts[0]}."
                
            elif any(word in query_lower for word in ['biblioteca']):
                response = f"¡Claro! Los horarios de la biblioteca son:\n\n"
                if len(time_texts) >= 2:
                    response += f"La biblioteca abre a las {time_texts[0]} y cierra a las {time_texts[-1]}."
                else:
                    response += f"La biblioteca está disponible a las {time_texts[0]}."
                    
            elif any(word in query_lower for word in ['secretaría']):
                response = f"¡Te ayudo con los horarios de secretaría!\n\n"
                if len(time_texts) >= 2:
                    response += f"La secretaría académica atiende desde las {time_texts[0]} hasta las {time_texts[-1]}."
                else:
                    response += f"La secretaría está disponible a las {time_texts[0]}."
                    
            elif any(word in query_lower for word in ['matrícula']):
                response = f"¡Importante! Los horarios especiales de matrícula son:\n\n"
                if len(time_texts) >= 2:
                    response += f"Durante el período de matrícula, el horario se extiende desde las {time_texts[0]} hasta las {time_texts[-1]}."
                else:
                    response += f"El horario especial de matrícula es a las {time_texts[0]}."
                    
            elif any(word in query_lower for word in ['abre', 'cierra']):
                response = f"¡Te cuento los horarios de apertura y cierre!\n\n"
                if len(time_texts) >= 2:
                    response += f"La universidad abre a las {time_texts[0]} y cierra a las {time_texts[-1]}."
                else:
                    response += f"El horario de la universidad es a las {time_texts[0]}."
                    
            else:
                response = f"¡Perfecto! Los horarios de la universidad son:\n\n"
                if len(time_texts) >= 2:
                    response += f"El horario general es desde las {time_texts[0]} hasta las {time_texts[-1]}."
                else:
                    response += f"El horario es a las {time_texts[0]}."
            
            # Agregar información adicional del contexto
            context_lines = context.split('\n')
            additional_info = []
            for line in context_lines:
                if any(word in line.lower() for word in ['especial', 'extendido', 'período', 'vacaciones']):
                    additional_info.append(line)
            
            if additional_info:
                response += "\n\n" + "\n".join(additional_info[:2])
                
        else:
            # Si no se encontraron horas específicas
            response = f"Te ayudo con la información de horarios que tengo disponible:\n\n{context}\n\n¿Te gustaría saber algo más específico sobre algún servicio en particular?"
        
        return response
    
    def _generate_friendly_general_response(self, query_lower: str, context: str) -> str:
        """Genera respuesta amigable para preguntas generales universitarias"""
        
        # Detectar tipo de pregunta
        if any(word in query_lower for word in ['normativa', 'reglamento', 'política']):
            response = f"¡Te ayudo con la normativa universitaria!\n\n"
            response += f"Según los documentos oficiales que tengo:\n\n{context}\n\n"
            response += "Esta es la normativa aplicable según los documentos oficiales de la universidad."
            
        elif any(word in query_lower for word in ['admisión', 'acceso']):
            response = f"¡Perfecto! Te cuento sobre los procesos de admisión:\n\n"
            response += f"Según la información disponible:\n\n{context}\n\n"
            response += "Esta información te ayudará con el proceso de admisión y acceso a la universidad."
            
        elif any(word in query_lower for word in ['matrícula', 'inscripción']):
            response = f"¡Te ayudo con la información de matrícula!\n\n"
            response += f"Según los documentos:\n\n{context}\n\n"
            response += "Esta información te guiará en el proceso de matrícula."
            
        elif any(word in query_lower for word in ['condiciones', 'requisitos']):
            response = f"¡Claro! Te explico las condiciones y requisitos:\n\n"
            response += f"Según la normativa:\n\n{context}\n\n"
            response += "Estas son las condiciones generales que debes tener en cuenta."
            
        else:
            response = f"¡Te ayudo con la información universitaria!\n\n"
            response += f"Según los documentos que tengo disponibles:\n\n{context}\n\n"
            response += "Esta información responde a tu consulta sobre la universidad."
        
        return response
    
    def _generate_gpt_response(self, query: str, memory_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Genera respuesta usando GPT para preguntas generales"""
        try:
            # Por ahora, devolvemos una respuesta simple
            # En el futuro, aquí se integraría con GPT
            response = {
                "answer": f"Para tu pregunta sobre '{query}', te puedo ayudar con información general. Sin embargo, para detalles específicos de la universidad, te recomiendo consultar los documentos oficiales.",
                "emotion": "helpful"
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error al generar respuesta GPT: {e}")
            return {
                "answer": "Lo siento, tuve un problema al generar la respuesta.",
                "emotion": "neutral"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema RAG"""
        try:
            vector_stats = self.vector_store.get_stats()
            rag_status = self.rag_manager.get_status()
            
            return {
                "system_initialized": self.is_initialized,
                "vector_store": vector_stats,
                "rag_manager": rag_status,
                "last_update_check": self.last_update_check
            }
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}
    
    def update_documents(self):
        """Actualiza los documentos del sistema"""
        try:
            logger.info("Actualizando documentos...")
            self.initialize(force_rebuild=True)
            logger.info("Documentos actualizados exitosamente")
        except Exception as e:
            logger.error(f"Error al actualizar documentos: {e}")

if __name__ == "__main__":
    # Ejemplo de uso
    rag_system = RAGSystem()
    
    # Inicializar sistema
    rag_system.initialize()
    
    # Mostrar estadísticas
    stats = rag_system.get_stats()
    print("Estadísticas del Sistema RAG:")
    print(json.dumps(stats, indent=2))
    
    # Probar consultas
    test_queries = [
        "¿Cuáles son los horarios de la universidad?",
        "¿Qué tiempo hace hoy?",
        "¿Cuál es la normativa de admisión?",
        "¿A qué distancia está la luna?"
    ]
    
    print("\nProbando consultas:")
    for query in test_queries:
        print(f"\nConsulta: {query}")
        response = rag_system.process_query(query)
        print(f"Respuesta: {response['answer']}")
        print(f"Tipo: {response['classification']['query_type']}")
        print(f"Confianza: {response['classification']['confidence']:.2f}") 