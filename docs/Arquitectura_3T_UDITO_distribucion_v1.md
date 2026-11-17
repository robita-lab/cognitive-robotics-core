# Arquitectura 3T - UDITO

## ¿Qué es 3T?

**3T** (*Three-Tier*, «tres capas») es una arquitectura clásica de robótica que separa al robot en tres niveles, cada uno con una única responsabilidad:

| Capa | En UDITO | Pregunta que responde | Analogía de empresa |
|------|----------|----------------------|---------------------|
| **Deliberativa** | `cognitive` (RAG + LLM + memoria) | **¿QUÉ** hago o digo? | Dirección: decide la estrategia |
| **Ejecutiva** | `cc` — orquestador central en **ROS 2** | **¿CÓMO** y en qué orden? | Jefe de proyecto: reparte y coordina |
| **Reactiva** | `voice`, `face`, `head`, `base` (sensores y actuadores) | Percibe y ejecuta | Equipo operativo |

**Reglas:**
- **Las órdenes bajan** (cognitive → cc → actuadores) y **los datos suben** (sensores → cc → cognitive).
- **Solo el `cc` da órdenes.** Ningún actuador recibe órdenes de otro nodo.
- **Todo pasa por ROS 2**, que funciona como un bus de mensajes (publicación/suscripción), igual que un *Enterprise Service Bus*.

### Conceptos ROS 2

| Concepto | Qué es | Analogía |
|----------|--------|----------|
| **Nodo** | Programa independiente con una sola responsabilidad | Un empleado con un puesto |
| **Topic** | Canal de mensajes con nombre (existe solo en ejecución) | Un canal de Teams |
| **Publisher** | Nodo que escribe en un topic | Quien publica en el canal |
| **Subscriber** | Nodo que lee un topic | Quien sigue el canal |

---

## 1. Hardware (inventario)

| Equipo | Componentes conectados |
|--------|------------------------|
| **Jetson Orin Nano** | ReSpeaker (micrófono), altavoz, pantalla |
| **Mini PC** (base, Intel) | Arduino UNO + driver de motores (ruedas), lidar LD19, Arduino cuello, ReSpeaker (base) |
| **Cabeza** | 2 servos (cuello: giro + inclinación) · 2 matrices LED 8×8 (ojos) → Arduino cuello |
| **Base** | 2 ruedas motorizadas → Arduino UNO |

---

## 2. Distribución de nodos

| Máquina | Nodo | Capa 3T | Contiene / controla | Hardware |
|---------|------|---------|---------------------|----------|
| **Jetson** | `voice` | Reactiva | STT (Whisper) + TTS (Piper) | ReSpeaker + altavoz |
| **Jetson** | `face` | Reactiva | Pantalla: boca y emociones | Pantalla |
| **Jetson** | `cognitive` | Deliberativa | RAG + LLM (desactivado en módulo 1) | — |
| **Mini PC** | `cc` | Ejecutiva | Orquestador (`intents.yaml`) | — |
| **Mini PC** | `head` | Reactiva | Cuello (2 servos) + ojos (2 matrices LED) | Arduino cuello |
| **Mini PC** | `base` | Reactiva | Ruedas + lidar + Nav2 | Arduino UNO + lidar |

**Criterios:**
- **Jetson = sentidos y cerebro:** su GPU/CPU se dedica a Whisper, Piper y RAG.
- **Mini PC = mando y cuerpo:** el `cc` está junto a los motores; una orden «para» llega directa a las ruedas.
- Un nodo va en la máquina a la que está **enchufado su Arduino**.
- STT y TTS van juntos en `voice`: comparten el audio y el robot cierra su micrófono mientras habla.
- Cuello y ojos van juntos en `head`: misma cabeza, mismo Arduino.

