# Piloto en la Jetson: `central_control` + `voice_skills` + `cognitive_language`

Pruebas del 12 y 13 de noviembre de 2026 en la Jetson Orin Nano de UDITO, con el
servidor LLM en un portátil de la misma red. Esta nota recoge lo que hay que hablar
con Danilo. La mayoría de los puntos son de la parte de voz (`voice_skills`).

- Rama de Danilo usada: `feature/ros2-voice-orchestrator` @ `973af73` (checkout en
  `/opt/cognitive-robotics-core`).
- Nuestra rama: `feature/cognitive-rag-llm`, instalada encima como worktree en
  `~/cognitive-language` (solo `--packages-select` de nuestros paquetes).
- Lanzamiento: `ros2 launch central_control udito_voice.launch.py cognitive:=false ...`
  y `ros2 param set /udito_cc use_cognitive true`. Con `cognitive:=true` arranca
  también el `cognitive_node` de Danilo y cada pregunta recibe dos respuestas.

## 1. Resumen

- La cadena completa funciona: oye, decide (orden del C.C. o pregunta al
  cognitivo), responde y habla.
- El cuello de botella es el **STT**. Con la configuración original
  (`whisper:=tiny` o `base`, media de los 6 canales) casi ninguna frase salía bien.
- Con un parche pequeño (sección 3) y `base`, las frases reales se transcriben bien
  en ~1,2 s y el robot empieza a hablar unos 3 s después de que el usuario termina.
- Para tener la precisión de `small` con ese retardo, **Whisper tiene que ir en la
  GPU de la Orin** (sección 4).

## 2. Números

| Medida | Valor |
|---|---|
| RAM total con todo arrancado (`base`) | ~3,1 GB de 7,6 GB |
| `cognitive_node` (nuestro) | 1,6–2,0 GB RSS (con el índice e5 de normativa cargado) |
| `stt_node` | 390 MB (`tiny`) · 443 MB (`base`) · 831 MB (`small`) |
| Transcripción por frase en CPU, 6 hilos | `base` ≈ 1,2 s · `small` ≈ 3,0 s |
| Respuesta del cognitivo | local < 30 ms · LLM 0,6–1,2 s (primera frase) |
| Silencio que cierra la frase (`silence_sec`) | 0,9 s |

Whisper siempre procesa una ventana de 30 s, así que el tiempo apenas depende de la
duración de la frase: con `small` en CPU no se baja de ~3 s.

## 3. STT: qué fallaba y el parche

Diagnóstico hecho con frases grabadas de los 6 canales del ReSpeaker y transcritas
offline en la Jetson con cada combinación de canal y modelo.

| Combinación (5 frases de prueba) | Aciertos | Tiempo/frase |
|---|---|---|
| `base` + media de 6 canales (original) | 0/5 | 1,1 s |
| `base` + canal 0 + vocabulario UDIT, sin reintentos | 4/5 | 1,2 s |
| `small` + media de 6 canales | 2/5 | 3,3 s |
| `small` + canal 0 + vocabulario UDIT | 5/5 | 3,0–3,3 s |

Causas:

1. **Mezcla de canales.** `robot_common.mono_from_capture` hace la media de los 6
   canales. En el ReSpeaker (firmware de 6 canales) el **canal 0 ya es el audio
   procesado por la placa** (beamforming, cancelación de eco, supresión de ruido), los
   canales 1–4 son los micros en bruto y el 5 es la referencia de reproducción (en
   silencio). La media mezcla la señal limpia con las crudas desfasadas. Ejemplo:
   «¿qué asignaturas tiene el máster oficial de animación?» → «¿qué hace en la
   naturaleza el más oficial de la emisión?».
2. **Sin vocabulario de UDIT.** El `initial_prompt` solo lleva las órdenes del
   robot. «UDIT» salía como «un hit», «vít» o «judí», y «sedes» como «se destiene».
3. **Reintentos de Whisper.** Con audio dudoso, faster-whisper repite la
   decodificación subiendo la temperatura, hasta 6 veces. Una frase tardó **40 s** y
   salió mezclada con palabras de la guía.

Parche: [`stt-channel-and-context.patch`](stt-channel-and-context.patch), sobre
`973af73`, 2 ficheros. Ahora mismo está aplicado sin commit en el checkout de la
Jetson. Se revierte con `git apply -R`.

- `robot_common.py`: nuevo `capture_channel()`. Con varios canales usa el canal 0 por
  defecto; `ROBITA_AUDIO_CHANNEL=mean` recupera la media y `=N` elige otro canal.
- `stt_node.py`:
  - parámetro `context_prompt` con vocabulario de UDIT, que se añade **después** de
    las órdenes porque faster-whisper conserva solo los últimos ~223 tokens de la guía;
  - `temperature=0.0` y `without_timestamps=True`;
  - `threads` por defecto `os.cpu_count()` (6 en la Orin Nano; antes 4). El launch no
    expone `threads` y el valor solo se lee al cargar el modelo.

