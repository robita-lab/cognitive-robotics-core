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
├── .env                  # Config local (no subir a git)
├── README.md
├── DEPLOY_JETSON_OFFLINE.md
└── _archive/             # Historial / archivos retirados (no ejecutar)
```

## Scripts principales

| Script | Uso |
|--------|-----|
| `udito-run.sh` | Pipeline con elección online/offline + preparación |
| `Menu_Udito.sh` | Menú de pruebas |
| `prepare-pipeline.sh` | Limpieza y liberar RAM (automático en udito-run) |
| `cleanup-project.sh` | Mover basura a `_archive/historial` |
| `setup-jetson-offline.sh` | Primera instalación Jetson |
| `setup-wakeword-oww.sh` | Modelos base openWakeWord + comprobar `udito.onnx` |
| `udito_standalone.sh` | Offline directo (sin menú de modo) |
| `start-udito-visible.sh` | Offline con log en terminal + tee a logs/ |
| `find-speaker.sh` | Menú micrófono / altavoz → .env |

## Servidor (modo online, misma rama)

`launch.sh`, `stop.sh`, `udito.sh`, `start-services.sh`, `udito_virtual.sh`, `watch-robot.sh`, `status-robot.sh`