```
┌──────────────── JETSON ────────────────┐        ┌──────────────── MINI PC ───────────────┐
│                                         │        │                                         │
│  voice ──/udito/stt─────────────────────┼───────▶│ cc                                      │
│  voice ◀─/udito/tts─────────────────────┼────────│ cc                                      │
│  voice ──/udito/tts_done────────────────┼───────▶│ cc                                      │
│  face  ◀─/udito/eyes_pose───────────────┼────────│ cc ──/udito/eyes_pose──▶ head ─▶ ojos LED│
│  cognitive ◀─/udito/cognitive/query─────┼────────│ cc ──/udito/neck_pose──▶ head ─▶ servos │
│  cognitive ──/udito/cognitive/answer────┼───────▶│ cc ──/udito/move───────▶ base ─▶ ruedas │
└─────────────────────────────────────────┘ Ethernet └─────────────────────────────────────────┘
```

---

## 3. Topics

| Topic | Tipo de mensaje | Publica | Se suscriben | Contenido |
|-------|-----------------|---------|--------------|-----------|
| `/udito/stt` | `body_interfaces/Speech2Text` | voice | cc | Texto reconocido + confianza |
| `/udito/tts` | `std_msgs/String` (JSON) | cc | voice | `{id, text, emotion}` |
| `/udito/tts_done` | `std_msgs/String` (JSON) | voice | cc | `{id}` al terminar de hablar |
| `/udito/doa` | `body_interfaces/DOA` | voice | cc (y head como reflejo) | Ángulo de quien habla |
| `/udito/eyes_pose` | `std_msgs/String` (JSON) | cc | **head, face** | `{expression, gaze_x, gaze_y, blink}` |
| `/udito/neck_pose` | `sensor_msgs/JointState` | cc | head | `pan`, `tilt` (radianes) |
| `/udito/move` | `geometry_msgs/Twist` | cc | base | Velocidad lineal y angular |
| `/udito/cognitive/query` | `std_msgs/String` (JSON) | cc | cognitive | `{id, text}` |
| `/udito/cognitive/answer` | `std_msgs/String` (JSON) | cognitive | cc | `{id, text, emotion}` |
| `/udito/cc/log` | `std_msgs/String` | cc | consola (pruebas) | Qué hace el cc, paso a paso |

**Mensajes estándar:** `Twist` es el estándar ROS para bases móviles (Nav2, `robot_base_nav`); `JointState` para articulaciones; `Speech2Text` y `DOA` ya existen en `body_interfaces` (paquete del investigador).

---

## 4. Ejemplo de flujo: «sígueme»

| Paso | Quién | Topic | Mensaje |
|------|-------|-------|---------|
| 1 | voice | `/udito/stt` | «sígueme» |
| 2 | cc | — | Reconoce la orden `follow_me` en `intents.yaml` |
| 3 | cc | `/udito/eyes_pose` | `{expression: happy}` → head (ojos LED) y face (pantalla) |
| 4 | cc | `/udito/tts` | «¡Te sigo!» → voice |
| 5 | cc | `/udito/move` | velocidades de seguimiento → base |
| 6 | voice | `/udito/tts_done` | Terminó de hablar → cc reabre el turno |

---

## 5. Del código actual a esta arquitectura

| Hoy (rama `feature/ros2-voice-orchestrator`) | Pasa a ser |
|---------------------------------------------|-----------|
| `udito_stt` + `udito_tts` | `voice` |
| `udito_cc` | `cc` (se ejecuta en el mini PC) |
| `udito_console` (cara) | `face` + consola solo para pruebas |
| `udito_body_example` | Referencia para `head` y `base` |
| `/udito/stt/text` | `/udito/stt` |
| `/udito/tts/say`, `/udito/tts/done` | `/udito/tts`, `/udito/tts_done` |
| `/udito/speech_out` | `/udito/eyes_pose` |
| `/udito/intent` | `/udito/neck_pose` + `/udito/move` |

---

## 6. Pendiente de decidir

1. **Dos ReSpeaker** (base y Jetson): usar solo el de la Jetson para la voz; confirmar si el de la base se usa para dirección del sonido.
2. **Cuello reactivo:** ¿`head` gira solo hacia quien habla (`/udito/doa`) o todo pasa por el `cc`?
3. **Red Jetson ↔ mini PC:** cable Ethernet y mismo `ROS_DOMAIN_ID` en ambas.
4. **Rendimiento Jetson:** `jetson_clocks` y `snapd` detenido al arrancar (hoy manual).
