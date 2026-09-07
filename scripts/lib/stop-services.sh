#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGDIR="$ROOT/logs"
for f in "$LOGDIR"/*.pid; do
  [[ -f "$f" ]] || continue
  kill "$(cat "$f")" 2>/dev/null || true
done
for port in 8000 8001 8002 8003 8004; do
  pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
done
echo "Pipeline detenido."
