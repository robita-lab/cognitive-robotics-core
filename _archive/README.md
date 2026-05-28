# Archivo / historial — no usar en ejecución

Contenido **fuera del árbol activo** del proyecto. Se conserva por referencia o recuperación.

| Carpeta | Contenido |
|---------|-----------|
| `historial/scripts/` | Scripts sustituidos o solo servidor antiguo |
| `historial/logs/` | Logs de instalación viejos |
| `historial/piper/` | Binario Piper x86_64 (Jetson usa aarch64) |
| `historial/tts/` | `piper_tts.py` duplicado (activo: `piper_tts_real.py`) |
| `historial/raw-docs/` | PDF duplicado |
| `historial/rag-factory/` | Carpeta vacía legacy |

No borrar manualmente sin revisar. El script `scripts/cleanup-project.sh` mueve aquí lo que deja de ser necesario.
