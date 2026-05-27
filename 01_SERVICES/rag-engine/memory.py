import json
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import os
from pathlib import Path
import numpy as np

class MemoryManager:
    def __init__(self, config_path: str = "config/settings.json"):
        self.logger = logging.getLogger("MemoryManager")
        self.config = self._load_config(config_path)
        self.logger.setLevel(logging.getLevelName(self.config['system']['log_level']))
        
        # Inicializar memoria
        self.memory = []
        self.context = []
        self.max_memory_size = 100
        self.memory_dir = Path("data/memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self, config_path: str) -> dict:
        """Cargar configuración; si el archivo no existe, usa valores por defecto."""
        default_config = {
            "system": {"log_level": "INFO"},
            "rag": {"max_context_chunks": 5},
        }
        try:
            path = Path(config_path)
            if not path.is_absolute():
                path = path.resolve()
            if not path.exists():
                self.logger.warning(f"Config no encontrado: {path}, usando valores por defecto")
                return default_config
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            self.logger.warning(f"Error cargando config: {e}, usando valores por defecto")
            return default_config
            
    def _save_memory(self):
        """Guardar memoria en disco"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.memory_dir / f"memory_{timestamp}.json"
            
            # Convertir numpy arrays a list para serialización
            memory_serializable = []
            for item in self.memory:
                memory_serializable.append({
                    "query": item["query"],
                    "answer": item["answer"],
                    "embedding": item["embedding"].tolist(),
                    "timestamp": item["timestamp"]
                })
            
            with open(filename, 'w') as f:
                json.dump(memory_serializable, f)
                
            self.logger.info(f"Memory saved to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error saving memory: {e}")
            
    def _load_memory(self) -> List[Dict[str, Any]]:
        """Cargar memoria desde disco"""
        try:
            # Obtener archivos de memoria ordenados por fecha
            memory_files = sorted(
                self.memory_dir.glob("memory_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if memory_files:
                latest_file = memory_files[0]
                with open(latest_file, 'r') as f:
                    memory_data = json.load(f)
                    
                # Convertir listas de vuelta a numpy arrays
                memory = []
                for item in memory_data:
                    memory.append({
                        "query": item["query"],
                        "answer": item["answer"],
                        "embedding": np.array(item["embedding"]),
                        "timestamp": item["timestamp"]
                    })
                    
                self.logger.info(f"Memory loaded from {latest_file}")
                return memory
                
            return []
            
        except Exception as e:
            self.logger.error(f"Error loading memory: {e}")
            return []
            
    def _cleanup_old_memory(self):
        """Limpiar memoria antigua"""
        try:
            # Obtener archivos de memoria
            memory_files = sorted(
                self.memory_dir.glob("memory_*.json"),
                key=lambda x: x.stat().st_mtime
            )
            
            # Mantener solo los últimos 10 archivos
            if len(memory_files) > 10:
                for file in memory_files[:-10]:
                    file.unlink()
                    self.logger.info(f"Removed old memory file: {file}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up memory: {e}")
            
    def add_memory(self, query: str, answer: str, embedding: np.ndarray):
        """
        Añadir nueva memoria
        
        Args:
            query: Pregunta original
            answer: Respuesta generada
            embedding: Embedding del contexto
        """
        try:
            # Limpiar memoria si está llena
            if len(self.memory) >= self.max_memory_size:
                self.memory = self.memory[-self.max_memory_size//2:]
                
            # Añadir nueva memoria
            self.memory.append({
                "query": query,
                "answer": answer,
                "embedding": embedding,
                "timestamp": datetime.now().isoformat()
            })
            
            # Guardar en disco
            self._save_memory()
            
        except Exception as e:
            self.logger.error(f"Error adding memory: {e}")
            
    def get_context(self, query: str, embedding: np.ndarray) -> List[Dict[str, Any]]:
        """
        Obtener contexto relevante
        
        Args:
            query: Pregunta actual
            embedding: Embedding de la pregunta
            
        Returns:
            Lista de contextos relevantes
        """
        try:
            # Cargar memoria si está vacía
            if not self.memory:
                self.memory = self._load_memory()
                
            # Calcular similitudes
            similarities = []
            for item in self.memory:
                similarity = self._cosine_similarity(
                    embedding,
                    item["embedding"]
                )
                similarities.append((item, similarity))
                
            # Ordenar por similitud
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Seleccionar contexto más relevante
            context = []
            for item, similarity in similarities[:self.config['rag']['max_context_chunks']]:
                if similarity > 0.7:
                    context.append({
                        "query": item["query"],
                        "answer": item["answer"],
                        "similarity": similarity
                    })
                    
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting context: {e}")
            return []
            
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calcular similitud coseno entre vectores"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2)
