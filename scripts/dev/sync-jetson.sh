#!/usr/bin/env bash
# Sincroniza código (wakeword + robot + scripts) a la Jetson y ejecuta setup mínimo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${ROBITA_JETSON_HOST:-10.8.0.16}"
USER="${ROBITA_JETSON_USER:-udito}"
DEST="${ROBITA_JETSON_PATH:-/opt/robita-lab}"
SSH="${ROBITA_JETSON_SSH:-$USER@$HOST}"

echo "==> Sync develop → Jetson ($SSH:$DEST)"

RSYNC_EXCLUDES=(
  --exclude '.git'
  --exclude '.venv'
  --exclude 'ww2/'
  --exclude 'WakeWord-Project/'
  --exclude 'data/huggingface/'
  --exclude '01_SERVICES/rag-engine/data/rag_cache/'
  --exclude 'token_github.txt'
  --exclude '__pycache__/'
  --exclude '*.pyc'
)

rsync -avz --delete "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/01_SERVICES/wakeword-engine/" \
  "$SSH:$DEST/01_SERVICES/wakeword-engine/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/03_ADAPTERS/robot-udit-physical/" \
  "$SSH:$DEST/03_ADAPTERS/robot-udit-physical/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/05_ROS2/" \
  "$SSH:$DEST/05_ROS2/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/scripts/udito/" \
  "$SSH:$DEST/scripts/udito/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/scripts/setup/" \
  "$SSH:$DEST/scripts/setup/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/scripts/ros2/" \
  "$SSH:$DEST/scripts/ros2/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/scripts/lib/" \
  "$SSH:$DEST/scripts/lib/"

rsync -avz "${RSYNC_EXCLUDES[@]}" \
  "$ROOT/scripts/README.md" \
  "$SSH:$DEST/scripts/README.md"

rsync -avz "$ROOT/UDITO" "$SSH:$DEST/UDITO"

if [[ -f "$ROOT/.env.example" ]]; then
  rsync -avz "$ROOT/.env.example" "$SSH:$DEST/.env.example"
fi

echo ""
echo "==> Setup remoto (venv + openWakeWord)…"
ssh "$SSH" "cd '$DEST' && find scripts -name '*.sh' -exec chmod +x {} + && chmod +x UDITO && ./scripts/setup/wakeword.sh"

echo ""
echo "==> Comprobar ROS2 en Jetson…"
ssh "$SSH" "bash -lc '
  if [[ -f /opt/ros/humble/setup.bash ]]; then source /opt/ros/humble/setup.bash; fi
  if command -v ros2 >/dev/null; then ros2 daemon status || true; else echo ROS2 no instalado; fi
  cd \"$DEST\" && .venv/bin/python -c \"
import sys
sys.path.insert(0,\\\"01_SERVICES/wakeword-engine\\\")
from engine import load
from ros2_bridge import probe_ros2, is_ros2_active
load()
print(\\\"wakeword OK\\\")
print(\\\"ros2_active=\\\", is_ros2_active())
\"
'"

echo ""
echo "Listo. En la Jetson:"
echo "  Terminal 1: cd $DEST && ./scripts/ros2/listener-wakeword.sh"
echo "  Terminal 2: cd $DEST && ./UDITO"
