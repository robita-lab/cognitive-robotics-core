# Pantalla de UDITO (ojos) — simulación y hardware

UDITO tiene **cabeza (pantalla/ojos)**, **cuello (servos)** y **ruedas**. Este documento cubre la **cara en pantalla**; cuello y ruedas van después por ROS2.

## Comandos de voz directos (20 expresiones)

Tras «udito», puedes pedir la cara **sin RAG** (ver `04_KNOWLEDGE_CORE/responses/face_commands.json`):

- «¿Cómo es una cara triste?», «sonríe», «guiña un ojo», «saca la lengua», «cara sorprendida», etc.

El pipeline detecta la frase, actualiza el JSON y la pantalla cambia al instante.

## Idea

Un solo módulo dibuja la cara según la **expresión** del pipeline o del comando:

| Origen | Dato |
|--------|------|
| `udito_speech.py` | Escribe `/tmp/udito_speech_out.json` y topic `/udito/speech_out` |
| Simulador | Lee ese JSON y abre una **ventana** (pygame) |
| Pantalla real (futuro) | Mismo dibujo, otro backend (`framebuffer`, SPI, etc.) |

Así lo que ves en la ventana es lo que debería verse en la pantalla del robot cuando esté conectada.

## Requisitos (simulación)

```bash
sudo apt install -y python3-pygame   # o pip install pygame en .venv
# Pantalla HDMI / escritorio activo
export DISPLAY=:0
```

En la Jetson con monitor:

```bash
cd /opt/robita-lab

# Terminal 1 — cara + wakeword (ROS2)
./scripts/ros2/listener-wakeword.sh

# Terminal 2 — pipeline
./UDITO
```

Cuando UDITO hable, la ventana cambia de emoción (`happy`, `thinking`, `sorry`, `laugh`, …).

### Probar sin pipeline

En la ventana del simulador:

| Tecla | Emoción |
|-------|---------|
| 1 | happy |
| 2 | sorry |
| 3 | thinking |
| 4 | laugh |
| 5 | idle |
| 6 | listening |
| 7 | helpful |

## Variables

| Variable | Default | Uso |
|----------|---------|-----|
| `ROBITA_FACE_BACKEND` | `sim` | `sim` = ventana; luego `fb` / `spi` |
| `ROBITA_FACE_WIDTH` | `480` | Ancho ventana sim |
| `ROBITA_FACE_HEIGHT` | `320` | Alto ventana sim |
| `ROBITA_SPEECH_EVENT_FILE` | `/tmp/udito_speech_out.json` | Mismo archivo que ROS2/voz |

## Conexión con ROS2 (opcional)

Si `ROBITA_ROS2_SPEECH=1` y `rclpy` instalado, el JSON también va a `/udito/speech_out`. Un nodo ROS2 puede:

1. Suscribirse al topic y llamar a la misma lógica de dibujo, o  
2. Seguir leyendo el JSON (más simple para pruebas).

Topic futuro recomendado: `/udito/state` (`idle`, `listening`, `thinking`, `speaking`).

## Pantalla física (siguiente paso)

Cuando tengas el driver de la pantalla del robot:

1. Implementar `FramebufferFaceDisplay` en `udito_face.py` (misma API que `PygameFaceSim`).
2. `export ROBITA_FACE_BACKEND=framebuffer`
3. Resolución igual que en sim (`480x320`) para que coincida pixel a pixel.

## Cuello y ruedas (después)

| Componente | Topic / acción sugerido |
|------------|-------------------------|
| Cuello | `/udito/neck/cmd` — inclinación según emoción |
| Ruedas | `/cmd_vel` — solo nodos de navegación |

La cara reacciona a **voz**; el cuello puede inclinarse en `listening` / `thinking`.

## Archivos

- `udito_face.py` — dibujo y simulador
- `scripts/udito/face-sim.sh` — arranque
- `SPEECH_ROS2.md` — emociones y JSON de voz
