# Voz, pausas, emociones y ROS2

## Pausas

El módulo `udito_speech.py` parte el texto en segmentos y concatena WAV con silencio:

- Tras **coma** o **punto y coma**: ~400–520 ms (según emoción).
- Tras **punto / interrogación / exclamación**: ~750 ms.
- En rangos horarios se inserta coma antes de «hasta»: *desde las 8 de la mañana, hasta las 10 de la tarde*.

## Emociones

| `emotion`   | Uso típico                          |
|------------|--------------------------------------|
| `helpful`  | Respuesta RAG con dato en documentos |
| `sorry`    | Sin dato o similitud baja            |
| `happy`    | Saludos / despedida                  |
| `informative` | Dirección fija UDIT              |
| `neutral`  | Por defecto                          |

Ajustan `length_scale` y `noise_scale` de Piper por segmento.

## ROS2

Cada frase hablada escribe `/tmp/udito_speech_out.json` y, si `rclpy` está instalado y `ROBITA_ROS2_SPEECH=1`, publica en:

- **Topic:** `/udito/speech_out` (`std_msgs/String`, JSON)

```json
{
  "text": "Claro, la biblioteca abre...",
  "emotion": "helpful",
  "source": "rag",
  "label": "rag",
  "segments": [
    {"text": "Claro", "pause_after_ms": 420},
    {"text": "la biblioteca abre de lunes a viernes desde las 8 de la mañana", "pause_after_ms": 420},
    {"text": "hasta las 10 de la tarde", "pause_after_ms": 0}
  ]
}
```

Variables: `ROBITA_SPEECH_EVENT_FILE`, `ROBITA_ROS2_SPEECH`, `ROBITA_RAG_MIN_SIMILARITY` (default `0.38`).

Arranque pipeline offline: `./scripts/Principal-UDITO.sh` (o `./UDITO`). Pantalla ojos: [FACE_DISPLAY.md](FACE_DISPLAY.md).

## Frases de espera (pre-RAG)

Antes de `process_query`, si la pregunta no es saludo ni chiste/dato curioso, UDITO dice una frase aleatoria de `responses/pre_search_phrases.json` (13 variantes, emoción `thinking`).

## Bip de «pensando» (Fase 1)

Tras cerrar la grabación, suena `assets/audio/Clock1.mp3` en bucle mientras STT y RAG procesan (GStreamer + PulseAudio). Se detiene antes de hablar la respuesta.

Variables: `ROBITA_PROCESSING_CUE=1`, `ROBITA_PROCESSING_SOUND`, `ROBITA_PROCESSING_VOLUME` (default 0.35). Si `ROBITA_PROCESSING_CUE=1`, no se usa la frase hablada pre-RAG (evita duplicar feedback).

## Datos curiosos y chistes

`responses/fun_notes.json`: 5 datos curiosos y 20 chistes. Tras cada chiste suena una **risa sintética** (varios «ja» generados, no TTS). Opcional: `ROBITA_LAUGH_SOUND` apunta a un MP3/WAV propio.

Palabras clave: *dato curioso*, *chiste*, *cuéntame algo gracioso*, etc.

## Qué contesta según los documentos

| Situación | Comportamiento |
|-----------|----------------|
| **Dato en documentos** (similitud ≥ umbral) | Respuesta conversacional desde el chunk (`conversational_answer.py`), p. ej. horarios en lenguaje natural. Emoción `helpful`. |
| **Sin resultados** en el índice | `rag_no_results`: no inventa; sugiere Secretaría / web. Emoción `sorry`. |
| **Resultados débiles** (similitud &lt; umbral) | `rag_low_confidence`: mismo mensaje honesto. |
| **Pregunta no universitaria** (sin RAG) | Mismo criterio: no inventar (`gpt` → mensaje tipo no_results). |