Efecto secundario a vigilar: el canal 0 lleva ganancia automática y el ruido medido
por el VAD sube (0,0003 → 0,0005–0,0028). Con el umbral mínimo `min_rms` 0,01 de
momento va bien.

## 4. Propuesta: Whisper en la GPU de la Orin

**Objetivo:** `small` (o mejor) en menos de 1 s por frase, para tener la precisión de
`small` con el retardo de `base`.

**Estado actual de la Jetson (13-nov):**

- L4T R36.4.7 (JetPack 6.2), CUDA 12.6, TensorRT 10.3, modo de energía `MAXN_SUPER`.
- `ctranslate2 4.7.2` instalado desde pip **sin CUDA** (`get_cuda_device_count() == 0`).
  `torch 2.12.0+cpu`. Es decir, ahora mismo nada de Python usa la GPU.
- **Disco al 98 %** (quedan 3,2 GB en `/`). Hay que liberar espacio antes de compilar
  nada o de bajar contenedores.
- La GPU comparte los 7,6 GB de RAM con la CPU. `small` en fp16 ocupa del orden de
  1 GB y cabe con lo que hay ahora (~3 GB usados).

**Opciones**, de menos a más cambio de código:

| Opción | Qué implica | Cambio en `stt_node` |
|---|---|---|
| A. CTranslate2 compilado con CUDA en la Jetson | Compilar CTranslate2 desde fuente (`-DWITH_CUDA=ON -DWITH_CUDNN=ON`, arquitectura sm_87) e instalarlo en el venv | Mínimo: `WhisperModel(..., device="cuda", compute_type="float16")` o `int8_float16` |
| B. Contenedor de [jetson-containers](https://github.com/dusty-nv/jetson-containers) (faster-whisper / whisper_trt) | Usar una imagen ya preparada para JetPack 6; correr el STT dentro del contenedor | Medio: el nodo o el motor STT pasan a vivir en el contenedor |
| C. whisper.cpp con CUDA | Compilar whisper.cpp (`GGML_CUDA=1`) y usar sus bindings o su servidor | Mayor: otro motor y otro formato de modelo (ggml) |

**Recomendación:** empezar por **A**, porque mantiene faster-whisper y el resto del
código tal cual. Si la compilación da guerra, pasar a **B**.

**Plan de prueba:**

1. Liberar disco.
2. Compilar e instalar.
3. Repetir la medida offline con las mismas grabaciones (`~/pilot-logs/mic6/`,
   scripts `stt_compare.py` y `stt_speed.py`): tiempo por frase y aciertos con
   `base`, `small` y, si cabe, `medium` o `large-v3-turbo`.
4. Medir la RAM total con todo arrancado.
5. Comprobar que el TTS (Piper) y nuestro nodo no se resienten.

Los tiempos esperados en GPU son una estimación: hay que medirlos.

## 5. Otros temas para hablar

**Parte de voz y control (Danilo):**

- **El robot contesta a todo lo que oye.** En modo `vad`, con un vídeo sonando en la
  sala transcribió y contestó unas 60 frases seguidas. Hace falta un mecanismo de
  atención: palabra de activación (el antiguo `wakeword-engine`), PTT desde la
  consola, o al menos exigir «UDITO» al principio, con una ventana de conversación
  abierta durante unos segundos.
- **Bucles de repetición de Whisper.** Con ruido salen cosas como «los dos, los dos,
  los dos…» o «la jefe de la jefe…». Al quitar los reintentos esto ya no se filtra
  solo. Propuesta: descartar la transcripción si algún segmento tiene
  `compression_ratio > 2.4`, `avg_logprob < -1.0` o `no_speech_prob > 0.6`, o bien
  usar `no_repeat_ngram_size`.
- **Streaming.** El C.C. usa los topics `/udito/cognitive/query|answer` y espera la
  respuesta completa. Nuestra acción `/udito/cognitive/think` envía frase a frase; si
  el C.C. la usara, el TTS podría empezar con la primera frase y se ganarían
  0,3–0,6 s en las respuestas largas.
- Exponer `threads` y `context_prompt` en `udito_voice.launch.py`.

**Nuestra parte (`cognitive_language`), ya en marcha:**

- Respuestas fijas que saltan por error: `basic_qa_manager.py` busca palabras clave
  como trozos de texto, así que «parte» coincide dentro de «imparten», y «oficial»,
  «robot» o «universidad» son demasiado genéricas.
- El LLM a veces se inventa datos de UDIT («un máster tiene entre 6 y 12 cursos»)
  o se niega con preguntas que la normativa sí cubre («¿qué titulación hace falta
  para acceder a un grado oficial?»).
- Arreglado en la rama: el LLM copiaba la frase de respaldo del historial
  (`e586101`, `c5bb788`).
