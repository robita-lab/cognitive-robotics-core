# Arquitectura 3T - UDITO

Asistente por voz del robot social **UDITO** (ROBITA-lab, UDIT) integrado en **ROS 2 Humble**. Rama: `feature/ros2-voice-orchestrator`.

---

## 1. ¿Qué es 3T?

**3T** (*Three-Tier*, «tres capas») es una arquitectura clásica de robótica que separa al robot en tres niveles, cada uno con una única responsabilidad:

| Capa | En UDITO | Pregunta que responde | Analogía de empresa |
|------|----------|----------------------|---------------------|
| **Deliberativa** | `cognitive` (RAG + LLM + memoria) | **¿QUÉ** hago o digo? | Dirección: decide la estrategia |
| **Ejecutiva** | `cc` — orquestador central en **ROS 2** | **¿CÓMO** y en qué orden? | Jefe de proyecto: reparte y coordina |
| **Reactiva** | voz, cara, cuello, base (sensores y actuadores) | Percibe y ejecuta | Equipo operativo |

**Reglas de la arquitectura**

- Las **órdenes bajan** (cognitive → cc → actuadores) y los **datos suben** (sensores → cc → cognitive).
- **Solo el `cc` da órdenes.** Ningún actuador recibe órdenes de otro nodo.
- **Todo pasa por ROS 2**, que funciona como un bus de mensajes de publicación/suscripción (equivalente a un *Enterprise Service Bus*).

### Conceptos ROS 2

| Concepto | Qué es | Analogía |
|----------|--------|----------|
| **Nodo** | Programa independiente con una sola responsabilidad | Un empleado con un puesto |
| **Topic** | Canal de mensajes con nombre (existe solo en ejecución) | Un canal de Teams |
| **Publisher** | Nodo que escribe en un topic | Quien publica en el canal |
| **Subscriber** | Nodo que lee un topic | Quien sigue el canal |

---

## 2. Qué incluye esta versión (módulo 1)

Órdenes simples por voz, **sin RAG**, con respuesta inmediata:

- **Oído (STT):** Whisper, modo «mantén para hablar» (~1,6 s por frase en la Jetson).
- **Voz (TTS):** Piper, con emociones, risa y control de volumen.
- **Orquestador (C.C.):** reconoce 20 órdenes de `config/intents.yaml` y reparte: voz, cara y cuerpo.
- **Consola del operador:** cara animada, botón ENCENDER, botón HABLAR, lista de órdenes y log en vivo.
- **Pantalla de audio:** elegir micrófono y altavoz, probar y ajustar volumen.
- **Ejemplo para el cuerpo:** nodo de referencia que recibe las órdenes de movimiento.

Los motores de IA (`01_SERVICES/`) **no se duplican**: los nodos ROS 2 los importan. El asistente sigue funcionando sin ROS 2 en otros dispositivos.

---

## 3. Arquitectura

### Distribución actual (desarrollo)

Todo corre en la **Jetson Orin Nano**.

### Distribución objetivo

| Máquina | Nodo | Capa | Controla |
|---------|------|------|----------|
| Jetson | `voice` | Reactiva | STT + TTS (ReSpeaker + altavoz) |
| Jetson | `face` | Reactiva | Pantalla (boca y emociones) |
| Servidor | `cognitive` | Deliberativa | RAG + LLM |
| Mini PC | `cc` | Ejecutiva | Orquestador |
| Mini PC | `head` | Reactiva | Cuello (2 servos) + ojos (2 matrices LED) — Arduino cuello |
| Mini PC | `base` | Reactiva | Ruedas + lidar + Nav2 — Arduino ruedas |

Detalle completo, tabla de topics objetivo y decisiones pendientes: [`docs/Arquitectura_3T_UDITO_distribucion_v1.md`](docs/Arquitectura_3T_UDITO_distribucion_v1.md).

### Flujo de una orden («sígueme»)

```
[micrófono] → udito_stt ──/udito/stt/text «sígueme»──▶ udito_cc
                                                   │ reconoce: follow_me (intents.yaml)
             ┌─────────────────────────────────────┼──────────────────────────────┐
             ▼                                     ▼                              ▼
   /udito/intent {follow}              /udito/speech_out {happy}       /udito/tts/say «¡Te sigo!»
             ▼                                     ▼                              ▼
   orquestador del cuerpo                    cara (pantalla)                udito_tts (altavoz)
```

---

## 4. Estructura de archivos

