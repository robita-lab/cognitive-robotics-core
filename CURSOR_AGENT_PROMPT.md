# CURSOR AGENT — Robita-Lab Server Pipeline Setup

> **Cómo usar:** Abre Cursor, activa el modo **Agent** en el Composer (⌘+I → selecciona "Agent"),
> pega este archivo completo y pulsa Enter. El agente leerá el codebase, moverá archivos,
> instalará dependencias y generará todo lo necesario. No interrumpas hasta que termine.

---

## CONTEXTO Y OBJETIVO

Eres el agente de desarrollo del proyecto **Robita-Lab**, un sistema de robótica social con
arquitectura de "Cerebro Centralizado / Cuerpos Distribuidos". El servidor corre Ubuntu Linux.

El repositorio ya tiene la estructura de carpetas creada en `/opt/robita-lab/` (espejada en GitHub).
Ya existen archivos de código previo dispersos con lógica de: **wakeword, STT, TTS y RAG**.

Tu objetivo es:
1. Escanear todo el codebase y localizar los archivos existentes de wakeword, STT, TTS y RAG
2. Reorganizarlos en las ubicaciones correctas de la arquitectura
3. Crear un wrapper FastAPI para cada servicio (cada uno expone su propia API REST)
4. Crear un Dockerfile para cada servicio
5. Crear el `docker-compose.yml` raíz que orqueste todo
6. Crear un servicio orquestador `pipeline-orchestrator` que conecte todo el flujo de voz en un único endpoint

**Todo debe quedar funcional y levantable con `docker-compose up -d`**

---

## ARQUITECTURA OBJETIVO

```
/opt/robita-lab/
├── docker-compose.yml                  ← orquesta todos los servicios
├── .env                                ← variables de entorno globales
│
├── 01_SERVICES/
│   ├── stt-engine/                     → API en :8001
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py                     ← FastAPI wrapper
│   │   └── [archivos STT existentes]
│   │
│   ├── tts-engine/                     → API en :8002
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── [archivos TTS existentes]
│   │
│   ├── wakeword-engine/                → API en :8003
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── [archivos wakeword existentes]
│   │
│   ├── rag-engine/                     → API en :8004
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── [archivos RAG existentes]
│   │
│   └── pipeline-orchestrator/          → API en :8000  ← ENTRADA PRINCIPAL
│       ├── Dockerfile
│       ├── requirements.txt
│       └── main.py
│
├── 02_AGENTS_FACTORY/
│   └── udit-robot-brain/
│       └── config.yaml                 ← perfil y prompts del robot UDITO
│
├── 03_ADAPTERS/
│   └── robot-udit-physical/
│       └── README.md
│
└── 04_KNOWLEDGE_CORE/
    ├── vector-stores/                  ← ChromaDB persistirá aquí
    │   ├── admisiones/
    │   ├── rrhh/
    │   └── general/
    └── raw-docs/                       ← PDFs y documentos fuente
```

---

## PASO 1 — ESCANEAR Y REUBICAR ARCHIVOS EXISTENTES

Primero ejecuta este análisis:

```bash
find /opt/robita-lab -type f \( -name "*.py" -o -name "*.sh" -o -name "*.yaml" -o -name "*.json" \) \
  | grep -v __pycache__ | grep -v .git | sort
```

Luego identifica a qué categoría pertenece cada archivo según su contenido:
- Archivos con lógica de **Whisper**, `speech_recognition`, `audio`, `transcri` → mover a `01_SERVICES/stt-engine/`
- Archivos con lógica de **Piper**, `tts`, `text_to_speech`, `synthesize`, `espeak` → mover a `01_SERVICES/tts-engine/`
- Archivos con lógica de **wakeword**, `porcupine`, `hotword`, `wake`, `keyword` → mover a `01_SERVICES/wakeword-engine/`
- Archivos con lógica de **RAG**, `chromadb`, `qdrant`, `embed`, `retriev`, `llm`, `ollama`, `langchain` → mover a `01_SERVICES/rag-engine/`

Copia (no muevas hasta confirmar) cada archivo a su destino y renombra el original añadiendo `.bak` temporalmente.

---

## PASO 2 — SERVICIO STT (`01_SERVICES/stt-engine/`)

Crea `main.py` con este contrato de API. Integra la lógica existente encontrada:

