# Scripts — Jetson offline

Solo lo esencial para **`./UDITO`** (wakeword → STT → RAG → TTS en la Jetson).

Modo servidor / online archivado en [`../_archive/modo-online/`](../_archive/modo-online/).

---

## Comandos (tú)

```bash
./UDITO                              # arrancar robot
./scripts/udito/audio-config.sh      # mic + altavoz → .env
./scripts/udito/face-sim.sh          # cara (2ª terminal)
./scripts/ros2/listener-wakeword.sh  # ROS2 (2ª terminal)
```

## Instalación (una vez)

**Solo en Jetson:**

```bash
./scripts/setup/jetson.sh              # incluye install_onnx_jetson.sh
./scripts/setup/models-download.sh
```

**Solo en PC de desarrollo (x86_64):**

```bash
./scripts/setup/venv.sh
./scripts/setup/install_onnx_pc.sh       # NO usar install_onnx_jetson.sh en PC
export ROBITA_WAKEWORD_CONFIG=config/wakeword.pc.json
```

Ver `01_SERVICES/wakeword-engine/config/README.md` (Jetson vs PC).

## Desarrollo PC → Jetson

```bash
./scripts/dev/sync-jetson.sh
```

---

## Estructura

| Carpeta | Contenido |
|---------|-----------|
| `udito/` | Arranque y audio del robot |
| `setup/` | venv, Piper, wakeword, modelos |
| `ros2/` | Listeners opcionales |
| `dev/` | Sincronizar a Jetson |
| `lib/` | **No ejecutar** — cadena interna de `./UDITO` |

Cadena interna:

```
./UDITO → udito/start.sh → lib/prepare-pipeline.sh → udito/run-standalone.sh
```
