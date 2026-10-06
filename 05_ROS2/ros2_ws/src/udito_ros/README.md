# Arquitectura 3T - UDITO

## ¿Qué es 3T?

**3T** (*Three-Tier*, «tres capas») es una arquitectura clásica de robótica que separa al robot en tres niveles, cada uno con una responsabilidad:

| Capa | En UDITO | Pregunta que responde | Analogía de empresa |
|------|----------|----------------------|---------------------|
| **Deliberativa** | Cognitive (RAG + LLM + memoria) | **¿QUÉ** hago o digo? | Dirección: decide la estrategia |
| **Ejecutiva / secuenciadora** | C.C. sobre **ROS 2** (orquestador) | **¿CÓMO** y en qué orden? | Jefe de proyecto: reparte y coordina |
| **Reactiva / control** | Sensores y actuadores (STT, TTS, rostro, cuello, base) | Ejecuta y percibe | Equipo operativo |

Regla: **las órdenes bajan** (Cognitive → C.C. → actuadores) y **los datos suben** (sensores → C.C. → Cognitive). Ningún actuador recibe órdenes del Cognitive directamente: **todo pasa por ROS 2**, que funciona como un bus de mensajes (publicación/suscripción), igual que un *Enterprise Service Bus*.

---

## Nodos del paquete `udito_ros`

| Nodo | Capa | Hace |
|------|------|------|
| `udito_stt` | Reactiva (sensor) | Micrófono → Whisper → publica texto |
| `udito_tts` | Reactiva (actuador) | Recibe orden → Piper habla → avisa al terminar |
| `udito_face` (`face-sim.sh`) | Reactiva (actuador) | Pantalla-rostro; reacciona a emociones |
| `udito_cc` | Ejecutiva (C.C.) | Decide intención y reparte órdenes |
| `udito_cognitive` | Deliberativa | Responde preguntas (respuestas fijas o RAG) |

Los motores **no se duplican**: los nodos importan Whisper, Piper y RAG desde `01_SERVICES/`.

## Contrato de topics

| Topic | Tipo | De → A |
|-------|------|--------|
| `/udito/stt/text` | String | STT → C.C. |
| `/udito/stt/enable` | Bool | C.C. → STT (cierra el micro mientras habla) |
| `/udito/tts/say` | String JSON `{id,text,emotion,laugh}` | C.C. → TTS |
| `/udito/tts/done` | String JSON `{id}` | TTS → C.C. |
| `/udito/speech_out` | String JSON `{emotion,...}` | C.C./TTS → rostro |
| `/udito/state` | String JSON `{state}` | STT/TTS → rostro |
| `/udito/intent` | String JSON `{name,text,args}` | C.C. → cuerpo (cuello/base, futuro) |
| `/udito/cognitive/query` | String JSON `{id,text}` | C.C. → Cognitive |
| `/udito/cognitive/answer` | String JSON `{id,text,emotion}` | Cognitive → C.C. |

## Intenciones directas (sin IA, respuesta inmediata)

| Dices | Intención | Qué hace |
|-------|-----------|----------|
| «cuéntame un chiste» | `joke` | Chiste + risa |
| «ríete» | `laugh` | Cara de risa + sonido de risa |
| «mueve los ojos» | `move_eyes` | Ciclo de ojos en pantalla + frase |
| «dato curioso» | `curious_fact` | Dato curioso |
| «pon cara triste/alegre…» | `face_expression` | Cambia el rostro |
| «para» / «silencio» | `stop` | Se detiene |
| cualquier otra cosa | `ask_cognitive` | Pregunta al Cognitive |

## Ejecutar (Jetson / Ubuntu 22.04)

```bash
cd /opt/robita-lab
./scripts/setup/ros2-humble.sh     # solo si no hay ROS 2 Humble
./scripts/setup/jetson.sh          # motores IA (.venv), si no está hecho
./scripts/ros2/udito-ros.sh        # compila y lanza todo
```

Opciones: `rag:=true` · `mic:=false` · `face:=false` · `wake_word:=udito` · `--build`

## Probar sin micrófono (otra terminal)

```bash
source /opt/ros/humble/setup.bash
ros2 topic pub --once /udito/stt/text std_msgs/String "{data: 'cuéntame un chiste'}"
ros2 topic pub --once /udito/stt/text std_msgs/String "{data: 'mueve los ojos'}"
ros2 topic echo /udito/intent
```
