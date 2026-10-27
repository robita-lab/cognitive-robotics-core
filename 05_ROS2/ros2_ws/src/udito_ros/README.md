# Arquitectura 3T - UDITO

## ¿Qué es 3T?

**3T** (*Three-Tier*, «tres capas») es una arquitectura clásica de robótica que separa al robot en tres niveles, cada uno con una responsabilidad:

| Capa | En UDITO | Pregunta que responde | Analogía de empresa |
|------|----------|----------------------|---------------------|
| **Deliberativa** | Cognitive (RAG + LLM + memoria) | **¿QUÉ** hago o digo? | Dirección: decide la estrategia |
| **Ejecutiva / secuenciadora** | C.C. sobre **ROS 2** (orquestador) | **¿CÓMO** y en qué orden? | Jefe de proyecto: reparte y coordina |
| **Reactiva / control** | Sensores y actuadores (STT, TTS, rostro, cuello, base) | Ejecuta y percibe | Equipo operativo |

Regla: **las órdenes bajan** (Cognitive → C.C. → actuadores) y **los datos suben** (sensores → C.C. → Cognitive). Ningún actuador recibe órdenes de otro sitio: **todo pasa por ROS 2**, que funciona como un bus de mensajes (publicación/suscripción), igual que un *Enterprise Service Bus*.

**Etapa actual (módulo 1):** órdenes simples por voz, sin RAG. El robot oye (STT), el C.C. reconoce la orden de un catálogo de 20 (`config/intents.yaml`) y reparte: voz (TTS), cara y, si toca, una orden al cuerpo (`/udito/intent`).

---

## Cómo arrancar

```bash
cd /opt/robita-lab
./scripts/ros2/udito-ros.sh --build    # la primera vez (o tras cambios en setup.py)
./scripts/ros2/udito-ros.sh            # las siguientes
```

Se abre la **Consola UDITO**: pulsa **ENCENDER**, mantén **MANTÉN PARA HABLAR** (o la barra espaciadora), di la orden y suelta. También puedes hacer clic en cualquier orden de la lista.

Opciones: `whisper:=tiny|base|small` (velocidad vs. precisión, por defecto base) · `stt_mode:=vad` (escucha continua) · `mic:=false` · `console:=false` · `body_example:=false` · `cognitive:=true rag:=true` · `face:=true` (cara en ventana aparte).

Audio (micrófono, altavoz, volumen): `./scripts/udito/audio.sh`.

---

## Nodos

| Nodo | Capa | Hace |
|------|------|------|
| `udito_stt` | Reactiva (sensor) | Micrófono → Whisper → texto. Modo «mantén para hablar» |
| `udito_tts` | Reactiva (actuador) | Recibe orden → Piper habla → avisa al terminar |
| `udito_cc` | Ejecutiva (C.C.) | Reconoce la orden y reparte: voz, cara, cuerpo |
| `udito_body_example` | Ejemplo cuerpo | Muestra cómo recibir `/udito/intent` y dónde conectar cuello y base |
| `udito_console` | Operador | Cara, ENCENDER, hablar, lista de órdenes y log en vivo |
| `udito_cognitive` | Deliberativa | (Desactivado en esta etapa) preguntas abiertas con RAG |

Los motores **no se duplican**: los nodos importan Whisper, Piper y RAG desde `01_SERVICES/`.

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

## Contrato de topics

| Topic | Tipo | De → A |
|-------|------|--------|
| `/udito/power` | Bool | Consola → C.C. (ENCENDER / APAGAR) |
| `/udito/stt/ptt` | Bool | Consola → STT (mantén para hablar) |
| `/udito/stt/text` | String | STT (o clic en consola) → C.C. |
| `/udito/stt/enable` | Bool | C.C. → STT (cierra el micro mientras habla) |
| `/udito/tts/say` | String JSON `{id,text,emotion,laugh}` | C.C. → TTS |
| `/udito/tts/done` | String JSON `{id}` | TTS → C.C. |
| `/udito/speech_out` | String JSON `{emotion,...}` | C.C./TTS → cara |
| `/udito/state` | String JSON `{state, stt_sec}` | STT/TTS → consola/cara |
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

**Ejemplo listo para copiar:** `udito_ros/body_example_node.py` (tabla de despacho acción → función).

**Probar sin voz:**

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /udito/intent                                            # terminal 1
ros2 topic pub --once /udito/stt/text std_msgs/String "{data: sigueme}"  # terminal 2
```

## Añadir una orden nueva

1. Añade un bloque en `config/intents.yaml` (`id`, `label`, `phrases`, `say`, `face` y, si mueve el cuerpo, `body`).
2. Si tiene `body`, añade su `name` en la tabla de despacho del orquestador del cuerpo.
3. Reinicia `./scripts/ros2/udito-ros.sh`. No hace falta tocar código del C.C.
