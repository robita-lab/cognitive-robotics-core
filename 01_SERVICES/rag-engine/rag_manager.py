#!/usr/bin/env python3
"""
Gestor de RAG (Retrieval-Augmented Generation) para UDI
Maneja documentos universitarios y configuración dinámica
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RAGManager")

class RAGManager:
    def __init__(self, config_path: str = "config/rag_config.json"):
        """Inicializa el gestor de RAG"""
        self.config_path = config_path
        self.config = self._load_config()
        self.document_cache = {}
        self.last_update = None
        self._validate_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración del RAG"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuración RAG cargada desde {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Archivo de configuración no encontrado: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear configuración JSON: {e}")
            raise
    
    def _validate_config(self):
        """Valida la configuración cargada"""
        required_keys = ['documents', 'rag_settings', 'fallback_settings']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Configuración RAG incompleta: falta '{key}'")
        
        # Validar que los archivos existen
        for category, category_data in self.config['documents'].items():
            if category_data.get('enabled', True):
                for file_info in category_data.get('files', []):
                    if file_info.get('enabled', True):
                        file_path = file_info['path']
                        if not os.path.exists(file_path):
                            logger.warning(f"Archivo no encontrado: {file_path}")
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Obtiene todos los documentos habilitados"""
        documents = []
        for category, category_data in self.config['documents'].items():
            if category_data.get('enabled', True):
                for file_info in category_data.get('files', []):
                    if file_info.get('enabled', True):
                        documents.append({
                            'category': category,
                            'category_name': category_data.get('name', category),
                            'priority': category_data.get('priority', 999),
                            **file_info
                        })
        
        # Ordenar por prioridad
        documents.sort(key=lambda x: x['priority'])
        return documents
    
    def get_documents_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Obtiene documentos de una categoría específica"""
        if category not in self.config['documents']:
            return []
        
        category_data = self.config['documents'][category]
        if not category_data.get('enabled', True):
            return []
        
        documents = []
        for file_info in category_data.get('files', []):
            if file_info.get('enabled', True):
                documents.append({
                    'category': category,
                    'category_name': category_data.get('name', category),
                    'priority': category_data.get('priority', 999),
                    **file_info
                })
        
        return documents
    
    def add_document(self, category: str, file_path: str, file_type: str = "pdf", 
                    description: str = "", enabled: bool = True):
        """Agrega un nuevo documento a la configuración"""
        if category not in self.config['documents']:
            logger.error(f"Categoría '{category}' no existe")
            return False
        
        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return False
        
        # Agregar documento
        new_doc = {
            "path": file_path,
            "type": file_type,
            "description": description,
            "enabled": enabled
        }
        
        self.config['documents'][category]['files'].append(new_doc)
        self._save_config()
        logger.info(f"Documento agregado: {file_path} a categoría {category}")
        return True
    
    def remove_document(self, category: str, file_path: str) -> bool:
        """Elimina un documento de la configuración"""
        if category not in self.config['documents']:
            return False
        
        files = self.config['documents'][category]['files']
        for i, file_info in enumerate(files):
            if file_info['path'] == file_path:
                del files[i]
                self._save_config()
                logger.info(f"Documento eliminado: {file_path} de categoría {category}")
                return True
        
        return False
    
    def enable_document(self, category: str, file_path: str, enabled: bool = True) -> bool:
        """Habilita o deshabilita un documento"""
        if category not in self.config['documents']:
            return False
        
        files = self.config['documents'][category]['files']
        for file_info in files:
            if file_info['path'] == file_path:
                file_info['enabled'] = enabled
                self._save_config()
                status = "habilitado" if enabled else "deshabilitado"
                logger.info(f"Documento {status}: {file_path}")
                return True
        
        return False
    
    def add_category(self, category: str, name: str, description: str = "", 
                    enabled: bool = True, priority: int = 999):
        """Agrega una nueva categoría de documentos"""
        if category in self.config['documents']:
            logger.error(f"La categoría '{category}' ya existe")
            return False
        
        self.config['documents'][category] = {
            "name": name,
            "description": description,
            "enabled": enabled,
            "priority": priority,
            "files": []
        }
        
        self._save_config()
        logger.info(f"Categoría agregada: {category} - {name}")
        return True
    
    def remove_category(self, category: str) -> bool:
        """Elimina una categoría completa"""
        if category not in self.config['documents']:
            return False
        
        del self.config['documents'][category]
        self._save_config()
        logger.info(f"Categoría eliminada: {category}")
        return True
    
    def get_rag_settings(self) -> Dict[str, Any]:
        """Obtiene la configuración de RAG"""
        return self.config['rag_settings']
    
    def get_fallback_settings(self) -> Dict[str, Any]:
        """Obtiene la configuración de fallback"""
        return self.config['fallback_settings']
    
    def update_rag_settings(self, new_settings: Dict[str, Any]):
        """Actualiza la configuración de RAG"""
        self.config['rag_settings'].update(new_settings)
        self._save_config()
        logger.info("Configuración RAG actualizada")
    
    def _save_config(self):
        """Guarda la configuración en el archivo"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"Configuración guardada en {self.config_path}")
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            raise
    
    def check_for_updates(self) -> bool:
        """Verifica si hay cambios en los documentos"""
        current_hash = self._get_documents_hash()
        if self.last_update != current_hash:
            self.last_update = current_hash
            return True
        return False
    
    def _get_documents_hash(self) -> str:
        """Genera un hash de todos los documentos para detectar cambios"""
        documents = self.get_all_documents()
        hash_string = ""
        for doc in documents:
            file_path = doc['path']
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                hash_string += f"{file_path}:{stat.st_mtime}:{stat.st_size}"
        
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del RAG"""
        documents = self.get_all_documents()
        enabled_docs = [doc for doc in documents if doc.get('enabled', True)]
        disabled_docs = [doc for doc in documents if not doc.get('enabled', True)]
        
        return {
            "total_documents": len(documents),
            "enabled_documents": len(enabled_docs),
            "disabled_documents": len(disabled_docs),
            "categories": len(self.config['documents']),
            "last_update": self.last_update,
            "config_file": self.config_path
        }

if __name__ == "__main__":
    # Ejemplo de uso
    rag_manager = RAGManager()
    
    # Mostrar estado
    status = rag_manager.get_status()
    print("Estado del RAG:")
    print(json.dumps(status, indent=2))
    
    # Mostrar documentos
    documents = rag_manager.get_all_documents()
    print(f"\nDocumentos configurados ({len(documents)}):")
    for doc in documents:
        print(f"- {doc['category_name']}: {doc['path']} ({'Habilitado' if doc.get('enabled', True) else 'Deshabilitado'})") 