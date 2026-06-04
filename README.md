# ROBITA-LAB — Cognitive Robotics Core

Plataforma del laboratorio **Robita-Lab** (UDIT) para agentes cognitivos en robótica social: RAG, voz local, wakeword y adaptadores hardware.

**Repositorio:** [github.com/robita-lab/cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core)

**Ruta habitual en Jetson/servidor:** `/opt/robita-lab`

---

## Ramas del repositorio

| Rama | Para qué sirve |
|------|----------------|
| **`develop`** | **Rama de trabajo** — UDITO offline en Jetson, `Principal-UDITO.sh`, ROS2, pantalla sim, conocimiento en `knowledge-text/`. |
| **`main`** | Releases / servidor histórico (Docker, cerebro remoto). |

**Clonar para Jetson / UDITO físico:**

```bash
git clone -b develop https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
cd /opt/robita-lab
```

```bash
cd /opt/robita-lab
git fetch origin
git checkout develop
git pull origin develop
```

---

## Producto UDITO (robot de voz)

Asistente por voz tipo Alexa/Siri para el autómata **UDITO**: «udito» → «¿Dime?» → pregunta → respuesta hablada.

| Uso | Comando |
|-----|---------|
| **Arrancar UDITO (Jetson)** | `./UDITO` o `./scripts/Principal-UDITO.sh` |
| Pantalla ojos (opcional) | `./scripts/udito-face-sim.sh` |
| Configurar mic/altavoz | `./scripts/find-speaker.sh` |

Menú de pruebas, modo online, servidor Docker: ver tabla en [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md). No hace falta invocar `udito_standalone.sh` ni otros `.sh` sueltos.

Guía Jetson offline: [DEPLOY_JETSON_OFFLINE.md](DEPLOY_JETSON_OFFLINE.md) · ROS2: [05_ROS2/README.md](05_ROS2/README.md)

---

## Inicio rápido (Jetson — rama `develop`)

```bash
cd /opt/robita-lab
cp .env.example .env          # editar audio (respeaker, pulse, etc.)
./scripts/setup-jetson-offline.sh
./scripts/download-offline-models.sh   # primera vez con internet (~2.7 GB en data/huggingface)
./scripts/Principal-UDITO.sh         # o: ./UDITO — di «udito»
```

**Consola:** `ROBITA_VERBOSE=0` (limpio) o `1` (log Hugging Face, RAG, etc.) en `.env`.

**Audio:** `./scripts/find-speaker.sh` — menú para micrófono y altavoz.

**Piper TTS:** los binarios en `01_SERVICES/tts-engine/piper/` son para **Jetson (aarch64)** — [piper/README.md](01_SERVICES/tts-engine/piper/README.md).

---

## Inicio rápido (servidor con Docker)

```bash
cd /opt/robita-lab
cp .env.example .env
./scripts/setup-venv.sh
./scripts/launch.sh
```

---

## Arquitectura

| Carpeta | Contenido |
|---------|-----------|
| `01_SERVICES/` | STT (Whisper), TTS (Piper), wakeword, RAG, orquestador |
| `02_AGENTS_FACTORY/` | Perfil `udit-robot-brain` |
| `03_ADAPTERS/robot-udit-physical/` | `udito_standalone.py`, `robot_common.py`, `log_config.py` |
| `04_KNOWLEDGE_CORE/` | Textos fijos + PDFs RAG — ver [04_KNOWLEDGE_CORE/README.md](04_KNOWLEDGE_CORE/README.md) |

Estructura detallada: [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md)

---

## Variables de entorno

Copiar `.env.example` → `.env`. Las más usadas en Jetson:

| Variable | Uso |
|----------|-----|
| `ROBITA_AUDIO_INPUT` | `respeaker` o índice ALSA |
| `ROBITA_AUDIO_OUTPUT` | `pulse`, `hdmi`, `platform` |
| `ROBITA_VERBOSE` | `0` consola limpia, `1` log completo |
| `ROBITA_RELEASE_MODELS` | `0` = Whisper en RAM (más rápido) |
| `ROBITA_RAG_REBUILD` | `1` una vez tras añadir PDFs |
| `HF_HOME` | Caché modelos (`data/huggingface`, no en git) |
| `WHISPER_MODEL` | `tiny` en 8 GB; `small` si hay RAM |

---

## Subir cambios a GitHub

Rama de trabajo: **`develop`**.

```bash
cd /opt/robita-lab
git checkout develop
GITHUB_TOKEN=ghp_xxx ./scripts/push-github.sh "feat: descripción del cambio"
```

(`push-github.sh` sube a `develop` por defecto; override: `ROBITA_GIT_BRANCH=otra`.)

El commit debe figurar con tu usuario Git (`git config user.name` / `user.email` en este repo).

No commitear: `.env`, `.venv/`, `data/huggingface/`, cachés RAG.

---

## Filosofía

1. Trabajar en rama **`develop`** (o `feature/…` derivada) para el robot físico UDITO.
2. Validar en hardware real (ReSpeaker + Jetson Orin) con **`./scripts/Principal-UDITO.sh`**.
3. Push a [cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core) en `develop`.
4. Otras Jetsons: `git pull origin develop` + `./scripts/setup-jetson-offline.sh` si hace falta.