```
cognitive-robotics-core/
├── 01_SERVICES/                     # Motores de IA (sin cambios de lógica)
│   ├── stt-engine/                  # Whisper
│   ├── tts-engine/config/tts_config.json   # ← voz del robot
│   └── rag-engine/                  # RAG (no usado en módulo 1)
├── 03_ADAPTERS/robot-udit-physical/
│   └── udito_audio.py               # Pantalla de audio
├── 04_KNOWLEDGE_CORE/responses/     # Chistes, datos curiosos, expresiones
├── 05_ROS2/ros2_ws/src/udito_ros/   # ← Paquete ROS 2 de UDITO
│   ├── config/intents.yaml          # ← Las 20 órdenes
│   ├── launch/udito_voice.launch.py
│   └── udito_ros/
│       ├── topics.py                # Nombres de todos los topics
│       ├── stt_node.py              # Oído
│       ├── tts_node.py              # Voz
│       ├── orchestrator_node.py     # C.C.
│       ├── console_node.py          # Consola del operador
│       ├── body_example_node.py     # Ejemplo para el cuerpo
│       └── cognitive_node.py        # RAG (desactivado)
├── docs/                            # Documentación de arquitectura
└── scripts/
    ├── ros2/udito-ros.sh            # ← Arranque
    ├── udito/audio.sh               # ← Pantalla de audio
    └── setup/ros2-humble.sh         # Instalador ROS 2 (Ubuntu 22.04)
```

---

## 5. Instalación

### Jetson Orin Nano (Ubuntu 22.04, JetPack 6)

```bash
git clone -b feature/ros2-voice-orchestrator https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
cd /opt/robita-lab
./scripts/setup/ros2-humble.sh     # ROS 2 Humble (si no está instalado)
./scripts/setup/jetson.sh          # Motores de IA (.venv)
./scripts/setup/piper-jetson.sh    # Binario de voz para ARM
./scripts/setup/models-download.sh # Modelos (primera vez, necesita internet)
```

### Otro PC con Ubuntu 22.04

Mismos pasos, excepto `piper-jetson.sh`.

---

## 6. Cómo usar

### 6.1 Rendimiento de la Jetson (tras cada reinicio)

```bash
sudo jetson_clocks && sudo systemctl stop snapd snapd.socket
```

Sin esto, el STT puede pasar de ~1,6 s a más de 20 s.

### 6.2 Configurar el audio (una vez)

```bash
cd /opt/robita-lab && ./scripts/udito/audio.sh
```

Elige micrófono y altavoz, ajusta el volumen, prueba y pulsa **Guardar selección**.

### 6.3 Arrancar el robot

```bash
cd /opt/robita-lab && ./scripts/ros2/udito-ros.sh --build   # primera vez o tras cambios
cd /opt/robita-lab && ./scripts/ros2/udito-ros.sh           # siguientes veces
```

En la **Consola UDITO**:

1. Pulsa **ENCENDER**.
2. Mantén **MANTÉN PARA HABLAR** (o la barra espaciadora), di la orden y suelta.
3. También puedes hacer clic en cualquier orden de la lista.

**Opciones de arranque**

| Opción | Efecto |
|--------|--------|
| `whisper:=tiny\|base\|small` | Velocidad frente a precisión del STT (por defecto `base`) |
| `stt_mode:=vad` | Escucha continua en vez de «mantén para hablar» |
| `mic:=false` | Sin micrófono (pruebas por texto) |
| `console:=false` | Sin consola |
| `body_example:=false` | Sin el nodo de ejemplo del cuerpo |
| `cognitive:=true rag:=true` | Activa el RAG para preguntas abiertas |

### 6.4 Probar sin voz

```bash
source /opt/ros/humble/setup.bash
ros2 topic pub --once /udito/stt/text std_msgs/String "{data: sigueme}"
ros2 topic echo /udito/intent
ros2 node list      # nodos vivos
ros2 topic list     # topics vivos
```

---

## 7. Órdenes disponibles

| # | Orden | Hace | Cuerpo |
|---|-------|------|--------|
| 1 | hola | Saluda | |
| 2 | cómo te llamas | Se presenta | |
| 3 | cuéntame un chiste | Chiste + risa | |
| 4 | ríete | Risa | |
| 5 | sonríe | Cara feliz | |
| 6 | ponte triste | Cara triste | |
| 7 | sorpréndete | Cara de sorpresa | |
| 8 | guiña un ojo | Guiño | |
| 9 | mueve los ojos | Ciclo de expresiones | |
| 10 | duérmete | Cara dormida | |
| 11 | mira a la izquierda | Gira el cuello | `look` |
| 12 | mira a la derecha | Gira el cuello | `look` |
| 13 | asiente | Gesto «sí» | `head_gesture` |
| 14 | niega | Gesto «no» | `head_gesture` |
| 15 | sígueme | Seguimiento | `follow` |
| 16 | para / quieto | Se detiene | `stop` |
| 17 | ven aquí | Se acerca | `go_to` |
| 18 | da una vuelta | Gira 360° | `rotate` |
| 19 | qué hora es | Dice la hora | |
| 20 | dato curioso | Dato curioso | |

