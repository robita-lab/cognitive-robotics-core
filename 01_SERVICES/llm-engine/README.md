# llm-engine — LLM conversacional de UDITO

Servicio HTTP (FastAPI) que da a UDITO conversación con un LLM local: modelo
servido por **Ollama** (API compatible OpenAI), memoria de conversación por
`conversation_id` (Redis o en memoria) y respuesta normal o en streaming (SSE).

Es **opcional**: el pipeline offline de la Jetson (`./UDITO`) funciona igual sin él.
Diseño completo, latencias y decisiones: [ARCHITECTURE.md](ARCHITECTURE.md).

## Dónde encaja (arquitectura por capas v2)

Capa **Cognitive** (LLM + memoria corta). Nunca da órdenes a actuadores: la
respuesta vuelve por la capa C.C. Lo usan:

- **Pipeline offline** — `03_ADAPTERS/robot-udit-physical/llm_fallback.py`.
  Solo si `ROBITA_LLM_URL` está definida y solo para preguntas generales
  (fuente RAG `gpt`). Las preguntas de la universidad siguen en `rag-engine`.
- **ROS 2** — paquete `05_ROS2/ros2_ws/src/llm_dialog_manager`
  (`stt_topic` → router → `/v1/chat` → `com_act_server`).

## Arranque rápido

```bash
cd 01_SERVICES/llm-engine
cp .env.example .env

# Servidor con GPU NVIDIA (modelo qwen3:4b-instruct-2507-q4_K_M + Redis; necesita nvidia-container-toolkit)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
# PC sin GPU (mismo modelo en CPU: lento, solo para desarrollo)
docker compose up --build -d
# Jetson / CPU (modelo 0.5B, sin Redis)
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build -d

# Primera vez: descargar el modelo en Ollama
docker compose exec ollama ollama pull qwen3:4b-instruct-2507-q4_K_M      # o qwen2.5:0.5b-instruct en CPU/Jetson

curl http://localhost:8080/readyz
curl -s http://localhost:8080/v1/chat -H 'Content-Type: application/json' \
  -d '{"conversation_id":"prueba","user_text":"Hola UDITO, ¿qué tal?"}'
```

Conectar UDITO: en el `.env` de la raíz, `ROBITA_LLM_URL=http://<host>:8080`.
Si corre en la propia Jetson, pon además `ROBITA_STOP_OLLAMA=0` y
`ROBITA_STOP_DOCKER=0`, o `prepare-pipeline.sh` lo detendrá al arrancar.

## API

| Método | Ruta | Uso |
|---|---|---|
| GET | `/healthz`, `/readyz` | Vivo / modelo cargado + Redis accesible |
| GET | `/v1/models` | Modelos que sirve Ollama |
| POST | `/v1/chat` | `{conversation_id, user_text, max_tokens?}` → `{reply, model, tier}` |
| POST | `/v1/chat/stream` | Igual, en SSE (`token` … `done`) |
| GET / DELETE | `/v1/conversations/{id}` | Ver / borrar la memoria de una conversación |
| POST | **`/v2/turn`** | Turno **sin estado** para `cognitive_language` (ver abajo). Requiere clave de API |

`/v1` se mantiene para `./UDITO` (`llm_fallback.py`); guarda la memoria en el
servidor. Lo nuevo va por `/v2`.

### `/v2/turn` (D5: la memoria vive en el robot)

```json
{"session_id": "s1", "turn_id": "t7", "user_text": "¿Tengo que traducir mis documentos?",
 "history": [{"role": "user", "content": "Hola"}, {"role": "assistant", "content": "¡Hola!"}],
 "context": [{"source": "normativa:ACC:7", "title": "Normativa de acceso…, artículo 7", "text": "…"}],
 "max_tokens": 120, "stream": true}
```

- El servidor **no guarda nada**: el robot manda el historial en cada turno.
- Con `context` (fragmentos que encontró la búsqueda local del robot), el LLM
  responde **solo** con esa información; sin él, conversación general sin
  inventar datos de UDIT. Prompts en `app/llm/prompts.py`.
- `stream: true` → SSE: `token` (texto), `done` (`{text, model, latency_ms, finish}`) o `error`.
  `stream: false` → JSON `{text, model, latency_ms, finish}`.
- **Cancelación:** si el robot cierra la conexión, se aborta la petición a
  Ollama y se registra `cancelado por el cliente … generación abortada`.
- **Clave:** `Authorization: Bearer <clave>` o `X-API-Key`. Claves en
  `LLM_API_KEYS` (separadas por comas). Vacía = sin clave, solo para
  desarrollo (el arranque lo avisa). El robot la recibe en `COGNITIVE_LLM_API_KEY`.
- Límites: `TURN_MAX_HISTORY` (16 mensajes), `TURN_MAX_CONTEXT_CHARS` (6000), `TURN_MAX_TOKENS_CAP` (400).

Configuración por variables de entorno: ver `.env.example` y ARCHITECTURE.md §7.3.

## Tests

```bash
uv sync && uv run pytest
```
