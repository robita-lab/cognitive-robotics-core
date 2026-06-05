#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.venv"
UVICORN="$VENV/bin/uvicorn"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

if [[ ! -x "$UVICORN" ]]; then
  echo "Entorno no encontrado. Ejecuta primero: $ROOT/scripts/setup/venv.sh"
  exit 1
fi

start_one() {
  local name="$1" dir="$2" port="$3"
  echo "Iniciando $name en :$port"
  cd "$ROOT/01_SERVICES/$dir"
  nohup "$UVICORN" main:app --host 127.0.0.1 --port "$port" \
    >"$LOGDIR/${name}.log" 2>&1 &
  echo $! >"$LOGDIR/${name}.pid"
}

# RAG primero (tarda en indexar)
start_one rag-engine rag-engine 8004
sleep 2
start_one stt-engine stt-engine 8001
start_one tts-engine tts-engine 8002
echo "Iniciando wakeword-engine en :8003 (CPU)"
cd "$ROOT/01_SERVICES/wakeword-engine"
CUDA_VISIBLE_DEVICES="" nohup "$UVICORN" main:app --host 127.0.0.1 --port 8003 \
  >"$LOGDIR/wakeword-engine.log" 2>&1 &
echo $! >"$LOGDIR/wakeword-engine.pid"
start_one pipeline-orchestrator pipeline-orchestrator 8000

echo "Servicios iniciados. Logs en $LOGDIR"
echo "Estado: curl http://127.0.0.1:8000/services/status"
