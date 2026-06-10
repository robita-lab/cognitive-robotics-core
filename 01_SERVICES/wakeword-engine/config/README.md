# Configuración wakeword — Jetson vs PC

| Archivo | Plataforma | `wake_provider` | Uso |
|---------|------------|-----------------|-----|
| `wakeword.json` | **Jetson** (producción) | `cuda` | Default del robot y UDITO |
| `wakeword.pc.json` | **PC** x86_64 (desarrollo) | `cpu` | Pruebas locales, entrenamiento, calibración aproximada |

## Jetson

```bash
./scripts/setup/install_onnx_jetson.sh
.venv/bin/python 01_SERVICES/wakeword-engine/check_env.py
```

Usa `config/wakeword.json` (sin variables extra).

## PC de desarrollo

```bash
./scripts/setup/install_onnx_pc.sh          # CPU
# ./scripts/setup/install_onnx_pc.sh --gpu  # opcional, si tienes CUDA x86_64

export ROBITA_WAKEWORD_CONFIG=config/wakeword.pc.json
.venv/bin/python 01_SERVICES/wakeword-engine/check_env.py
```

**No ejecutes** `install_onnx_jetson.sh` en el PC — desinstala onnxruntime e intenta un wheel ARM64.

La calibración final del `wake_threshold` debe hacerse en la Jetson con el micrófono del robot.
