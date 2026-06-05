#!/usr/bin/env bash
# Lanza el pipeline completo Robita-Lab y espera hasta que esté listo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
VENV="$ROOT/.venv"
UVICORN="$VENV/bin/uvicorn"
LOGDIR="$ROOT/logs"
PORTS=(8004 8001 8002 8003 8000)
NAMES=(rag-engine stt-engine tts-engine wakeword-engine pipeline-orchestrator)
MAX_WAIT=180

mkdir -p "$LOGDIR"

if [[ ! -x "$UVICORN" ]]; then
  echo "Creando entorno virtual..."
  bash "$ROOT/scripts/setup/venv.sh"
fi

stop_port() {
  local port="$1"
  local pid
  pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
}

echo "==> Deteniendo instancias previas..."
for port in "${PORTS[@]}"; do stop_port "$port"; done

start_service() {
  local name="$1" port="$2" extra_env="${3:-}"
  echo "==> Iniciando $name en :$port"
  cd "$ROOT/01_SERVICES/$name"
  # shellcheck disable=SC2086
  env $extra_env nohup "$UVICORN" main:app --host 127.0.0.1 --port "$port" \
    >"$LOGDIR/${name}.log" 2>&1 &
  echo $! >"$LOGDIR/${name}.pid"
}

start_service rag-engine 8004
sleep 3
start_service stt-engine 8001
start_service tts-engine 8002
start_service wakeword-engine 8003 "CUDA_VISIBLE_DEVICES="
start_service pipeline-orchestrator 8000

echo "==> Esperando servicios (RAG puede tardar hasta ${MAX_WAIT}s la primera vez)..."
elapsed=0
while (( elapsed < MAX_WAIT )); do
  up=0
  for port in "${PORTS[@]}"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:${port}/health" 2>/dev/null || echo 000)
    [[ "$code" == "200" ]] && up=$((up + 1))
  done
  if [[ "$up" -eq 5 ]]; then
    if curl -sf --max-time 5 http://127.0.0.1:8000/services/status | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      echo ""
      echo "=========================================="
      echo "  PIPELINE LISTO — http://127.0.0.1:8000"
      echo "=========================================="
      curl -s http://127.0.0.1:8000/services/status | python3 -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8000/services/status
      echo ""
      echo "Prueba rápida:"
      echo '  curl -X POST http://127.0.0.1:8000/text-query -H "Content-Type: application/json" -d '"'"'{"text":"Hola"}'"'"''
      echo "Logs: $LOGDIR/"
      exit 0
    fi
  fi
  printf "\r  %d/%ds — servicios up: %d/5" "$elapsed" "$MAX_WAIT" "$up"
  sleep 5
  elapsed=$((elapsed + 5))
done

echo ""
echo "ERROR: timeout esperando servicios. Revisa logs en $LOGDIR/"
tail -20 "$LOGDIR/rag-engine.log" 2>/dev/null || true
exit 1
