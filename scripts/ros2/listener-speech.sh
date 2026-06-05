#!/usr/bin/env bash
# Terminal 1 — ejemplo ROS2: escucha lo que dice el pipeline offline.
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
  echo "ROS2 no encontrado (/opt/ros/humble)."
  exit 1
fi

echo "UDITO ROS2 listener — topic /udito/speech_out"
echo "En otra terminal: ./UDITO"
echo ""

exec python3 "$ROOT/05_ROS2/udito_speech_listener.py"