```python
# 01_SERVICES/stt-engine/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import whisper
import tempfile, os, logging

app = FastAPI(title="STT Engine", version="1.0")
model = None

@app.on_event("startup")
async def load_model():
    global model
    model_name = os.getenv("WHISPER_MODEL", "small")
    logging.info(f"Cargando Whisper modelo: {model_name}")
    model = whisper.load_model(model_name)

@app.get("/health")
def health():
    return {"status": "ok", "model": os.getenv("WHISPER_MODEL", "small")}

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = "es"):
    """
    Recibe un archivo de audio (wav/mp3/ogg) y devuelve el texto transcrito.
    """
    if model is None:
        raise HTTPException(503, "Modelo no cargado")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        result = model.transcribe(tmp_path, language=language, fp16=False)
        return {"text": result["text"].strip(), "language": language, "segments": result.get("segments", [])}
    finally:
        os.unlink(tmp_path)
```

Crea `requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
openai-whisper>=20231117
python-multipart>=0.0.9
```

Crea `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## PASO 3 — SERVICIO TTS (`01_SERVICES/tts-engine/`)

Crea `main.py`:

```python
# 01_SERVICES/tts-engine/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import subprocess, os, tempfile, io, logging

app = FastAPI(title="TTS Engine", version="1.0")

PIPER_MODEL = os.getenv("PIPER_MODEL", "/models/es_ES-davefx-medium.onnx")

class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0

@app.get("/health")
def health():
    return {"status": "ok", "model": PIPER_MODEL}

@app.post("/synthesize")
def synthesize(req: TTSRequest):
    """
    Recibe texto, devuelve audio WAV como stream.
    Empieza a generar en cuanto llegan los primeros tokens (streaming).
    """
    if not req.text.strip():
        raise HTTPException(400, "Texto vacío")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
        out_path = out.name
    try:
        proc = subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", out_path],
            input=req.text.encode("utf-8"),
            capture_output=True
        )
        if proc.returncode != 0:
            raise HTTPException(500, f"Piper error: {proc.stderr.decode()}")
        with open(out_path, "rb") as f:
            audio_bytes = f.read()
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)

@app.post("/synthesize-stream")
async def synthesize_stream(req: TTSRequest):
    """Versión streaming: devuelve audio a medida que se genera."""
    # Implementar con piper --output_raw y chunked response
    return await synthesize(req)
```

Crea `requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.0
```

Crea `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
RUN wget -q https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz \
    -O /tmp/piper.tar.gz && tar -xzf /tmp/piper.tar.gz -C /usr/local/bin && rm /tmp/piper.tar.gz
RUN mkdir -p /models
# Descarga el modelo español si no existe en volumen
RUN wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx" \
    -O /models/es_ES-davefx-medium.onnx || echo "Descarga de modelo fallida, montar volumen con modelo"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

---

## PASO 4 — SERVICIO WAKEWORD (`01_SERVICES/wakeword-engine/`)

Crea `main.py` integrando el código wakeword existente encontrado:

```python
# 01_SERVICES/wakeword-engine/main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.websockets import WebSocket
from pydantic import BaseModel
import os, tempfile, logging

app = FastAPI(title="Wakeword Engine", version="1.0")

# Integrar aquí la lógica del archivo wakeword existente
# Si usa Porcupine: PORCUPINE_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
# Si usa openWakeWord: import openwakeword

@app.get("/health")
def health():
    return {"status": "ok", "engine": os.getenv("WAKEWORD_ENGINE", "openwakeword")}

@app.post("/detect")
async def detect(audio: UploadFile = File(...)):
    """
    Recibe chunk de audio, devuelve si se detectó la palabra de activación.
    """
    audio_bytes = await audio.read()
    # --- INTEGRAR LÓGICA EXISTENTE ---
    # detected = wakeword_model.predict(audio_bytes)
    detected = False  # placeholder hasta integrar
    return {"detected": detected, "confidence": 0.0}

@app.websocket("/stream")
async def stream_detection(websocket: WebSocket):
    """
    WebSocket para detección continua. El cliente envía chunks de audio,
    el servidor responde con JSON {"detected": bool, "confidence": float}.
    """
    await websocket.accept()
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            # detected = wakeword_model.predict(audio_chunk)
            await websocket.send_json({"detected": False, "confidence": 0.0})
    except Exception as e:
        logging.info(f"WebSocket cerrado: {e}")
```

