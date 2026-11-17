# Arquitectura híbrida - UDITO · Proyecto `voice_skills` (oído y voz)

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales.
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Capa 1 · Habilidades.** Saben escuchar y hablar; no deciden nada: obedecen al C.C. ([`central_control`](../central_control/)).

| Nodo (ejecutable) | Archivo | Hace |
|-------------------|---------|------|
| `udito_stt` (`stt_node`) | `voice_skills/stt_node.py` | Micrófono → Whisper → texto (`/udito/stt/text`). Modo «mantén para hablar» o escucha continua |
| `udito_tts` (`tts_node`) | `voice_skills/tts_node.py` | Recibe `/udito/tts/say`, habla con Piper, envía a la cara el volumen del audio (boca sincronizada) y avisa en `/udito/tts/done` |

## De qué depende

| Pieza | Dónde |
|-------|-------|
| Whisper (oído) | `01_SERVICES/stt-engine/` |
| Piper (voz) y su configuración | `01_SERVICES/tts-engine/` · `config/tts_config.json` |
| Voz con emociones, volumen y reproducción | `01_SERVICES/voice-face-engine/` |
| Nombres de topics, vocabulario de órdenes y rutas | `central_control` (`topics.py`, `intents.py`, `paths.py`) — pasarán a `robita_interfaces` en F1 |

## Arrancar

Se arranca junto con el C.C.: `ros2 launch central_control udito_voice.launch.py` (o `robot`).
En la fase F1 el oído y la voz se unirán en una sola habilidad de voz en un único proceso (consenso, condición 4).
