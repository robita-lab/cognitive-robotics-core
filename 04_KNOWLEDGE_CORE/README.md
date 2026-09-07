# Knowledge core — UDITO

Textos hablados y documentos para el asistente. El código carga todo vía `load_responses.py` y `ROBITA_KNOWLEDGE_CORE`.

## Estructura

```
04_KNOWLEDGE_CORE/
├── knowledge-text/          # Respuestas fijas rápidas (NO van al índice RAG)
│   ├── udito_identidad.txt    # Quién es UDITO
│   ├── udit_sedes_contacto.txt # Sedes Madrid + web (editar aquí)
│   └── udit_horarios.txt      # Horarios de atención
├── responses/               # JSON: saludo, despedida, chistes, Q&A
│   ├── agent.json           # Saludo tras wakeword («¿Dime?»)
│   ├── conversation.json
│   ├── qa.json              # Respuestas fijas (dirección hablada vía load_responses)
│   └── fun_notes.json       # Chistes y datos curiosos
├── raw-docs/                # Solo PDFs → índice RAG (rag_config.jetson.json)
│   └── *.pdf
└── load_responses.py
```

## Reglas

| Tipo de pregunta | Fuente |
|------------------|--------|
| Saludo / despedida / identidad | `responses/*.json` |
| Dirección, sedes, horarios | `knowledge-text/` (prioridad sobre RAG) |
| Chiste / dato curioso | `fun_notes.json` |
| **Cara / expresión** (sin RAG) | `face_commands.json` — «sonríe», «guiña», «cara triste», etc. |
| Normativa, trámites, PDFs | RAG sobre `raw-docs/*.pdf` |

Tras cambiar PDFs en `raw-docs/`, reindexar: `ROBITA_RAG_REBUILD=1` en `.env` y reiniciar UDITO (`./scripts/udito/start.sh`).

Tras editar `knowledge-text/` o `responses/`, basta reiniciar el pipeline (no hace falta reindexar).

Arranque Jetson offline: [DEPLOY_JETSON_OFFLINE.md](../DEPLOY_JETSON_OFFLINE.md) · comando principal: `./scripts/udito/start.sh` o `./UDITO`.