Crea `requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
websockets>=12.0
openwakeword>=0.6.0
python-multipart>=0.0.9
```

Crea `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libportaudio2 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

---

## PASO 5 — SERVICIO RAG (`01_SERVICES/rag-engine/`)

Este es el servicio más importante. Integra la lógica RAG existente:

```python
# 01_SERVICES/rag-engine/main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import chromadb, os, logging
from chromadb.utils import embedding_functions

app = FastAPI(title="RAG Engine", version="1.0")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
CHROMA_PATH = os.getenv("CHROMA_PATH", "/data/chromadb")

chroma_client = None
embed_fn = None

@app.on_event("startup")
async def startup():
    global chroma_client, embed_fn
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    )
    logging.info(f"ChromaDB listo en {CHROMA_PATH}")
    logging.info(f"LLM: {OLLAMA_MODEL} en {OLLAMA_URL}")

# ── Modelos ──────────────────────────────────────────────────────────
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

# ── Endpoints ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL, "chroma": CHROMA_PATH}

@app.get("/collections")
def list_collections():
    cols = chroma_client.list_collections()
    return {"collections": [c.name for c in cols]}

@app.post("/ingest")
def ingest(req: IngestRequest):
    """Ingesta documentos en una colección ChromaDB."""
    col = chroma_client.get_or_create_collection(
        name=req.collection, embedding_function=embed_fn
    )
    ids = req.ids or [f"doc_{i}" for i in range(len(req.documents))]
    meta = req.metadatas or [{} for _ in req.documents]
    col.add(documents=req.documents, metadatas=meta, ids=ids)
    return {"ingested": len(req.documents), "collection": req.collection}

@app.post("/query")
def query(req: QueryRequest):
    """
    Consulta RAG: busca en la colección, construye contexto y llama al LLM vía Ollama.
    """
    import httpx
    try:
        col = chroma_client.get_collection(req.collection, embedding_function=embed_fn)
    except Exception:
        raise HTTPException(404, f"Colección '{req.collection}' no encontrada")

    results = col.query(query_texts=[req.text], n_results=req.n_results)
    docs = results["documents"][0] if results["documents"] else []
    context = "\n\n".join(docs)

    system = req.system_prompt or (
        "Eres un asistente universitario. Responde usando únicamente el contexto proporcionado. "
        "Si no lo sabes, dilo claramente. Responde en español, de forma concisa."
    )

    prompt = f"Contexto:\n{context}\n\nPregunta: {req.text}"

    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": False},
        timeout=60
    )
    response.raise_for_status()
    answer = response.json().get("response", "")
    return {"answer": answer, "collection": req.collection, "sources_used": len(docs)}

@app.post("/route")
def route_query(req: RouterRequest):
    """
    Semantic router: clasifica la consulta y devuelve la colección más adecuada.
    Usa similitud semántica contra intenciones predefinidas por colección.
    """
    import httpx
    collections_desc = {
        "admisiones": "matricula ingreso acceso universidad estudiante nuevo admision",
        "rrhh": "empleado trabajador contrato nomina vacaciones recursos humanos",
        "general": "informacion general campus servicios horarios ubicacion",
    }
    # Simple: pide al LLM que clasifique
    prompt = (
        f"Clasifica esta pregunta en una sola palabra de estas opciones: "
        f"{', '.join(collections_desc.keys())}.\n"
        f"Pregunta: {req.text}\nResponde solo con el nombre de la colección."
    )
    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=30
    )
    collection = response.json().get("response", "general").strip().lower()
    if collection not in collections_desc:
        collection = "general"
    return {"collection": collection, "query": req.text}
```

Crea `requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
chromadb>=0.5.0
httpx>=0.27.0
sentence-transformers>=3.0.0
pydantic>=2.0
python-multipart>=0.0.9
```

Crea `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
```

---

## PASO 6 — ORQUESTADOR (`01_SERVICES/pipeline-orchestrator/`)

Este es el único punto de entrada para el robot y los agentes web:

```python
# 01_SERVICES/pipeline-orchestrator/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx, os, logging, io

app = FastAPI(title="Pipeline Orchestrator", version="1.0")

STT_URL  = os.getenv("STT_URL",  "http://stt-engine:8001")
TTS_URL  = os.getenv("TTS_URL",  "http://tts-engine:8002")
WW_URL   = os.getenv("WW_URL",   "http://wakeword-engine:8003")
RAG_URL  = os.getenv("RAG_URL",  "http://rag-engine:8004")

