#!/usr/bin/env bash
# Muestra dónde corre UDITO: en ESTE equipo y (opcional) en la Jetson.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${ROBITA_JETSON_HOST:-10.8.0.16}"
USER="${ROBITA_JETSON_USER:-udito}"
SSH="${ROBITA_JETSON_SSH:-$USER@$HOST}"

_check_host() {
  local label="$1"
  echo "── $label ($(hostname)) ──"
  if pgrep -f '\.venv/bin/python -u .*udito_standalone\.py' >/dev/null 2>&1; then
    pgrep -af '\.venv/bin/python -u .*udito_standalone\.py' || true
  else
    echo "  UDITO (./UDITO):        NO corre"
  fi
  if pgrep -f 'udito_face\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_face\.py' || true
  else
    echo "  Cara sim (face-sim):  NO corre"
  fi
  if pgrep -f 'udito_wakeword_listener\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_wakeword_listener\.py' || true
  else
    echo "  ROS2 listener wakeword: NO corre"
  fi
  if pgrep -f 'udito_speech_listener\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_speech_listener\.py' || true
  else
    echo "  ROS2 listener voz:      NO corre"
  fi
  echo ""
}

echo "Repo: $ROOT"
echo ""

_check_host "ESTE PC"

if [[ "${1:-}" != "--local" ]]; then
  if ssh -o BatchMode=yes -o ConnectTimeout=3 "$SSH" 'true' 2>/dev/null; then
    ssh "$SSH" "bash -s" <<'EOF'
check() {
  if pgrep -f '\.venv/bin/python -u .*udito_standalone\.py' >/dev/null 2>&1; then
    pgrep -af '\.venv/bin/python -u .*udito_standalone\.py' || true
  else
    echo "  UDITO (./UDITO):        NO corre"
  fi
  if pgrep -f 'udito_face\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_face\.py' || true
  else
    echo "  Cara sim (face-sim):  NO corre"
  fi
  if pgrep -f 'udito_wakeword_listener\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_wakeword_listener\.py' || true
  else
    echo "  ROS2 listener wakeword: NO corre"
  fi
  if pgrep -f 'udito_speech_listener\.py' >/dev/null 2>&1; then
    pgrep -af 'udito_speech_listener\.py' || true
  else
    echo "  ROS2 listener voz:      NO corre"
  fi
}
echo "── JETSON ($(hostname) @ $(hostname -I 2>/dev/null | awk '{print $1}')) ──"
check
EOF
    echo ""
  else
    echo "── JETSON ($SSH) ──"
    echo "  (sin SSH — solo comprobado este PC)"
    echo ""
  fi
fi

cat <<'HELP'

Regla:
  • Lo que lanzo yo con ssh udito@10.8.0.16 … corre EN LA JETSON (robot real).
  • ./UDITO en tu terminal de udito-309 corre EN ESTE PC (sin mic del robot).
  • Para el robot real, usa SSH a la Jetson (no el ./UDITO de este PC).

Arrancar en Jetson:
  ssh -t udito@10.8.0.16 'cd /opt/robita-lab && ./UDITO'

Parar en Jetson:
  ssh udito@10.8.0.16 'pkill -f udito_standalone.py; pkill -f udito_wakeword_listener.py'

HELP
