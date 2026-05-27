#!/usr/bin/env python3
"""
Procesador de documentos para el sistema RAG
Extrae texto de PDFs y crea chunks para embeddings
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import hashlib
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DocumentProcessor")

class DocumentProcessor:
    def __init__(self, config_path: str = "config/rag_config.json", project_root: str = None):
        """Inicializa el procesador de documentos.
        project_root: si se pasa (p. ej. desde el notebook), se usa como raíz para docs/; si no, se infiere del path del config.
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.rag_settings = self.config['rag_settings']
        if project_root is not None:
            self._project_root = Path(project_root).resolve()
        else:
            self._project_root = Path(config_path).resolve().parent.parent
        self.cache_dir = (self._project_root / "data" / "rag_cache").resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración del RAG"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            raise
    
    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extrae texto de un archivo PDF"""
        try:
            import PyPDF2  # pyright: ignore[reportMissingImports]
            
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Página {page_num + 1} ---\n"
                        text += page_text + "\n"
            
            logger.info(f"Texto extraído de {pdf_path}: {len(text)} caracteres")
            return text.strip()
            
        except ImportError:
            logger.error("PyPDF2 no está instalado. Instalando...")
            try:
                import subprocess
                subprocess.check_call(["pip", "install", "PyPDF2"])
                return self.extract_text_from_pdf(pdf_path)
            except Exception as e:
                logger.error(f"Error al instalar PyPDF2: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error al extraer texto de {pdf_path}: {e}")
            return None
    
    def create_chunks(self, text: str, chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """
        Crea chunks de texto para procesamiento
        
        Args:
            text: Texto a dividir en chunks
            chunk_size: Tamaño de cada chunk (caracteres)
            overlap: Solapamiento entre chunks
            
        Returns:
            Lista de chunks con metadatos
        """
        if chunk_size is None:
            chunk_size = self.rag_settings['chunk_size']
        if overlap is None:
            overlap = self.rag_settings['chunk_overlap']
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Extraer chunk
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # Buscar el final de una oración si es posible
            if end < len(text):
                # Buscar el último punto, signo de exclamación o interrogación
                last_sentence_end = max(
                    chunk_text.rfind('.'),
                    chunk_text.rfind('!'),
                    chunk_text.rfind('?'),
                    chunk_text.rfind('\n')
                )
                
                if last_sentence_end > chunk_size * 0.7:  # Si encontramos un buen punto de corte
                    end = start + last_sentence_end + 1
                    chunk_text = text[start:end]
            
            # Crear chunk con metadatos
            chunk = {
                'text': chunk_text.strip(),
                'start_char': start,
                'end_char': end,
                'length': len(chunk_text),
                'chunk_id': len(chunks)
            }
            
            chunks.append(chunk)
            
            # Mover al siguiente chunk con solapamiento
            start = end - overlap
            if start >= len(text):
                break
        
        logger.info(f"Creados {len(chunks)} chunks de texto")
        return chunks
    
    def process_document(self, file_path: str, file_type: str = "pdf") -> List[Dict[str, Any]]:
        """
        Procesa un documento completo
        
        Args:
            file_path: Ruta al archivo
            file_type: Tipo de archivo (pdf, txt, etc.)
            
        Returns:
            Lista de chunks procesados
        """
        try:
            # Resolver ruta respecto a la raíz del proyecto
            full_path = Path(file_path)
            if not full_path.is_absolute():
                full_path = self._project_root / file_path
            full_path = full_path.resolve()
            if not full_path.exists():
                logger.error(f"Archivo no encontrado: {full_path}")
                return []
            file_path = str(full_path)
            
            # Generar hash del archivo para cache
            file_hash = self._get_file_hash(file_path)
            cache_file = self.cache_dir / f"{file_hash}.json"
            
            # Verificar cache
            if cache_file.exists():
                logger.info(f"Cargando chunks desde cache: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Extraer texto según el tipo de archivo
            if file_type.lower() == "pdf":
                text = self.extract_text_from_pdf(file_path)
            elif file_type.lower() == "txt":
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                logger.error(f"Tipo de archivo no soportado: {file_type}")
                return []
            
            if not text:
                logger.warning(f"No se pudo extraer texto de {file_path}")
                return []
            
            # Crear chunks
            chunks = self.create_chunks(text)
            
            # Agregar metadatos del documento
            for chunk in chunks:
                chunk.update({
                    'source_file': file_path,
                    'file_type': file_type,
                    'file_hash': file_hash,
                    'processed_at': datetime.now().isoformat()
                })
            
            # Guardar en cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Documento procesado y cacheado: {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error al procesar documento {file_path}: {e}")
            return []
    
    def process_all_documents(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Procesa todos los documentos configurados
        
        Returns:
            Diccionario con chunks por categoría
        """
        all_chunks = {}
        
        for category, category_data in self.config['documents'].items():
            if not category_data.get('enabled', True):
                continue
                
            category_chunks = []
            
            for file_info in category_data.get('files', []):
                if not file_info.get('enabled', True):
                    continue
                
                file_path = file_info['path']
                file_type = file_info['type']
                
                logger.info(f"Procesando documento: {file_path}")
                chunks = self.process_document(file_path, file_type)
                
                # Agregar metadatos de categoría
                for chunk in chunks:
                    chunk.update({
                        'category': category,
                        'category_name': category_data.get('name', category),
                        'priority': category_data.get('priority', 999),
                        'description': file_info.get('description', '')
                    })
                
                category_chunks.extend(chunks)
            
            all_chunks[category] = category_chunks
            logger.info(f"Categoría {category}: {len(category_chunks)} chunks")
        
        return all_chunks
    
    def _get_file_hash(self, file_path: str) -> str:
        """Genera un hash del archivo para cache"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
            return hashlib.md5(file_content).hexdigest()
        except Exception as e:
            logger.error(f"Error al generar hash de {file_path}: {e}")
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def clear_cache(self):
        """Limpia el cache de documentos procesados"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cache de documentos limpiado")
        except Exception as e:
            logger.error(f"Error al limpiar cache: {e}")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Obtiene el estado del cache"""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "cache_dir": str(self.cache_dir),
                "files_count": len(cache_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": [f.name for f in cache_files]
            }
        except Exception as e:
            logger.error(f"Error al obtener estado del cache: {e}")
            return {}

if __name__ == "__main__":
    # Ejemplo de uso
    processor = DocumentProcessor()
    
    # Mostrar estado del cache
    cache_status = processor.get_cache_status()
    print("Estado del cache:")
    print(json.dumps(cache_status, indent=2))
    
    # Procesar todos los documentos
    print("\nProcesando documentos...")
    all_chunks = processor.process_all_documents()
    
    total_chunks = sum(len(chunks) for chunks in all_chunks.values())
    print(f"\nTotal de chunks procesados: {total_chunks}")
    
    for category, chunks in all_chunks.items():
        print(f"- {category}: {len(chunks)} chunks") 