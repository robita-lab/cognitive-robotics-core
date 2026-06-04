# Wakeword «udito» — plataformas

## Modelo entrenado (repo correcto)

El wakeword «udito» está en **[dguevaras/UDITO — WakeWord-project](https://github.com/dguevaras/UDITO/tree/master/WakeWord-project)**:

| Archivo | Formato |
|---------|---------|
| `wakeword_model.h5` | Keras (el entrenamiento real) |
| `Detector_wakeword.py` | Espera `wakeword_model.tflite` (no subido; se genera en Jetson) |

**No es un export openWakeWord `.onnx`** — es CNN + MFCC. En Jetson usamos `udito_mfcc` (tensorflow.lite tras convertir el `.h5`).

```bash
./scripts/fetch-wakeword-udito-repo.sh
export ROBITA_WAKEWORD_BACKEND=udito_mfcc   # ya es el default en .env
```

---

## Qué hay en GitHub (`cognitive-robotics-core`)

| Archivo | ¿En GitHub? | Notas |
|---------|-------------|--------|
| `micro_model.tflite` | Sí (~1 KB) | Antiguo export TFLite; en Jetson suele fallar con `tflite_runtime` + numpy 2 |
| `udito_model.net` | **No** | Aparece en `config/wake_word.json` pero **nunca se subió** al repo |
| `models/udito.onnx` | **No** | Export openWakeWord que debes añadir tú |

Descargar lo que sí está en GitHub:

```bash
./scripts/fetch-wakeword-from-github.sh
```

El modelo entrenado con openWakeWord debe copiarse manualmente a `models/udito.onnx` (o subirse al repo, idealmente con **Git LFS**).

---

## Por defecto en Jetson (este repo)

| Backend | Cuándo |
|---------|--------|
| **`udito_mfcc`** (default) | Modelo de [dguevaras/UDITO](https://github.com/dguevaras/UDITO/tree/master/WakeWord-project) |
| `openwakeword` | Solo si tienes un `models/udito.onnx` exportado aparte |

### openWakeWord (opcional)

En **NVIDIA Jetson** también puedes usar **[openWakeWord](https://github.com/dscripka/openWakeWord)** si tienes el `.onnx`:

| Elemento | Ruta / valor |
|----------|----------------|
| Código | `oww_detector.py` (usado vía `Detector_wakeword.py`) |
| Modelo custom entrenado | `models/udito.onnx` (export de tu entrenamiento OWW) |
| Modelos base (mel + embedding) | `models/openwakeword/*.onnx` |
| Setup | `./scripts/setup-wakeword-oww.sh` |
| Inferencia | **ONNX** (`onnxruntime`) — no usa `tflite_runtime` en Jetson |

Variables útiles (`.env`):

```bash
ROBITA_WAKEWORD_BACKEND=openwakeword
ROBITA_WAKEWORD_MODEL=/opt/robita-lab/01_SERVICES/wakeword-engine/models/udito.onnx
```

Umbrales: `config/wake_word_config.json`.

---

## Windows (no usar openWakeWord directamente)

En **Windows** el stack del laboratorio **no** usa openWakeWord en el pipeline de producción porque:

- El entorno Windows del repo se montó con **TensorFlow Lite** (`micro_model.tflite`).
- `tflite_runtime` en Windows encaja con ese flujo; en Jetson falla con numpy 2.x y no es el camino soportado.

| Plataforma | Motor wakeword | Modelo |
|------------|----------------|--------|
| **Jetson / Linux** (defecto) | **openWakeWord** | `models/udito.onnx` |
| **Windows** | **TFLite** | `micro_model.tflite` (ver `_archive/historial/wakeword-tflite/`) |

En Windows: entrenar/exportar para TFLite o copiar el `.tflite` histórico; **no** ejecutar `setup-wakeword-oww.sh` como sustituto sin adaptar el código.

Para portar un modelo OWW de Linux a Windows, re-exportar a `.tflite` y usar el detector TFLite legacy (no está en la ruta por defecto de `udito_standalone.py` en Jetson).

---

## Resumen

```
Jetson  → openWakeWord + udito.onnx   (DEFAULT en Principal-UDITO / udito_standalone)
Windows → TFLite + micro_model.tflite (legado; no mezclar con oww_detector.py)
```

Documentación Jetson: [DEPLOY_JETSON_OFFLINE.md](../../DEPLOY_JETSON_OFFLINE.md).