TIMEOUT = httpx.Timeout(60.0)

@app.get("/health")
def health():
    return {"status": "ok", "services": [STT_URL, TTS_URL, WW_URL, RAG_URL]}

@app.get("/services/status")
async def services_status():
    """Verifica que todos los microservicios estén vivos."""
    results = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in [("stt", STT_URL), ("tts", TTS_URL), ("wakeword", WW_URL), ("rag", RAG_URL)]:
            try:
                r = await client.get(f"{url}/health")
                results[name] = r.json()
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}
    return results

@app.post("/voice-query")
async def voice_query(audio: UploadFile = File(...), collection: str = "general"):
    """
    Pipeline completo de voz:
    1. Detecta si hay audio válido (opcional: wakeword ya resuelto en edge)
    2. STT: audio → texto
    3. RAG router: texto → colección
    4. RAG query: texto + colección → respuesta
    5. TTS: respuesta → audio WAV
    Devuelve el audio de respuesta directamente.
    """
    audio_bytes = await audio.read()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 1. STT
        stt_resp = await client.post(
            f"{STT_URL}/transcribe",
            files={"audio": ("audio.wav", audio_bytes, "audio/wav")}
        )
        stt_resp.raise_for_status()
        text = stt_resp.json()["text"]
        logging.info(f"STT → '{text}'")
        if not text.strip():
            raise HTTPException(400, "No se detectó texto en el audio")

        # 2. Router semántico
        route_resp = await client.post(f"{RAG_URL}/route", json={"text": text})
        routed_collection = route_resp.json().get("collection", collection)
        logging.info(f"Router → colección: {routed_collection}")

        # 3. RAG query
        rag_resp = await client.post(
            f"{RAG_URL}/query",
            json={"text": text, "collection": routed_collection}
        )
        rag_resp.raise_for_status()
        answer = rag_resp.json()["answer"]
        logging.info(f"RAG → '{answer[:80]}...'")

        # 4. TTS
        tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
        tts_resp.raise_for_status()
        audio_out = tts_resp.content

    return StreamingResponse(io.BytesIO(audio_out), media_type="audio/wav",
                             headers={"X-Transcribed-Text": text, "X-Answer": answer[:200]})

class TextQuery(BaseModel):
    text: str
    collection: str = "general"
    respond_with_audio: bool = False

