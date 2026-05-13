# Robot físico UDIT (producto UDITO)

| Script | Etapa | Uso |
|--------|-------|-----|
| `robot_voice_loop.py` | 1 | Todo en un equipo (STT+RAG TinyLlama+TTS local) |
| `robot_edge_client.py` | 2 | Jetson: wakeword local → cerebro servidor por LAN |
| `robot_common.py` | — | Audio, VAD, bucle wakeword compartido |

Guía completa: [`DEPLOY_UDITO.md`](../../DEPLOY_UDITO.md) en la raíz del repo.

```bash
./scripts/etapa1-local.sh                              # etapa 1
./scripts/etapa2-servidor.sh  # + etapa2-edge.sh       # etapa 2
```
