#!/usr/bin/env python3
"""
Sistema de Vector Store para RAG
Usa FAISS para almacenar y buscar embeddings de documentos
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import numpy as np
import pickle
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VectorStore")

class VectorStore:
    def __init__(self, config_path: str = "config/rag_config.json"):
        """Inicializa el vector store"""
        self.config_path = config_path
        self.config = self._load_config()
        self.rag_settings = self.config['rag_settings']
        
        # Configurar directorios
        self.cache_dir = Path(self.rag_settings['cache_dir'])
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar componentes
        self.embedding_model = None
        self.index = None
        self.chunks = []
        self.chunk_embeddings = []
        
        # Cargar modelo de embeddings
        self._load_embedding_model()
        
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            raise
    
    def _load_embedding_model(self):
        """Carga el modelo de embeddings"""
        try:
            from sentence_transformers import SentenceTransformer
            
            model_name = self.rag_settings['embedding_model']
            logger.info(f"Cargando modelo de embeddings: {model_name}")
            
            self.embedding_model = SentenceTransformer(model_name)
            logger.info("Modelo de embeddings cargado exitosamente")
            
        except ImportError:
            logger.error("sentence-transformers no está instalado. Instalando...")
            try:
                import subprocess
                subprocess.check_call(["pip", "install", "sentence-transformers"])
                self._load_embedding_model()
            except Exception as e:
                logger.error(f"Error al instalar sentence-transformers: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Error al cargar modelo de embeddings: {e}")
            raise
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Obtiene el embedding de un texto"""
        try:
            if self.embedding_model is None:
                raise ValueError("Modelo de embeddings no cargado")
            
            # Limpiar y normalizar texto
            text = text.strip()
            if not text:
                return np.zeros(self.embedding_model.get_sentence_embedding_dimension())
            
            # Generar embedding
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding
            
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return np.zeros(self.embedding_model.get_sentence_embedding_dimension())
    
    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Agrega chunks al vector store
        
        Args:
            chunks: Lista de chunks con texto y metadatos
        """
        try:
            if not chunks:
                return
            
            logger.info(f"Agregando {len(chunks)} chunks al vector store")
            
            # Generar embeddings para todos los chunks
            texts = [chunk['text'] for chunk in chunks]
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            
            # Agregar a la lista
            self.chunks.extend(chunks)
            self.chunk_embeddings.extend(embeddings)
            
            logger.info(f"Vector store actualizado: {len(self.chunks)} chunks total")
            
        except Exception as e:
            logger.error(f"Error al agregar chunks: {e}")
    
    def search(self, query: str, top_k: int = None, threshold: float = None) -> List[Dict[str, Any]]:
        """
        Busca chunks similares a una consulta
        
        Args:
            query: Texto de consulta
            top_k: Número máximo de resultados
            threshold: Umbral de similitud mínimo
            
        Returns:
            Lista de chunks similares con scores
        """
        try:
            if not self.chunks or not self.chunk_embeddings:
                logger.warning("Vector store vacío")
                return []
            
            if top_k is None:
                top_k = self.rag_settings['max_results']
            if threshold is None:
                threshold = self.rag_settings['similarity_threshold']
            
            # Generar embedding de la consulta
            query_embedding = self.get_embedding(query)
            
            # Calcular similitudes
            similarities = []
            for i, chunk_embedding in enumerate(self.chunk_embeddings):
                similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                if similarity >= threshold:
                    similarities.append((i, similarity))
            
            # Ordenar por similitud
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Obtener resultados
            results = []
            for chunk_idx, similarity in similarities[:top_k]:
                chunk = self.chunks[chunk_idx].copy()
                chunk['similarity'] = float(similarity)
                chunk['rank'] = len(results) + 1
                results.append(chunk)
            
            logger.info(f"Búsqueda completada: {len(results)} resultados")
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            return []
    
    def search_by_category(self, query: str, category: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Busca chunks similares dentro de una categoría específica
        
        Args:
            query: Texto de consulta
            category: Categoría de documentos
            top_k: Número máximo de resultados
            
        Returns:
            Lista de chunks similares de la categoría
        """
        try:
            # Filtrar chunks por categoría
            category_chunks = []
            category_embeddings = []
            
            for i, chunk in enumerate(self.chunks):
                if chunk.get('category') == category:
                    category_chunks.append(chunk)
                    category_embeddings.append(self.chunk_embeddings[i])
            
            if not category_chunks:
                logger.warning(f"No hay chunks en la categoría: {category}")
                return []
            
            # Generar embedding de la consulta
            query_embedding = self.get_embedding(query)
            
            # Calcular similitudes
            similarities = []
            for i, chunk_embedding in enumerate(category_embeddings):
                similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                similarities.append((i, similarity))
            
            # Ordenar por similitud
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Obtener resultados
            results = []
            for chunk_idx, similarity in similarities[:top_k]:
                chunk = category_chunks[chunk_idx].copy()
                chunk['similarity'] = float(similarity)
                chunk['rank'] = len(results) + 1
                results.append(chunk)
            
            logger.info(f"Búsqueda en categoría {category}: {len(results)} resultados")
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda por categoría: {e}")
            return []
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calcula la similitud coseno entre dos vectores"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            logger.error(f"Error al calcular similitud: {e}")
            return 0.0
    
    def save(self, filename: str = None):
        """Guarda el vector store en disco"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"vector_store_{timestamp}.pkl"
            
            filepath = self.cache_dir / filename
            
            # Preparar datos para guardar
            data = {
                'chunks': self.chunks,
                'chunk_embeddings': self.chunk_embeddings,
                'config': self.rag_settings,
                'created_at': datetime.now().isoformat()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Vector store guardado en: {filepath}")
            
        except Exception as e:
            logger.error(f"Error al guardar vector store: {e}")
    
    def load(self, filename: str = None):
        """Carga el vector store desde disco"""
        try:
            if filename is None:
                # Buscar el archivo más reciente
                files = list(self.cache_dir.glob("vector_store_*.pkl"))
                if not files:
                    logger.warning("No se encontraron archivos de vector store")
                    return
                
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                filename = files[0].name
            
            filepath = self.cache_dir / filename
            
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            self.chunks = data['chunks']
            self.chunk_embeddings = data['chunk_embeddings']
            
            logger.info(f"Vector store cargado desde: {filepath}")
            logger.info(f"Chunks cargados: {len(self.chunks)}")
            
        except Exception as e:
            logger.error(f"Error al cargar vector store: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del vector store"""
        try:
            categories = {}
            for chunk in self.chunks:
                category = chunk.get('category', 'unknown')
                if category not in categories:
                    categories[category] = 0
                categories[category] += 1
            
            return {
                'total_chunks': len(self.chunks),
                'categories': categories,
                'embedding_dimension': len(self.chunk_embeddings[0]) if self.chunk_embeddings else 0,
                'model_name': self.rag_settings['embedding_model']
            }
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}
    
    def clear(self):
        """Limpia el vector store"""
        self.chunks = []
        self.chunk_embeddings = []
        logger.info("Vector store limpiado")

if __name__ == "__main__":
    # Ejemplo de uso
    vector_store = VectorStore()
    
    # Mostrar estadísticas
    stats = vector_store.get_stats()
    print("Estadísticas del Vector Store:")
    print(json.dumps(stats, indent=2)) 