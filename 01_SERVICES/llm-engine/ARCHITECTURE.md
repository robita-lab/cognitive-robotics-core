# UDITO — Server-Side LLM Architecture

**Component:** `udito/server-side/`
**Feature branch:** `feature/llm-server-side`
**Status:** Slice 1 scaffold landing in this branch. Slices 2 and 3 follow.

---

## 1. What this component does

Exposes UDITO's dialogue generation as a **network-callable service**, so that:

- API keys and provider credentials live off the robot, not in source code.
- The underlying model/provider can be swapped without touching robot code.
- Conversation memory is centralised.
- Future consumers (dashboards, evaluation harnesses) share one endpoint.

The service wraps an **OpenAI-compatible** inference backend (Ollama by default), maintains per-conversation memory in **Redis**, and streams tokens back over **SSE** so the robot's TTS can start speaking on the first sentence boundary rather than on the last token.

---

## 2. Deployment — two-tier

This is **not** a single-box deployment. UDITO runs in two cooperating tiers:

```
┌───────────────────────────────────────┐             ┌───────────────────────────────────────┐
│  TIER 1 — on-robot (local)            │             │  TIER 2 — GPU workstation (server)    │
│                                       │    LAN      │                                       │
│  ROS: llm_dialog_manager              │◀──────────▶ │  Docker stack:                        │
│    │                                  │    SSE/HTTP │    - udito-llm-api (FastAPI)          │
│    ├─ router (intent classifier)      │             │    - ollama (qwen2.5:3b-instruct)     │
│    │    ├─▶ local tier (localhost)    │             │    - redis (conversation memory)      │
│    │    └─▶ server tier (LAN)         │             │    - qdrant   (Slice 3, optional)     │
│    │                                  │             │                                       │
│  Docker stack (same code as server):  │             │  Profile: full, GPU-accelerated       │
│    - udito-llm-api (FastAPI)          │             └───────────────────────────────────────┘
│    - ollama (qwen2.5:0.5b or 1.5b)    │
│                                       │
│  Profile: lite, CPU-only, stateless   │
└───────────────────────────────────────┘
```

**Key properties of the split:**

- **Same codebase, two profiles.** The FastAPI app is one artefact; deployment differs only in Docker Compose overlay and env.
- **Local tier is stateless** for v1 — no Redis, no persistent memory. It handles short, context-free chit-chat. Its job is speed, not depth.
- **Server tier owns conversation memory** (Redis) and heavier reasoning.
- **Routing decision lives in the robot** (`llm_dialog_manager` ROS node), not in the API. Neither tier knows about the other.

### 2.1 How the robot decides which tier to call

For Slice 1, the router is a simple **regex/keyword intent classifier** running in the ROS node. Cost: <1 ms per turn.

| Intent | Example utterances | Route |
|---|---|---|
| `greeting` | "hola", "buenos días", "hasta luego" | **local** |
| `acknowledgement` | "sí", "vale", "gracias" | **local** |
| `backchannel` | "mm", "ya", "ajá" | **local** |
| `emotion_expression` | "estoy triste", "me aburro" | **local** |
| `factual_query` | "qué", "quién", "cuándo", "cómo funciona…" | **server** |
| `multi_turn_continuation` | anything after a factual_query, anything longer than N tokens | **server** |
| `unknown` | everything else | **server** (safer default) |

v2 replaces regex with a tiny intent classifier (scikit-learn or a 0.3B model) once we have transcripts to train on.

### 2.2 Memory across tiers

Local tier does not persist memory in v1. The router sends, along with any server request, a compact "recent context" field (last K turns that happened locally) so the server tier has continuity if the conversation escalated. Server tier then stores the full trajectory in Redis keyed by `conversation_id`.

Slice 2 may introduce a tiny local Redis for short-term context if this proves insufficient. For v1 we punt on it.

---

## 3. Latency budget

A conversational turn, end-to-end:

```
user stops speaking ──▶ STT ──▶ router ──▶ LLM ──▶ TTS ──▶ first audio
```

