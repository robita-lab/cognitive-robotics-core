#!/usr/bin/env bash
# Terminal 1 — ROS2 + simulador de cara (espera wakeword). Terminal 2: ./UDITO
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -f /opt/ros/humble/setup.bash ]]; then
  set +u
  # shellcheck source=/dev/null
  source /opt/ros/humble/setup.bash
  set -u
elif [[ -f /opt/ros/jazzy/setup.bash ]]; then
  set +u
  # shellcheck source=/dev/null
  source /opt/ros/jazzy/setup.bash
  set -u
else
  echo "Aviso: ROS2 no encontrado — la cara seguirá leyendo /tmp/udito_wakeword.json"
fi

if command -v ros2 >/dev/null 2>&1; then
  ros2 daemon status 2>/dev/null | grep -q "is running" || ros2 daemon start 2>/dev/null || true
fi

exec "$ROOT/scripts/udito/face-sim.sh" --wakeword
