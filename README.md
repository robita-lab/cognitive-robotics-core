# ROBITA-LAB — Cognitive Robotics Core

Plataforma del laboratorio **Robita-Lab** (UDIT) para agentes cognitivos en robótica social: RAG, LLMs locales, voz y adaptadores hardware.

Repositorio: [github.com/robita-lab/cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core)

Ruta de trabajo habitual en servidor: `/opt/robita-lab`

---

## Producto UDITO (robot de voz)

Asistente tipo Alexa/Siri para el autómata social **UDITO**: wakeword «udito» → saludo → pregunta por voz → respuesta hablada. **No es una web app.**

| Modo | Script | Descripción |
|------|--------|-------------|
| **Cerebro virtual** | `./scripts/launch.sh` o `./scripts/udito_virtual.sh` | STT + TTS + RAG + orquestador (puertos 8000–8004) |
| **Robot físico** | `./scripts/udito.sh` | Wakeword y mic en el cuerpo; cerebro por red (`ROBITA_SERVER_URL`) |
| **Todo en un PC** | `./scripts/udito_standalone.sh` | Wakeword + STT + RAG + TTS locales (sin Docker) |

Guía de despliegue Jetson/servidor: [`DEPLOY_UDITO.md`](DEPLOY_UDITO.md)

---

## Arquitectura de carpetas

### `01_SERVICES/` — Motores de IA

| Servicio | Puerto | Rol |
|----------|--------|-----|
| `pipeline-orchestrator` | 8000 | STT → RAG / despedida → TTS (`/voice-query`) |
| `stt-engine` | 8001 | Whisper (faster-whisper) |
| `tts-engine` | 8002 | Piper (es_ES-sharvard-medium) |
| `wakeword-engine` | 8003 | Detector «udito» (TFLite) |
| `rag-engine` | 8004 | FAISS + TinyLlama + Q&A fijo |

### `02_AGENTS_FACTORY/` — Perfil del agente

- `udit-robot-brain/`: personalidad, `config.yaml` y rutas al knowledge core.
- El **saludo inicial** lo define el agente / `04_KNOWLEDGE_CORE/responses/agent.json`.

### `03_ADAPTERS/robot-udit-physical/` — Cuerpo del robot

- `udito.py` — robot físico (edge).
- `udito_standalone.py` — modo monolítico local.
- `robot_common.py` — bucle wakeword, VAD, audio compartido.

### `04_KNOWLEDGE_CORE/` — Conocimiento y textos hablados

```
04_KNOWLEDGE_CORE/
├── raw-docs/              # PDFs y TXT para RAG documental
├── responses/
│   ├── agent.json         # Saludo tras wakeword
│   ├── conversation.json  # Despedida, avisos, goodbye_keywords
│   └── qa.json            # Preguntas fijas (identidad, sedes…)
└── load_responses.py      # Cargador único de textos
```

Variable de entorno: `ROBITA_KNOWLEDGE_CORE` (por defecto `04_KNOWLEDGE_CORE`).

---

## Inicio rápido

```bash
cd /opt/robita-lab
cp .env.example .env          # editar audio y URL del cerebro
./scripts/setup-venv.sh         # primera vez
./scripts/launch.sh             # cerebro en :8000
./scripts/udito.sh              # robot (otra terminal)
```

Parar cerebro: `./scripts/stop.sh`

Probar solo texto:

```bash
curl -X POST http://127.0.0.1:8000/text-query \
  -H "Content-Type: application/json" \
  -d '{"text":"¿Quién eres?"}'
```

---

## Variables de entorno (`.env`)

| Variable | Uso |
|----------|-----|
| `ROBITA_SERVER_URL` | URL del orquestador (robot físico) |
| `ROBITA_KNOWLEDGE_CORE` | Ruta al knowledge core |
| `ROBITA_AUDIO_INPUT` | Índice micrófono (sounddevice) |
| `ROBITA_AUDIO_OUTPUT` | Dispositivo ALSA (`default`, `plughw:X,Y`) |
| `WHISPER_MODEL` | Modelo STT (`small`, etc.) |

---

## Git y GitHub

```bash
git status
GITHUB_TOKEN=ghp_xxx ./scripts/push-github.sh
```

No commitear: `.env`, `.venv/`, `logs/`, cachés RAG (`data/rag_cache/`, `data/memory/`).

---

## Filosofía de trabajo

1. Desarrollo en ramas `feature/` (ver `GIT-FLOW.md` si existe).
2. Validación en este servidor (integración real entre servicios).
3. `push` a GitHub cuando esté estable.
4. Jetson / robots hacen `git pull` o usan imágenes Docker verificadas.

---

## Documentación adicional

- [`DEPLOY_UDITO.md`](DEPLOY_UDITO.md) — servidor, Jetson, GitHub
- [`03_ADAPTERS/robot-udit-physical/README.md`](03_ADAPTERS/robot-udit-physical/README.md) — adaptador físico
- [`CURSOR_AGENT_PROMPT.md`](CURSOR_AGENT_PROMPT.md) — contexto para desarrollo con agentes
