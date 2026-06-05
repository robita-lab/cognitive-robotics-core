#!/usr/bin/env bash
# Terminal 1 — ejemplo ROS2: escucha wakeword y estado del pipeline offline.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -f /opt/ros/humble/setup.bash ]]; then
  # shellcheck source=/dev/null
  source /opt/ros/humble/setup.bash
elif [[ -f /opt/ros/jazzy/setup.bash ]]; then
  # shellcheck source=/dev/null
  source /opt/ros/jazzy/setup.bash
else
  echo "ROS2 no encontrado (/opt/ros/humble)."
  exit 1
fi

echo "UDITO ROS2 wakeword listener — /udito/wakeword, /udito/state"
echo "Archivo JSON (sin ROS2): /tmp/udito_wakeword.json"
echo "En otra terminal: ./scripts/udito/start.sh"
echo ""

exec python3 "$ROOT/05_ROS2/udito_wakeword_listener.py"