@app.post("/text-query")
async def text_query(req: TextQuery):
    """
    Pipeline solo texto (para agentes web).
    Opcionalmente devuelve también el audio TTS.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        route_resp = await client.post(f"{RAG_URL}/route", json={"text": req.text})
        col = route_resp.json().get("collection", req.collection)

        rag_resp = await client.post(f"{RAG_URL}/query", json={"text": req.text, "collection": col})
        rag_resp.raise_for_status()
        answer = rag_resp.json()["answer"]

        result = {"answer": answer, "collection": col, "input": req.text}

        if req.respond_with_audio:
            tts_resp = await client.post(f"{TTS_URL}/synthesize", json={"text": answer})
            import base64
            result["audio_base64"] = base64.b64encode(tts_resp.content).decode()

    return result
```

Crea `requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
pydantic>=2.0
python-multipart>=0.0.9
```

Crea `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## PASO 7 — DOCKER-COMPOSE RAÍZ

Crea `/opt/robita-lab/docker-compose.yml`:

```yaml
version: "3.9"

services:

  # ── LLM Engine (Ollama) ──────────────────────────────────────────────
  ollama:
    image: ollama/ollama:latest
    container_name: robita-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=2
    # Si tienes GPU NVIDIA descomenta:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

  # ── STT Engine ──────────────────────────────────────────────────────
  stt-engine:
    build: ./01_SERVICES/stt-engine
    container_name: robita-stt
    restart: unless-stopped
    ports:
      - "8001:8001"
    environment:
      - WHISPER_MODEL=${WHISPER_MODEL:-small}
    volumes:
      - whisper_cache:/root/.cache/whisper

  # ── TTS Engine ──────────────────────────────────────────────────────
  tts-engine:
    build: ./01_SERVICES/tts-engine
    container_name: robita-tts
    restart: unless-stopped
    ports:
      - "8002:8002"
    environment:
      - PIPER_MODEL=/models/es_ES-davefx-medium.onnx
    volumes:
      - piper_models:/models

  # ── Wakeword Engine ─────────────────────────────────────────────────
  wakeword-engine:
    build: ./01_SERVICES/wakeword-engine
    container_name: robita-wakeword
    restart: unless-stopped
    ports:
      - "8003:8003"
    environment:
      - WAKEWORD_ENGINE=openwakeword

  # ── RAG Engine ──────────────────────────────────────────────────────
  rag-engine:
    build: ./01_SERVICES/rag-engine
    container_name: robita-rag
    restart: unless-stopped
    ports:
      - "8004:8004"
    environment:
      - OLLAMA_URL=http://ollama:11434
      - OLLAMA_MODEL=${OLLAMA_MODEL:-mistral:7b-instruct-q4_K_M}
      - CHROMA_PATH=/data/chromadb
      - EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
    volumes:
      - chromadb_data:/data/chromadb
      - ./04_KNOWLEDGE_CORE/raw-docs:/data/raw-docs:ro
    depends_on:
      - ollama

  # ── Pipeline Orchestrator (entrada principal) ────────────────────────
  pipeline-orchestrator:
    build: ./01_SERVICES/pipeline-orchestrator
    container_name: robita-orchestrator
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - STT_URL=http://stt-engine:8001
      - TTS_URL=http://tts-engine:8002
      - WW_URL=http://wakeword-engine:8003
      - RAG_URL=http://rag-engine:8004
    depends_on:
      - stt-engine
      - tts-engine
      - wakeword-engine
      - rag-engine

volumes:
  ollama_models:
  whisper_cache:
  piper_models:
  chromadb_data:

networks:
  default:
    name: robita-net
```

---

## PASO 8 — ARCHIVO .env RAÍZ

Crea `/opt/robita-lab/.env`:

```env
# LLM
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M

# STT
WHISPER_MODEL=small

# Jetson edge (referencia, no usado en server)
EDGE_MODEL=tinyllama
```

---

## PASO 9 — PRIMER ARRANQUE Y DESCARGA DEL MODELO

Después de generar todos los archivos ejecuta en terminal:

```bash
cd /opt/robita-lab

# 1. Construir todas las imágenes
docker-compose build

# 2. Levantar todo
docker-compose up -d

# 3. Descargar el modelo LLM (solo la primera vez, tarda varios minutos)
docker exec robita-ollama ollama pull mistral:7b-instruct-q4_K_M

# 4. Verificar que todos los servicios están vivos
curl http://localhost:8000/services/status

# 5. Test rápido de texto
curl -X POST http://localhost:8000/text-query \
  -H "Content-Type: application/json" \
  -d '{"text": "¿Cuáles son los plazos de matrícula?", "collection": "admisiones"}'
```

---

## PASO 10 — VERIFICACIÓN FINAL

Confirma que estos endpoints responden con status 200:

| Servicio         | URL                                          |
|------------------|----------------------------------------------|
| Orquestador      | `GET  http://localhost:8000/health`          |
| Estado completo  | `GET  http://localhost:8000/services/status` |
| STT              | `GET  http://localhost:8001/health`          |
| TTS              | `GET  http://localhost:8002/health`          |
| Wakeword         | `GET  http://localhost:8003/health`          |
| RAG              | `GET  http://localhost:8004/health`          |
| RAG colecciones  | `GET  http://localhost:8004/collections`     |
| Docs API         | `GET  http://localhost:8000/docs`            |

Si algún servicio falla, lee sus logs con:
```bash
docker-compose logs <nombre-servicio> --tail=50
```

---

## NOTAS IMPORTANTES PARA CURSOR

- **No borres archivos existentes** sin hacer backup `.bak` primero
- Si un archivo existente ya implementa correctamente una función (ej: transcripción con Whisper), **reutiliza esa lógica** dentro del `main.py` del servicio correspondiente — no la reescribas
- El archivo `main.py` de cada servicio debe ser el **único punto de entrada** de la API; el código legacy va en módulos auxiliares dentro de la misma carpeta
- Si encuentras código de wakeword que depende de audio en tiempo real del micrófono local, **adáptalo** para recibir audio por HTTP/WebSocket en lugar de capturarlo directamente
- Los puertos **8000–8004 no deben estar ocupados**; verifica con `ss -tlnp | grep -E '800[0-4]'` antes de levantar
