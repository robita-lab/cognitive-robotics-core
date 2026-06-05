#!/usr/bin/env bash
# Monitor en vivo: edge + cerebro + salud de servicios
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p logs

echo "══════════════════════════════════════════════"
echo "  UDITO — monitor (Ctrl+C para salir)"
echo "══════════════════════════════════════════════"
echo "  Log edge:     logs/robot-edge.log"
echo "  Log cerebro:  logs/pipeline-orchestrator.log"
echo ""
echo "  Arrancar edge en otra terminal:"
echo "    ./scripts/server/robot-edge.sh"
echo "══════════════════════════════════════════════"
echo ""

status_once() {
  local up=0 code
  for p in 8000 8001 8002 8003 8004; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://127.0.0.1:${p}/health" 2>/dev/null || echo 000)
    [[ "$code" == "200" ]] && up=$((up + 1))
  done
  echo "[$(date +%H:%M:%S)] cerebro: ${up}/5 servicios OK"
}

status_once

# Estado cada 30s en segundo plano
(
  while true; do
    sleep 30
    status_once
  done
) &
STATUS_PID=$!
trap 'kill "$STATUS_PID" 2>/dev/null; exit' INT TERM

touch logs/robot-edge.log logs/pipeline-orchestrator.log
tail -n 5 -F logs/robot-edge.log logs/pipeline-orchestrator.log 2>/dev/null
