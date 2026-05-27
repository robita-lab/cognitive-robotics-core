from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
import os
from pathlib import Path

from rag_system import RAGSystem

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="RAG Engine", version="1.0")

_BASE = Path(__file__).resolve().parent
CONFIG_PATH = str(_BASE / "config" / "rag_config.json")
SETTINGS_PATH = str(_BASE / "config" / "settings.json")

rag_system: RAGSystem | None = None


class QueryRequest(BaseModel):
    text: str
    collection: str = "general"
    n_results: int = 4
    system_prompt: Optional[str] = None


class IngestRequest(BaseModel):
    collection: str
    documents: List[str]
    metadatas: Optional[List[dict]] = None
    ids: Optional[List[str]] = None


class RouterRequest(BaseModel):
    text: str


@app.on_event("startup")
async def startup():
    global rag_system
    os.chdir(_BASE)
    rag_system = RAGSystem(config_path=CONFIG_PATH, settings_path=SETTINGS_PATH)
    rag_system.initialize(force_rebuild=False)
    logging.info("RAG Engine listo")


@app.get("/health")
def health():
    backend = "tinyllama"
    if rag_system and rag_system.llm:
        backend = type(rag_system.llm).__name__
    return {"status": "ok", "backend": backend, "vector_store": "faiss"}


@app.get("/collections")
def list_collections():
    if rag_system is None:
        raise HTTPException(503, "RAG no inicializado")
    categories = list(rag_system.rag_manager.config.get("documents", {}).keys())
    return {"collections": categories}


@app.post("/ingest")
def ingest(req: IngestRequest):
    if rag_system is None:
        raise HTTPException(503, "RAG no inicializado")
    chunks = []
    for i, doc in enumerate(req.documents):
        chunks.append({
            "text": doc,
            "category": req.collection,
            "category_name": req.collection,
            "source_file": f"ingest_{req.ids[i] if req.ids else i}",
            "chunk_id": i,
        })
    rag_system.vector_store.add_chunks(chunks)
    rag_system.vector_store.save()
    return {"ingested": len(req.documents), "collection": req.collection}


@app.post("/query")
def query(req: QueryRequest):
    if rag_system is None:
        raise HTTPException(503, "RAG no inicializado")
    result = rag_system.process_query(req.text)
    answer = result.get("answer", "")
    sources = result.get("search_results") or []
    return {
        "answer": answer,
        "collection": req.collection,
        "sources_used": len(sources),
        "source": result.get("source", "rag"),
    }


@app.post("/route")
def route_query(req: RouterRequest):
    if rag_system is None:
        raise HTTPException(503, "RAG no inicializado")
    classification = rag_system.classify_query(req.text)
    query_type = classification.get("query_type", "general")
    mapping = {
        "university": "admisiones",
        "general": "general",
        "unknown": "general",
    }
    collection = mapping.get(query_type, "general")
    return {"collection": collection, "query": req.text, "classification": classification}
