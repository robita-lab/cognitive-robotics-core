#!/usr/bin/env bash
# Arquitectura 3T - UDITO · Compila (si hace falta) y lanza voz + C.C. + Cognitive sobre ROS 2.
#
#   ./scripts/ros2/udito-ros.sh                 # arranca (compila la primera vez)
#   ./scripts/ros2/udito-ros.sh --build         # fuerza recompilar
#   ./scripts/ros2/udito-ros.sh rag:=true       # con RAG completo
#   ./scripts/ros2/udito-ros.sh mic:=false      # sin micrófono (pruebas por texto)
#   ./scripts/ros2/udito-ros.sh wake_word:=udito
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROBITA_ROOT="$ROOT"
WS="$ROOT/05_ROS2/ros2_ws"

# 1) ROS 2
if [[ -f /opt/ros/humble/setup.bash ]]; then
  source /opt/ros/humble/setup.bash
else
  echo "ROS 2 Humble no encontrado. Instálalo con: ./scripts/setup/ros2-humble.sh"; exit 1
fi
command -v colcon >/dev/null || { echo "Falta colcon: sudo apt install -y python3-colcon-common-extensions"; exit 1; }

# 2) Motores de IA (venv del repo: Whisper, Piper, RAG)
VENV_SP="$(ls -d "$ROOT"/.venv/lib/python3*/site-packages 2>/dev/null | head -1 || true)"
[[ -n "$VENV_SP" ]] || { echo "Falta .venv — ejecuta ./scripts/setup/jetson.sh"; exit 1; }
if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env" || true; set +a; fi
# Jetson: mismas variables que el modo standalone (modelos en data/huggingface, bajo consumo)
[[ "$(uname -m)" == "aarch64" && -f "$ROOT/scripts/lib/jetson-env.sh" ]] && source "$ROOT/scripts/lib/jetson-env.sh"

# Una sola instancia: si quedó otra corriendo, se cierra (evita respuestas duplicadas)
pkill -f "lib/udito_ros/" 2>/dev/null || true
pkill -f "udito_face.py" 2>/dev/null || true
sleep 1

# 3) Compilar solo nuestro paquete
BUILD=0
ARGS=()
for a in "$@"; do
  if [[ "$a" == "--build" ]]; then BUILD=1; else ARGS+=("$a"); fi
done
cd "$WS"
if [[ $BUILD -eq 1 || ! -d install/udito_ros ]]; then
  colcon build --packages-select udito_ros --symlink-install
fi
source install/setup.bash

# 4) Lanzar
export PYTHONPATH="$VENV_SP:${PYTHONPATH:-}"
export ROBITA_ROS2_SPEECH=0
export DISPLAY="${DISPLAY:-:0}"
exec ros2 launch udito_ros udito_voice.launch.py "${ARGS[@]}"
