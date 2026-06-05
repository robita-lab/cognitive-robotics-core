# ROBITA-LAB — Cognitive Robotics Core

Plataforma **Robita-Lab** (UDIT): robot de voz **UDITO** offline en Jetson (wakeword + STT + RAG + TTS local).

**Repositorio:** [github.com/robita-lab/cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core)

**Ruta en Jetson:** `/opt/robita-lab`

---

## Ramas

| Rama | Para qué |
|------|----------|
| **`develop`** | **Trabajo activo** — solo Jetson **offline** |
| **`develop-base`** | Referencia + `_archive/` (modo servidor conservado) |
| **`main`** | Releases antiguos |

Modo online / Docker archivado: [`_archive/modo-online/`](_archive/modo-online/README.md)

---

## UDITO — arranque

```bash
cd /opt/robita-lab
cp .env.example .env
./scripts/setup/jetson.sh              # una vez
./scripts/setup/models-download.sh     # una vez (~2.7 GB)
./UDITO                                # di «udito»
```

| Comando | Uso |
|---------|-----|
| **`./UDITO`** | Robot offline (principal) |
| `./scripts/udito/audio-config.sh` | Micrófono y altavoz |
| `./scripts/udito/face-sim.sh` | Cara (2ª terminal) |
| `./scripts/ros2/listener-wakeword.sh` | ROS2 (2ª terminal) |

Guía completa: [DEPLOY_JETSON_OFFLINE.md](DEPLOY_JETSON_OFFLINE.md) · ROS2: [05_ROS2/README.md](05_ROS2/README.md) · Scripts: [scripts/README.md](scripts/README.md)

---

## Arquitectura (offline)

| Carpeta | Contenido |
|---------|-----------|
| `01_SERVICES/` | wakeword, STT, TTS, RAG |
| `03_ADAPTERS/robot-udit-physical/` | `udito_standalone.py`, bucle wakeword |
| `04_KNOWLEDGE_CORE/` | Saludos, Q&A, PDFs |
| `05_ROS2/` | Topics `/udito/wakeword`, `/udito/speech_out` |
| `scripts/` | Arranque e instalación |

Detalle: [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md)

---

## Variables `.env` (Jetson)

| Variable | Uso |
|----------|-----|
| `ROBITA_AUDIO_INPUT` | `respeaker` o índice ALSA |
| `ROBITA_AUDIO_OUTPUT` | `pulse`, `hdmi`, `platform` |
| `ROBITA_VERBOSE` | `0` limpio, `1` log completo |
| `ROBITA_RAG_CONFIG` | `rag_config.jetson.json` |
| `HF_HOME` | `data/huggingface` |

---

## Git

Trabajar en **`develop`**. Push manual o script archivado en `_archive/modo-online/scripts/dev/push-github.sh`.

No commitear: `.env`, `.venv/`, `data/huggingface/`, modelos wakeword entrenados.
