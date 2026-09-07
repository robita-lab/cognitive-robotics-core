# Adaptador físico UDITO (Jetson offline)

Código del **cuerpo** del robot: micrófono, wakeword, STT, RAG y TTS **locales** en la Jetson.

Guía: [DEPLOY_JETSON_OFFLINE.md](../../DEPLOY_JETSON_OFFLINE.md) · Scripts: [scripts/README.md](../../scripts/README.md)

```bash
cd /opt/robita-lab
./scripts/setup/jetson.sh
./scripts/setup/models-download.sh
./UDITO
```

Modo cerebro remoto (`udito.py` edge): archivado en [`_archive/modo-online/adapters/udito.py`](../../_archive/modo-online/adapters/udito.py).

---

## Archivos activos

| Archivo | Rol |
|---------|-----|
| `udito_standalone.py` | Pipeline offline (STT + RAG + TTS en proceso) |
| `robot_common.py` | Bucle wakeword, VAD, calibración |
| `udito_speech.py` | TTS con emociones + ROS2 `/udito/speech_out` |
| `config/session.json` | VAD, speaker lock, tiempos de grabación |
| `voice_features.py` | MFCC para speaker lock |

---

## Flujo offline

```
«udito» (OpenWakeWord + udito.onnx)
  → saludo Piper (agent.json)
  → grabación pregunta (VAD)
  → Whisper STT → RAG → Piper TTS
  → vuelve a escuchar wakeword
```

ROS2: `/udito/wakeword`, `/udito/state` — [05_ROS2/README.md](../../05_ROS2/README.md)

---

## Configuración

```bash
cp .env.example .env
./scripts/udito/audio-config.sh   # mic + altavoz
```

| Variable | Descripción |
|----------|-------------|
| `ROBITA_AUDIO_INPUT` | `respeaker` o índice ALSA |
| `ROBITA_AUDIO_OUTPUT` | `pulse`, `hdmi`, `platform` |
| `ROBITA_KNOWLEDGE_CORE` | Textos en `04_KNOWLEDGE_CORE/responses/` |

Wakeword: `01_SERVICES/wakeword-engine/config/wakeword.json`

---

## Textos hablados

- Saludo: `04_KNOWLEDGE_CORE/responses/agent.json`
- Despedida / Q&A: `conversation.json`, `qa.json`

Tras cambios en JSON, reinicia `./UDITO`.
