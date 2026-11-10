# Arquitectura híbrida - UDITO · Proyecto `central_control` (C.C.)

> **Arquitectura híbrida** = evolución del modelo 3T acordada en el consenso de ROBITA-lab (D14).
> Conserva la separación deliberativa / ejecutiva / reactiva y añade **habilidades** con contrato
> uniforme, un **ejecutivo en Behavior Tree** (py_trees, fase F2) y **cuatro planos transversales**
> (seguridad, modelo del mundo, modos y salud, observabilidad).
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

UDITO en ROS 2 son **dos proyectos** (paquetes) en `05_ROS2/ros2_ws/src/`:

| Proyecto | Capa | Contiene | Analogía de empresa |
|----------|------|----------|---------------------|
| **`central_control`** (este) | 2 · Ejecutiva (+ operador y 3 · deliberativa) | C.C. `udito_cc`, catálogo de órdenes, consola, ejemplo del cuerpo, `cognitive`, lanzador | Jefe de proyecto: decide cómo y cuándo |
| [`voice_skills`](../voice_skills/) | 1 · Habilidades | Oído (`udito_stt`) y voz (`udito_tts`) | Especialistas en escuchar y hablar |

Los motores no son ROS y viven en `01_SERVICES/` (Whisper, Piper y `voice-face-engine`: voz con emociones, rostro y audio).
La instalación del hardware está en `03_ADAPTERS/UDITO_ROBOT_SOCIAL/Dispositivos/Jetson_Orin_Nano`.

**Etapa actual (módulo 1):** órdenes simples por voz, sin RAG. El robot oye (STT), el C.C. reconoce la
orden de un catálogo de 20 (`config/intents.yaml`) y reparte: voz (TTS), cara y, si toca, una orden al
cuerpo (`/udito/intent`). El operador puede escribir frases con expresión: `[feliz] ¡Hola! [sorpresa] ¿En serio?`.

---

## Cómo arrancar

| Forma | Comando |
|-------|---------|
| **Nativa ROS 2** (recomendada) | `ros2 launch central_control udito_voice.launch.py` |
| Atajo | `robot` — cierra instancias anteriores, compila si hace falta y lanza lo mismo |

La primera vez (o tras cambiar `setup.py`):

```bash
cd /opt/cognitive-robotics-core/05_ROS2/ros2_ws && colcon build --packages-select central_control voice_skills --symlink-install
```

El lanzador prepara el entorno solo: lee `.env`, añade el `.venv` (Whisper, Piper, RAG) y, en la Jetson,
las variables de bajo consumo. **Las variables que ya tengas en la terminal mandan.** Los ajustes de
hardware (frecuencias, ReSpeaker, snap) se aplican al iniciar Ubuntu, no aquí.

### Opciones del lanzador

| Opción | Valores | Por defecto | Efecto |
|--------|---------|-------------|--------|
| `whisper` | `tiny` · `base` · `small` | `base` | Velocidad frente a precisión del STT |
| `stt_mode` | `ptt` · `vad` | `ptt` | Mantén para hablar / escucha continua |
| `mic` | `true` · `false` | `true` | Sin micrófono (pruebas por texto) |
| `console` | `true` · `false` | `true` | Consola del operador |
| `body_example` | `true` · `false` | `true` | Nodo de ejemplo del cuerpo |
| `cognitive` · `rag` | `true` · `false` | `false` | Capa deliberativa y RAG completo |
| `face` | `true` · `false` | `false` | Cara en ventana aparte (pantalla física) |

Ejemplo: `ros2 launch central_control udito_voice.launch.py whisper:=tiny mic:=false`

### Variables de entorno (archivo `.env` de la raíz)

| Variable | Para qué |
|----------|----------|
| `ROBITA_AUDIO_INPUT` · `ROBITA_AUDIO_OUTPUT` | Micrófono y altavoz (los guarda la pantalla de audio) |
| `ROBITA_AUDIO_VOLUME` | Volumen de la voz (0–100) |
| `UDITO_INTENTS` | Otro catálogo de órdenes en vez de `config/intents.yaml` |
| `ROBITA_TTS_CONFIG` | Configuración de la voz (Piper) |
| `ROBITA_RAG_CONFIG` · `HF_HOME` | RAG y carpeta de modelos |
| `ROBITA_ROOT` | Raíz del repo (por defecto `/opt/cognitive-robotics-core`) |

Pantalla de audio: `./scripts/udito/audio.sh`.

---

## Nodos

| Nodo (ejecutable) | Capa | Hace |
|-------------------|------|------|
| `udito_stt` (`voice_skills/stt_node`) | 1 · Habilidad | Micrófono → Whisper → texto. Modo «mantén para hablar» |
| `udito_tts` (`voice_skills/tts_node`) | 1 · Habilidad | Habla con Piper, boca sincronizada con el volumen del audio, avisa al terminar |
| `udito_cc` (`udito_cc_node`) | 2 · Ejecutiva | **C.C. de UDITO**: reconoce la orden y reparte voz, cara y cuerpo |
| `udito_body_example` (`body_example_node`) | Ejemplo | Cómo recibir `/udito/intent` y dónde conectar cuello y base |
| `udito_console` (`console_node`) | Operador | Robot dibujado, ENCENDER, hablar, órdenes, «Haz que diga» y log |
| `udito_cognitive` (`cognitive_node`) | 3 · Deliberativa | (Desactivado) preguntas abiertas con RAG |

