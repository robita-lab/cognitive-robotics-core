# ROBITA-LAB — Cognitive Robotics Core

Plataforma del laboratorio **Robita-Lab** (UDIT) para agentes cognitivos en robótica social: RAG, voz local, wakeword y adaptadores hardware.

**Repositorio:** [github.com/robita-lab/cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core)

**Ruta habitual en Jetson/servidor:** `/opt/robita-lab`

---

## Ramas del repositorio

En GitHub hay dos ramas con propósitos distintos. **No uses `main` por defecto** si vas a desplegar UDITO en un robot físico.

| Rama | Estado | Para qué sirve |
|------|--------|----------------|
| **`jetson-udito-offline`** | **Más actualizada** — recomendada | Robot social físico **UDITO** en Jetson Orin: wakeword, STT, RAG y TTS **todo local**, sin cerebro remoto. Incluye `start-udito-visible.sh`, `find-speaker.sh`, conocimiento estructurado (`knowledge-text/`), consola limpia y guía [DEPLOY_JETSON_OFFLINE.md](DEPLOY_JETSON_OFFLINE.md). |
| **`main`** | Histórico / instalación antigua | Scripts Docker y `install_in_jetson.sh` de versiones anteriores. **No** incluye el pipeline offline actual ni los scripts de arranque visibles de UDITO. |

**Clonar la rama correcta (Jetson / UDITO físico):**

```bash
git clone -b jetson-udito-offline https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
cd /opt/robita-lab
```

Si ya tienes el repo y estabas en `main`:

```bash
cd /opt/robita-lab
git fetch origin
git checkout jetson-udito-offline
git pull origin jetson-udito-offline
```

Cuando el equipo valide en hardware, se puede fusionar `jetson-udito-offline` → `main` con un pull request en GitHub.

---

## Producto UDITO (robot de voz)

Asistente por voz tipo Alexa/Siri para el autómata **UDITO**: «udito» → «¿Dime?» → pregunta → respuesta hablada.

| Modo | Script | Descripción |
|------|--------|-------------|
| **Jetson offline** | `./scripts/start-udito-visible.sh` o `./scripts/udito-run.sh` | Todo local en Orin (~8 GB). Ver [DEPLOY_JETSON_OFFLINE.md](DEPLOY_JETSON_OFFLINE.md) |
| Cerebro virtual | `./scripts/launch.sh` | STT + TTS + RAG + orquestador (`:8000–8004`) |
| Robot físico + cerebro | `./scripts/udito.sh` | Mic en el robot; IA por `ROBITA_SERVER_URL` |
| Un solo PC | `./scripts/udito_standalone.sh` | Wakeword + STT + RAG + TTS sin Docker |

Guía de despliegue en robot físico (rama `jetson-udito-offline`): [DEPLOY_JETSON_OFFLINE.md](DEPLOY_JETSON_OFFLINE.md)

---

## Inicio rápido (Jetson — rama `jetson-udito-offline`)

```bash
cd /opt/robita-lab   # debe estar en la rama jetson-udito-offline (ver arriba)
cp .env.example .env          # editar audio (respeaker, pulse, etc.)
./scripts/setup-jetson-offline.sh
./scripts/download-offline-models.sh   # primera vez con internet (~2.7 GB en data/huggingface)
./scripts/start-udito-visible.sh       # consola limpia; di «udito»
```

**Consola:** `ROBITA_VERBOSE=0` (limpio) o `1` (log Hugging Face, RAG, etc.) en `.env`.

**Audio:** `./scripts/find-speaker.sh` — menú para micrófono y altavoz.

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

Los cambios de UDITO offline se suben a la rama **`jetson-udito-offline`** (no a `main` hasta fusionar por PR).

```bash
cd /opt/robita-lab
git checkout jetson-udito-offline
GITHUB_TOKEN=ghp_xxx ./scripts/push-github.sh "feat: descripción del cambio"
```

El commit debe figurar con tu usuario Git (`git config user.name` / `user.email` en este repo).

No commitear: `.env`, `.venv/`, `data/huggingface/`, cachés RAG.

---

## Filosofía

1. Trabajar en rama **`jetson-udito-offline`** (o `feature/…` derivada de ella) para el robot físico UDITO.
2. Validar en hardware real (ReSpeaker + Jetson Orin).
3. Push a [cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core) en esa rama.
4. Otros equipos en Jetson: `git pull origin jetson-udito-offline` + `./scripts/setup-jetson-offline.sh` si hace falta.
