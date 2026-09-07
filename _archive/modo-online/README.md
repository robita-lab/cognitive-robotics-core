# Modo online / servidor — archivado

Contenido **retirado de la rama `develop`** (Jetson offline). Se conserva aquí para cuando volváis a cerebro remoto o Docker.

| Qué | Para qué era |
|-----|----------------|
| `scripts/server/` | Cerebro en red, robot edge, Docker |
| `docker-compose.yml` | Stack HTTP puertos 8000–8004 |
| `DEPLOY_UDITO.md` | Despliegue etapa 1/2 servidor + Jetson |
| `adapters/udito.py` | Robot físico → `POST /voice-query` al cerebro |
| `01_SERVICES/pipeline-orchestrator/` | Orquestador HTTP |
| `02_AGENTS_FACTORY/` | Perfil cerebro remoto (no usado en standalone) |

**Rama `develop-base`:** conserva el historial completo; este árbol `_archive/` debe existir también allí tras merge.

**Recuperar modo online:** copiar desde aquí a las rutas originales o revisar commit anterior en `develop-base`.
