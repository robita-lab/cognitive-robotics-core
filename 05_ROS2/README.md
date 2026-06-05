# ROS2 + UDITO (Jetson offline)

UDITO offline publica cada frase hablada con **emoción** y **texto**. Otros nodos (cara, cuello, ruedas) pueden reaccionar sin tocar el pipeline de voz.

| Documento | Contenido |
|-----------|-----------|
| [SPEECH_ROS2.md](../03_ADAPTERS/robot-udit-physical/SPEECH_ROS2.md) | JSON, emociones, topic `/udito/speech_out` |
| [FACE_DISPLAY.md](../03_ADAPTERS/robot-udit-physical/FACE_DISPLAY.md) | Ventana pygame (ojos) |
| [DEPLOY_JETSON_OFFLINE.md](../DEPLOY_JETSON_OFFLINE.md) | Instalación Jetson |

---

## Por qué dos terminales

El pipeline (`udito/start.sh`) es **pesado y en tiempo real** (micrófono, wakeword, STT). La **cara** o un **listener ROS2** necesitan un bucle aparte (ventana 30 fps o `rclpy.spin`).

| Terminal | Proceso | Qué hace |
|----------|---------|----------|
| **1** | Cara sim **o** listener ROS2 | Muestra ojos / imprime emociones |
| **2** | `scripts/udito/start.sh` | Wakeword → STT → RAG → TTS |

Si todo va en una sola terminal, la ventana pygame o ROS2 compiten con el audio y es más difícil depurar.

---

## Ejemplo A — Pantalla simulada (sin depender del daemon ROS2)

La cara lee el mismo JSON que escribe la voz (`/tmp/udito_speech_out.json`). **No hace falta** `ros2 daemon` para este ejemplo.

```bash
cd /opt/robita-lab

# Terminal 1 — ventana con ojos
./scripts/udito/face-sim.sh

# Terminal 2 — pipeline offline
./scripts/udito/start.sh
```

Di «udito», pregunta algo: en la **ventana** cambian los ojos (`happy`, `thinking`, `sorry`, …).

---

## Ejemplo B — ROS2 puro (listener en terminal 1)

Requiere ROS2 Humble instalado (`/opt/ros/humble`).

```bash
cd /opt/robita-lab

# Terminal 1 — suscriptor ROS2
./scripts/ros2/listener-speech.sh

# Terminal 2 — pipeline (publica en /udito/speech_out si rclpy OK)
export ROBITA_ROS2_SPEECH=1   # por defecto ya es 1
./scripts/udito/start.sh
```

En terminal 1 verás líneas como:

```text
[helpful] rag — Claro, la biblioteca abre de lunes a viernes…
```

---

## Prueba wakeword (2 terminales)

**Terminal 1** — ROS2 + ventana de cara:

```bash
./scripts/ros2/listener-wakeword.sh
```

**Terminal 2** — micrófono + wakeword:

```bash
./UDITO
```

La cara pasa a `listening` al detectar «udito» (`/tmp/udito_wakeword.json` o topics ROS2).

Comprobar el topic a mano:

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /udito/speech_out
```

---

## Ejemplo C — Solo pipeline (una terminal)

```bash
./scripts/udito/start.sh
```

Sigue escribiendo `/tmp/udito_speech_out.json`. Sin cara ni ROS2 hasta que abras otro proceso.

---

## Qué publica el pipeline (offline)

### Voz (TTS / RAG)

**Topic:** `/udito/speech_out` (`std_msgs/String`, cuerpo = JSON)

```json
{
  "text": "Claro, la biblioteca…",
  "emotion": "helpful",
  "source": "rag",
  "label": "rag",
  "segments": [ … ]
}
```

**Archivo:** `ROBITA_SPEECH_EVENT_FILE` (default `/tmp/udito_speech_out.json`)

Variables: `ROBITA_ROS2_SPEECH=1` (publicar ROS2), `0` para desactivar solo el topic.

### Wakeword

Config en `01_SERVICES/wakeword-engine/config/wakeword.json` → sección `ros2`.

**Topics:**

| Topic | Cuándo |
|-------|--------|
| `/udito/wakeword` | Se detecta «udito» |
| `/udito/state` | Cambia el estado del bucle (`wakeword_listening`, `session_listening`, `idle`, …) |

**Archivo (sin ROS2):** `/tmp/udito_wakeword.json`

Prueba en terminal 1:

```bash
./scripts/ros2/listener-wakeword.sh
```

El JSON de cada evento incluye `"ros2_active": true|false` para que otros nodos sepan si la publicación ROS2 está viva.

---

## Siguientes pasos (cuello y ruedas)

| Componente | Topic sugerido | Quién publica |
|------------|----------------|---------------|
| Wakeword | `/udito/wakeword` | Pipeline (al detectar «udito») |
| Estado | `/udito/state` | Pipeline (`idle`, `wakeword_listening`, `session_listening`, …) |
| Cuello | `/udito/neck/cmd` | Nodo que escucha emoción/estado |
| Ruedas | `/cmd_vel` | Nodo navegación (fuera del pipeline de voz) |

La pantalla física del robot usará el mismo dibujo que `udito_face.py` con otro backend (`ROBITA_FACE_BACKEND=framebuffer`).

---

## Archivos de este ejemplo

| Archivo | Uso |
|---------|-----|
| `05_ROS2/udito_wakeword_listener.py` | Listener consola (debug, sin ventana) |
| `scripts/ros2/listener-wakeword.sh` | T1 prueba wakeword: ROS2 + cara (`face-sim --wakeword`) |
| `scripts/udito/face-sim.sh` | Ventana ojos (`--wakeword` = modo wakeword) |
