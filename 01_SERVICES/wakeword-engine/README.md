# Wakeword «udito» — OpenWakeWord + ONNX

## Arquitectura

```
config/wakeword.json   ← toda la configuración (modelo, audio, umbrales)
engine.py              ← clase WakeWordEngine (lee JSON, inferencia)
Detector_wakeword.py   ← entrada del robot (reexporta engine)
models/
  udito.onnx           ← modelo entrenado (no en git; copiar manualmente)
  openwakeword/        ← melspectrogram.onnx + embedding_model.onnx (auto-descarga)
main.py                ← API HTTP opcional (/detect, /stream)
```

El robot (`03_ADAPTERS/robot-udit-physical/`) importa `Detector_wakeword as ww` y lee umbrales de detección desde este JSON. La configuración de grabación/VAD/speaker-lock está en `03_ADAPTERS/robot-udit-physical/config/session.json`.

## Configuración (`config/wakeword.json`)

| Sección | Campos | Uso |
|---------|--------|-----|
| `wake_word` | nombre | Clave esperada en predicciones OWW |
| `model` | `path`, `framework`, `vad_threshold`, `base_models_dir` | Ruta al ONNX y modelos base |
| `audio` | `sample_rate`, `chunk_ms`, `voice_energy_min` | Formato de audio del micrófono |
| `detection` | `wakeword_threshold`, `hits_required`, `cool_down_sec`, `wakeword_rel_spike_min`, … | Umbrales usados por `robot_common.py` |
| `ros2` | `enabled`, `topic_wakeword`, `topic_state`, `event_file` | Publicación ROS2 al detectar «udito» |

Edita solo el JSON. No hay umbrales en el código Python.

## ROS2

Al cargar el motor (`engine.load()`), el módulo comprueba si ROS2 está activo (`rclpy` + opcional `require_daemon`).

| Topic | Evento |
|-------|--------|
| `/udito/wakeword` | Wakeword detectado (JSON: probabilidad, margen, `ros2_active`) |
| `/udito/state` | `wakeword_listening`, `wakeword_detected`, `session_listening`, `idle` |

Sin ROS2: escribe `/tmp/udito_wakeword.json` (mismo patrón que la voz).

Listener de prueba (Jetson, terminal 1):

```bash
./scripts/ros2/listener-wakeword.sh
```

## Instalación del modelo

Copia tu modelo entrenado:

```bash
cp /ruta/a/udito.onnx 01_SERVICES/wakeword-engine/models/udito.onnx
```

Descarga modelos base OpenWakeWord (primera vez):

```bash
./scripts/setup/wakeword.sh
```

## Probar carga

```bash
cd /opt/robita-lab
source .venv/bin/activate
python -c "
import sys; sys.path.insert(0,'01_SERVICES/wakeword-engine')
from engine import load; load(); print('OK')
"
```

## Dependencias

Ver `requirements.txt`. En PC (Python 3.12, solo ONNX):

```bash
pip install onnxruntime 'numpy<2.1'
pip install --no-deps 'openwakeword>=0.6.0'
```

`vad_threshold` en JSON debe ser `0` (VAD lo hace el robot en `session.json`). Si subes el umbral OWW, copia `silero_vad.onnx` a `openwakeword/resources/models/` o usa `./scripts/setup/wakeword.sh`.