### Añadir una orden

1. Añade un bloque en `05_ROS2/ros2_ws/src/udito_ros/config/intents.yaml` (`id`, `label`, `phrases`, `say`, `face` y, si mueve el cuerpo, `body`).
2. Si tiene `body`, añade su `name` al orquestador del cuerpo.
3. Reinicia con `./scripts/ros2/udito-ros.sh --build`. No hace falta tocar código.

---

## 8. Topics (implementación actual)

| Topic | Tipo | De → A |
|-------|------|--------|
| `/udito/power` | Bool | Consola → C.C. |
| `/udito/stt/ptt` | Bool | Consola → STT |
| `/udito/stt/text` | String | STT → C.C. |
| `/udito/stt/enable` | Bool | C.C. → STT |
| `/udito/tts/say` | String JSON `{id,text,emotion,laugh}` | C.C. → TTS |
| `/udito/tts/done` | String JSON `{id}` | TTS → C.C. |
| `/udito/speech_out` | String JSON `{emotion}` | C.C./TTS → cara |
| `/udito/state` | String JSON `{state, stt_sec}` | STT/TTS → consola |
| `/udito/intent` | String JSON `{name,args,intent,text}` | **C.C. → cuerpo** |
| `/udito/cc/log` | String | C.C. → consola |
| `/udito/cognitive/query` · `/answer` | String JSON | C.C. ↔ Cognitive |

### Para el responsable del cuerpo

El C.C. **no mueve motores**: publica la intención en `/udito/intent` y el orquestador del cuerpo la ejecuta.

```json
{"name": "follow", "args": {"target": "person"}, "intent": "follow_me", "text": "sígueme", "source": "udito_cc", "stamp": 1791238809.57}
```

Ejemplo listo para copiar: `05_ROS2/ros2_ws/src/udito_ros/udito_ros/body_example_node.py`.

---

## 9. Voz del robot

Archivo: `01_SERVICES/tts-engine/config/tts_config.json`

| Parámetro | Valor actual | Para qué sirve |
|-----------|--------------|----------------|
| `voice_model` | `es_ES-davefx-medium.onnx` | La voz (archivos en `tts-engine/piper/voices/`) |
| `length_scale` | `1.0` | Velocidad (menor = más rápido) |
| `noise_scale` | `0.667` | Expresividad de la entonación |
| `noise_w` | `0.8` | Variación del ritmo |
| `sentence_silence` | `0.3` | Pausa entre frases (segundos) |

---

## 10. Red y acceso remoto

| Interfaz | IP fija | Uso |
|----------|---------|-----|
| LAN (`eno1`) | `10.8.0.132/24`, GW `10.8.0.254` | Laboratorio OFC 309 y servidor del Cognitive |
| Wifi (`wlP1p1s0`) | `10.8.34.5/23`, GW `10.8.35.254` | Robot sin cables (requiere MAC registrada por TI) |

```powershell
ssh udito@10.8.0.132        # desde un PC del mismo segmento (10.8.0.x)
```

NoMachine: puerto `4000`. La red de la universidad bloquea el tráfico entre segmentos distintos.

---

## 11. Problemas frecuentes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| STT muy lento (>10 s) | Jetson en bajo consumo o `snapd` activo | Apartado 6.1 |
| No encuentra el micrófono `pulse` | Sesión gráfica como root | Elegir dispositivo ALSA `[A]` en `audio.sh` |
| `Exec format error` en Piper | Binario de PC en vez de ARM | `./scripts/setup/piper-jetson.sh` |
| Respuestas duplicadas | Dos instancias corriendo | `udito-ros.sh` ya cierra las anteriores |
| `ros2: command not found` | ROS no cargado | `source /opt/ros/humble/setup.bash` |

---

## 12. Flujo de trabajo Git

Ver [`GIT-FLOW.md`](GIT-FLOW.md). Trabajo en `feature/ros2-voice-orchestrator` → Pull Request a `develop` tras aprobación.

**Autor:** Danilo Guevara — ROBITA-lab, UDIT.