Los motores **no se duplican**: los nodos importan Whisper, Piper y RAG desde `01_SERVICES/`, y los
módulos de voz, rostro y audio desde `01_SERVICES/voice-face-engine/`.

## Flujo de una orden («sígueme»)

```
[micrófono] → udito_stt ──/udito/stt/text «sígueme»──▶ udito_cc
                                                   │ reconoce: follow_me (intents.yaml)
             ┌─────────────────────────────────────┼──────────────────────────────┐
             ▼                                     ▼                              ▼
   /udito/intent {follow, target:person}   /udito/speech_out {happy}    /udito/tts/say «¡Te sigo!»
             ▼                                     ▼                              ▼
   orquestador del CUERPO (Nav2)              cara (pantalla)                 udito_tts (altavoz)
```

## Archivos de este proyecto

| Archivo | Para qué |
|---------|----------|
| `central_control/udito_cc_node.py` | El C.C.: reconoce la orden y reparte voz, cara y cuerpo |
| `central_control/intents.py` | Carga y reconoce órdenes; separa etiquetas de emoción |
| `config/intents.yaml` | Las 20 órdenes (sin tocar código) |
| `central_control/topics.py` | Nombres de todos los topics (también los usa `voice_skills`) |
| `central_control/paths.py` | Rutas del repo y de los motores de `01_SERVICES` |
| `central_control/console_node.py` | Consola del operador |
| `central_control/body_example_node.py` | Ejemplo para el orquestador del cuerpo |
| `central_control/cognitive_node.py` | Capa deliberativa (RAG, desactivada) |
| `launch/udito_voice.launch.py` | Arranca los dos proyectos |

## Contrato de topics (módulo 1)

Hoy son `std_msgs` con JSON. En la fase F1 pasan a mensajes tipados de `robita_interfaces`
(`Utterance`, `TurnTrace` y la acción `Think`), según el consenso (D2, D3).

| Topic | Tipo | De → A |
|-------|------|--------|
| `/udito/power` | Bool | Consola → C.C. (ENCENDER / APAGAR) |
| `/udito/stt/ptt` | Bool | Consola → STT (mantén para hablar) |
| `/udito/stt/text` | String | STT (o clic en consola) → C.C. |
| `/udito/stt/enable` | Bool | C.C. → STT (cierra el micro mientras habla) |
| `/udito/cc/say` | String JSON `{text,emotion}` | Consola («Haz que diga») → C.C. |
| `/udito/tts/say` | String JSON `{id,text,emotion,laugh}` | C.C. → TTS |
| `/udito/tts/done` | String JSON `{id}` | TTS → C.C. |
| `/udito/speech_out` | String JSON `{emotion,...}` | C.C./TTS → cara |
| `/udito/state` | String JSON `{state, env, fps}` | STT/TTS → consola/cara |
| `/udito/intent` | String JSON (ver abajo) | **C.C. → orquestador del cuerpo** |
| `/udito/cc/log` | String | C.C. → consola (qué hace, paso a paso) |
| `/udito/cognitive/query` · `/answer` | String JSON | C.C. ↔ Cognitive (desactivado) |

---

## Para el responsable del orquestador del cuerpo

El C.C. **no mueve motores**: publica la intención en `/udito/intent` y el orquestador del cuerpo decide cómo ejecutarla.

**Mensaje** (`std_msgs/String` con JSON):

```json
{
  "name": "follow",
  "args": {"target": "person"},
  "intent": "follow_me",
  "text": "sígueme",
  "source": "udito_cc",
  "stamp": 1791238809.57
}
```

**Acciones que hoy emite el C.C.**

| Orden dicha | `name` | `args` | Dónde conectarlo |
|-------------|--------|--------|------------------|
| mira a la izquierda / derecha | `look` | `{direction, degrees}` | `head_package` → servicio `HeadMove` |
| asiente / niega | `head_gesture` | `{gesture: nod/shake, times}` | secuencia de `HeadMove` |
| sígueme | `follow` | `{target: person}` | seguimiento (lidar/cámara) + Nav2 |
| para / quieto | `stop` | `{}` | cancelar metas Nav2 + `/cmd_vel` = 0 |
| ven aquí | `go_to` | `{target: speaker}` | acción `NavigateToPose` |
| da una vuelta | `rotate` | `{degrees: 360}` | `/cmd_vel` angular o `Spin` de Nav2 |

**Ejemplo listo para copiar:** `central_control/body_example_node.py` (tabla de despacho acción → función).

**Probar sin voz:**

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /udito/intent                                            # terminal 1
ros2 topic pub --once /udito/stt/text std_msgs/String "{data: sigueme}"  # terminal 2
```

## Añadir una orden nueva

1. Añade un bloque en `config/intents.yaml` (`id`, `label`, `phrases`, `say`, `face` y, si mueve el cuerpo, `body`).
2. Si tiene `body`, añade su `name` en la tabla de despacho del orquestador del cuerpo.
3. Reinicia con `robot` (o `ros2 launch central_control udito_voice.launch.py`). No hace falta tocar código del C.C.
