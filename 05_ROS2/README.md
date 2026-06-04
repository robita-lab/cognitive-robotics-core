# ROS2 + UDITO (Jetson offline)

UDITO offline publica cada frase hablada con **emoción** y **texto**. Otros nodos (cara, cuello, ruedas) pueden reaccionar sin tocar el pipeline de voz.

| Documento | Contenido |
|-----------|-----------|
| [SPEECH_ROS2.md](../03_ADAPTERS/robot-udit-physical/SPEECH_ROS2.md) | JSON, emociones, topic `/udito/speech_out` |
| [FACE_DISPLAY.md](../03_ADAPTERS/robot-udit-physical/FACE_DISPLAY.md) | Ventana pygame (ojos) |
| [DEPLOY_JETSON_OFFLINE.md](../DEPLOY_JETSON_OFFLINE.md) | Instalación Jetson |

---

## Por qué dos terminales

El pipeline (`Principal-UDITO`) es **pesado y en tiempo real** (micrófono, wakeword, STT). La **cara** o un **listener ROS2** necesitan un bucle aparte (ventana 30 fps o `rclpy.spin`).

| Terminal | Proceso | Qué hace |
|----------|---------|----------|
| **1** | Cara sim **o** listener ROS2 | Muestra ojos / imprime emociones |
| **2** | `Principal-UDITO.sh` | Wakeword → STT → RAG → TTS |

Si todo va en una sola terminal, la ventana pygame o ROS2 compiten con el audio y es más difícil depurar.

---

## Ejemplo A — Pantalla simulada (sin depender del daemon ROS2)

La cara lee el mismo JSON que escribe la voz (`/tmp/udito_speech_out.json`). **No hace falta** `ros2 daemon` para este ejemplo.

```bash
cd /opt/robita-lab

# Terminal 1 — ventana con ojos
./scripts/udito-face-sim.sh

# Terminal 2 — pipeline offline
./scripts/Principal-UDITO.sh
```

Di «udito», pregunta algo: en la **ventana** cambian los ojos (`happy`, `thinking`, `sorry`, …).

---

## Ejemplo B — ROS2 puro (listener en terminal 1)

Requiere ROS2 Humble instalado (`/opt/ros/humble`).

```bash
cd /opt/robita-lab

# Terminal 1 — suscriptor ROS2
./scripts/udito-ros2-listener.sh

# Terminal 2 — pipeline (publica en /udito/speech_out si rclpy OK)
export ROBITA_ROS2_SPEECH=1   # por defecto ya es 1
./scripts/Principal-UDITO.sh
```

En terminal 1 verás líneas como:

```text
[helpful] rag — Claro, la biblioteca abre de lunes a viernes…
```

Comprobar el topic a mano:

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /udito/speech_out
```

---

## Ejemplo C — Solo pipeline (una terminal)

```bash
./scripts/Principal-UDITO.sh
```

Sigue escribiendo `/tmp/udito_speech_out.json`. Sin cara ni ROS2 hasta que abras otro proceso.

---

## Qué publica el pipeline (offline)

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

---

## Siguientes pasos (cuello y ruedas)

| Componente | Topic sugerido | Quién publica |
|------------|----------------|---------------|
| Estado | `/udito/state` | Pipeline (`idle`, `listening`, `thinking`, `speaking`) — pendiente |
| Cuello | `/udito/neck/cmd` | Nodo que escucha emoción/estado |
| Ruedas | `/cmd_vel` | Nodo navegación (fuera del pipeline de voz) |

La pantalla física del robot usará el mismo dibujo que `udito_face.py` con otro backend (`ROBITA_FACE_BACKEND=framebuffer`).

---

## Archivos de este ejemplo

| Archivo | Uso |
|---------|-----|
| `05_ROS2/udito_speech_listener.py` | Nodo ejemplo terminal 1 |
| `scripts/udito-ros2-listener.sh` | Arranque con `source` ROS2 |
| `scripts/udito-face-sim.sh` | Ejemplo A (ventana) |