| Stage | Typical |
|---|---|
| STT (Whisper base, CPU) | 200–500 ms |
| Router (regex) | <1 ms |
| **LLM (target TTFT, local tier, 0.5B CPU)** | **80–150 ms** |
| **LLM (target TTFT, server tier, 3B GPU)** | **150–300 ms** |
| LAN round trip (server only) | 1–5 ms |
| TTS (Coqui vits, first chunk) | ~500 ms |
| **Total to first speech (local)** | **~800 ms–1.1 s** |
| **Total to first speech (server)** | **~1.0–1.3 s** |

Current Watson-based flow sits at ~1.5–2 s, depending on the network to IBM. So the split gains ~300–500 ms on routine turns *and* removes the IBM outage dependency entirely.

**Implication:** streaming (SSE) is mandatory, not optional. We build it from day one server-side; the robot client starts consuming non-streaming, then upgrades.

---

## 4. Inference backend choice

Locked for v1: **Ollama** on both tiers, behind an **OpenAI-compatible HTTP client** inside the FastAPI app.

Why this shape:
- Ollama wraps `llama.cpp`, so we get its speed without the build complexity.
- OpenAI-compatible API means we can point the FastAPI client at **llama.cpp-server, vLLM, or TGI** by changing one env var (`LLM_BASE_URL`). No code change.
- Model swap is `ollama pull <model>` + env var — no container rebuild.

Model selection:

| Tier | Model | Quantization | Why |
|---|---|---|---|
| Local (on-robot) | `qwen2.5:0.5b-instruct` (start) → `qwen2.5:1.5b-instruct` (if CPU allows) | Q4_K_M | Strong Spanish, tiny footprint, 100 ms-ish TTFT on CPU |
| Server (GPU) | **`qwen2.5:3b-instruct`** | Q4_K_M | Primary: strong Spanish, fits easily on any modern consumer GPU |

Fallbacks kept as overlays: `llama3.2:3b-instruct`, `phi3:mini`, `gemma2:2b`.

---

## 5. Memory strategy

**Slice 1 (this branch):** Redis-backed **rolling window** of the last N user+assistant turns. No summarisation. No RAG. Reads/writes keyed by `conversation_id`. TTL on conversation keys (configurable, default 24 h).

**Slice 2:** Add **periodic summarisation** of old turns (amortised one extra LLM call per ~10 turns) to keep the window useful across long sessions. Keep Redis for persistence. Make KV-cache reuse explicit on the Ollama side (`keep_alive`, persistent session).

**Slice 3:** Add **gated RAG**:
- Qdrant container alongside Redis.
- `bge-m3` embeddings (multilingual, Spanish-capable).
- Intent gate in the ROS router decides whether to request `?rag=on` on the endpoint.
- Factual-intent turns only — chit-chat stays fast.

---

## 6. Other latency levers (applied from v1)

1. **SSE streaming** — every `/v1/chat/stream` response starts flushing the moment the first token arrives from Ollama.
2. **Model warm-up on startup** — FastAPI lifespan event fires a 1-token dummy completion against Ollama so the first real user turn never pays cold-start cost.
3. **Short system prompt.** Persona templates live in `app/llm/prompts.py`. Kept tight.
4. **`max_tokens` cap.** Default 80 tokens per turn for TTS-coupled dialogue. Overridable per request.
5. **Aggressive stop tokens.** Stop on newline for single-utterance turns; otherwise on sentence boundaries.
6. **Async end-to-end.** FastAPI `async def`, `httpx.AsyncClient` for Ollama, async Redis client (`redis.asyncio`). Zero blocking.

Stacked on top of the backend choice, these should take server-tier TTFT well under 300 ms.

---

## 7. Slice 1 — what lands in this branch

### 7.1 API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness |
| GET | `/readyz` | Model warm + Redis reachable (if configured) |
| GET | `/v1/models` | What Ollama currently serves |
| POST | `/v1/chat` | Non-streaming — for debug / tests / non-streaming robot client |
| POST | `/v1/chat/stream` | **Primary:** SSE |
| GET | `/v1/conversations/{id}` | Fetch rolling window (debugging) |
| DELETE | `/v1/conversations/{id}` | Reset memory |

Request body (both chat endpoints):

