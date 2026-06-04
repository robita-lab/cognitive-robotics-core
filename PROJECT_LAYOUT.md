# Estructura del proyecto (activo)

```
/opt/robita-lab/
├── 01_SERVICES/          # Motores: STT, TTS, wakeword (OWW en Jetson), RAG, orquestador
├── 02_AGENTS_FACTORY/    # Perfil udit-robot-brain
├── 03_ADAPTERS/          # udito.py, udito_standalone.py, robot_common.py
├── 04_KNOWLEDGE_CORE/    # knowledge-text/ + responses/ + raw-docs/ (ver README ahí)
├── data/huggingface/     # Modelos descargados (no versionar)
├── logs/                 # Logs en ejecución (vacío tras limpieza)
├── scripts/              # Arranque y utilidades
├── UDITO                   # Atajo → scripts/Principal-UDITO.sh
├── .env                  # Config local (no subir a git)
├── README.md
├── 05_ROS2/              # ROS2 + docs pantalla
├── DEPLOY_JETSON_OFFLINE.md
└── _archive/             # Historial / archivos retirados (no ejecutar)
```

## Scripts — orden de uso (pocos, el resto es interno)

### Usar UDITO (Jetson offline)

| Comando | Qué hace |
|---------|----------|
| **`./UDITO`** o **`./scripts/Principal-UDITO.sh`** | **Único arranque habitual** — wakeword, STT, RAG, TTS, log |
| `./scripts/udito-face-sim.sh` | Pantalla de ojos (segunda terminal, opcional) |

No hace falta llamar a mano: `udito_standalone.sh`, `start-udito-visible.sh` (alias al principal), ni scripts sueltos de prueba.

### Configurar una vez

| Script | Qué hace |
|--------|----------|
| `setup-jetson-offline.sh` | Primera instalación |
| `find-speaker.sh` | Mic / altavoz → `.env` (incl. ReSpeaker `respeaker.asr`) |
| `download-offline-models.sh` | Modelos Whisper/RAG |

### Avanzado (solo si lo necesitas)

| Script | Qué hace |
|--------|----------|
| `Menu_Udito.sh` | Menú de pruebas (opción 1 = mismo que `./UDITO`) |
| `udito-run.sh` | Online u offline (offline → Principal-UDITO) |
| `prepare-pipeline.sh` | Limpieza RAM (ya lo llama el principal; `ROBITA_SKIP_PREPARE=1` para saltar) |

### Servidor / Docker (modo online, otra máquina)

`launch.sh`, `stop.sh`, `udito.sh`, `start-services.sh`, `udito_virtual.sh`, `watch-robot.sh`, `status-robot.sh`

### Internos (no ejecutar directo)

`udito_standalone.sh`, `jetson-env.sh`, `choose-udito-mode.sh`, `install-*.sh`, `fetch-*.sh`, `test-*.sh`, `find-speaker-interactive.sh` (alternativa a `find-speaker.sh`)
