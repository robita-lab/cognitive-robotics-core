#!/usr/bin/env bash
# Resumen rápido: procesos, puertos y últimas líneas del log
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "── Procesos ──"
pgrep -af "udito\.py|udito_standalone" 2>/dev/null || echo "(ningún cliente UDITO)"
pgrep -af "uvicorn.*8000" 2>/dev/null | head -1 || echo "(orquestador no activo)"

echo ""
echo "── Salud HTTP ──"
for p in 8000 8001 8002 8003 8004; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:${p}/health" 2>/dev/null || echo 000)
  echo "  :$p  HTTP $code"
done

echo ""
echo "── .env audio ──"
grep -E '^ROBITA_' .env 2>/dev/null || echo "(sin .env)"

echo ""
echo "── Últimas 15 líneas edge ──"
tail -15 logs/robot-edge.log 2>/dev/null || echo "(sin log)"