```json
{
  "conversation_id": "udito-session-1234",
  "user_text": "Hola UDITO, ¿qué tal?",
  "persona": "default",
  "max_tokens": 80,
  "recent_context": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

`recent_context` is the **cross-tier continuity hook**: optional, used when the local tier escalates to server. Server tier merges it into the Redis-stored history for the given `conversation_id`.

Streaming response: SSE events of shape `{"type": "token", "value": "..."}`, terminated by `{"type": "done", "reply": "<full text>", "usage": {...}}`.

### 7.2 Repository layout (in this commit)

```
udito/server-side/
├── README.md                      # already committed
├── ARCHITECTURE.md                # this doc
├── pyproject.toml                 # uv-managed; deps pinned
├── .python-version                # 3.12
├── .env.example                   # all config documented
├── .gitignore
├── .dockerignore
├── Dockerfile                     # multi-stage, uv-based
├── docker-compose.yml             # server tier: api + ollama + redis
├── docker-compose.local.yml       # overlay: local tier (api + ollama only, no redis)
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + lifespan warm-up
│   ├── config.py                  # pydantic-settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py              # /healthz, /readyz
│   │   ├── chat.py                # /v1/chat, /v1/chat/stream
│   │   └── conversations.py       # GET/DELETE conversation memory
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # LLMClient protocol
│   │   ├── openai_compat.py       # single impl for Ollama / llama.cpp / vLLM
│   │   └── prompts.py             # persona templates
│   └── memory/
│       ├── __init__.py
│       └── store.py               # protocol + InMemoryStore + RedisStore
└── tests/
    ├── __init__.py
    ├── conftest.py                # fake LLM client, in-memory store
    ├── test_health.py
    └── test_chat.py               # mocked LLM, both endpoints
```

### 7.3 Configuration surface (env-driven, via `pydantic-settings`)

| Env var | Default | Purpose |
|---|---|---|
| `UDITO_TIER` | `server` | `server` \| `local`. Influences defaults below. |
| `LLM_BASE_URL` | `http://ollama:11434/v1` | OpenAI-compatible endpoint (Ollama / llama.cpp / vLLM). |
| `LLM_API_KEY` | `ollama` | Most local backends accept any string. |
| `LLM_MODEL` | `qwen2.5:3b-instruct` (server) / `qwen2.5:0.5b-instruct` (local) | Model tag. |
| `LLM_WARMUP_ON_START` | `true` | Fire a 1-token dummy completion on boot. |
| `LLM_MAX_TOKENS_DEFAULT` | `80` | Per-request cap if not overridden. |
| `REDIS_URL` | `redis://redis:6379/0` (server) / unset (local) | If unset → `InMemoryStore`. |
| `MEMORY_WINDOW_SIZE` | `8` | Turns kept in the rolling window. |
| `MEMORY_TTL_SECONDS` | `86400` | Conversation key TTL in Redis. |
| `CORS_ALLOW_ORIGINS` | `*` (v1) | Tighten before any public deploy. |
| `LOG_LEVEL` | `INFO` | |
| `API_PORT` | `8080` | |

### 7.4 Not in Slice 1 (explicit)

- Summarisation / long-context handling (Slice 2).
- Gated RAG, vector store, embeddings (Slice 3).
- Authentication / rate limiting.
- Metrics endpoint (can add Prometheus in Slice 2).
- The ROS-side `llm_dialog_manager` node — that's a separate change on the robot side, tracked in a follow-up branch.

---

## 8. Running it locally

```bash
# server tier (default)
cd udito/server-side
cp .env.example .env
docker compose up --build

# local tier (overlay swaps model + drops redis)
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

First boot pulls the Ollama model (~2 GB for the 3B, ~400 MB for the 0.5B). Subsequent boots are near-instant thanks to the `ollama-models` volume.

Tests (requires `uv`):

```bash
uv sync
uv run pytest
```

---

## 9. Open items for Slice 2+

- ROS router implementation + `llm_dialog_manager` node — depends on which ROS2 distro we commit to (see `docs/01-repo-analysis.md` §14).
- Summarisation strategy for the rolling window (manual prompt vs dedicated small model).
- Whether to add a tiny local Redis in the local tier.
- Evaluation harness (golden-set prompts, latency + quality metrics).
- CI (lint + tests on every PR).
