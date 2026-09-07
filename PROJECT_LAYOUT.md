# Estructura del proyecto (rama `develop` — Jetson offline)

```
/opt/robita-lab/
├── 01_SERVICES/          # wakeword, STT, TTS, RAG (librerías locales)
├── 03_ADAPTERS/robot-udit-physical/   # udito_standalone.py, robot_common.py
├── 04_KNOWLEDGE_CORE/    # textos + PDFs RAG
├── 05_ROS2/              # topics wakeword + voz
├── scripts/              # ver scripts/README.md
├── UDITO                   # atajo → scripts/udito/start.sh
├── data/huggingface/     # modelos (no en git)
├── logs/
├── DEPLOY_JETSON_OFFLINE.md
└── _archive/             # historial + modo online retirado
```

## Ramas

| Rama | Contenido |
|------|-----------|
| **`develop`** | Trabajo activo — **solo offline** en Jetson |
| **`develop-base`** | Referencia histórica; incluye `_archive/` con modo servidor |
| **`main`** | Releases antiguos |

Modo online (Docker, cerebro remoto, `udito.py` edge): [`_archive/modo-online/`](_archive/modo-online/README.md)

---

## Comandos

| Comando | Uso |
|---------|-----|
| **`./UDITO`** | Arrancar robot offline |
| `./scripts/setup/jetson.sh` | Primera instalación |
| `./scripts/setup/models-download.sh` | Whisper + RAG |
| `./scripts/udito/audio-config.sh` | Micrófono y altavoz |
| `./scripts/udito/face-sim.sh` | Pantalla ojos (opcional) |
| `./scripts/ros2/listener-wakeword.sh` | ROS2 (opcional) |
| `./scripts/dev/sync-jetson.sh` | PC → Jetson |

Índice completo: [scripts/README.md](scripts/README.md)
