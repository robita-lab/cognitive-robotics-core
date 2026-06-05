#!/usr/bin/env bash
# Preparación antes de lanzar UDITO: libera RAM y deja el proyecto limpio.
# Llamado desde Principal-UDITO.sh / udito-run.sh (desactivar: ROBITA_SKIP_PREPARE=1)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
[[ -f "$ROOT/scripts/lib/jetson-env.sh" ]] && source "$ROOT/scripts/lib/jetson-env.sh"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

: "${ROBITA_STOP_DOCKER:=1}"
: "${ROBITA_STOP_PIPELINE_PORTS:=1}"
: "${ROBITA_STOP_OLLAMA:=1}"
: "${ROBITA_CLEANUP_PROJECT:=1}"
: "${ROBITA_SYNC_FILECACHE:=0}"

echo ""
echo "════════════════════════════════════════"
echo "  Preparación Jetson — antes del pipeline"
echo "════════════════════════════════════════"

if [[ "${ROBITA_CLEANUP_PROJECT:-1}" == "1" ]]; then
  echo "→ Limpieza del árbol del proyecto..."
  bash "$ROOT/scripts/lib/cleanup-project.sh"
fi

if [[ "${ROBITA_STOP_PIPELINE_PORTS:-1}" == "1" ]]; then
  echo "→ Deteniendo pipeline previo (puertos 8000–8004)..."
  bash "$ROOT/scripts/lib/stop-services.sh" 2>/dev/null || true
fi

if [[ "${ROBITA_STOP_DOCKER:-1}" == "1" ]] && command -v docker >/dev/null; then
  if docker ps -q 2>/dev/null | grep -q .; then
    echo "→ Deteniendo contenedores Docker (liberan RAM)..."
    docker ps -q | xargs -r docker stop 2>/dev/null || true
  else
    echo "→ Docker: sin contenedores activos"
  fi
  if [[ -f "$ROOT/_archive/modo-online/docker-compose.yml" ]]; then
    docker compose -f "$ROOT/_archive/modo-online/docker-compose.yml" down 2>/dev/null || true
  fi
fi

_stop_ollama() {
  # Sin sudo interactivo (nunca pedir contraseña en el arranque)
  if systemctl is-active ollama >/dev/null 2>&1; then
    systemctl stop ollama 2>/dev/null \
      || sudo -n systemctl stop ollama 2>/dev/null \
      || true
  fi
  if pgrep -x ollama >/dev/null 2>&1; then
    pkill -x ollama 2>/dev/null || true
  fi
}

if [[ "${ROBITA_STOP_OLLAMA:-1}" == "1" ]]; then
  if systemctl is-active ollama >/dev/null 2>&1 || pgrep -x ollama >/dev/null 2>&1; then
    echo "→ Deteniendo ollama (sin pedir contraseña)..."
    _stop_ollama
  fi
fi

if [[ "${ROBITA_SYNC_FILECACHE:-0}" == "1" ]]; then
  echo "→ Sincronizando caché de disco..."
  sync
  if [[ -w /proc/sys/vm/drop_caches ]]; then
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
  else
    sudo -n sh -c 'echo 1 > /proc/sys/vm/drop_caches' 2>/dev/null || true
  fi
fi

# Comprobar RAM libre
if command -v free >/dev/null; then
  echo ""
  free -h | head -2
  avail=$(free -m | awk '/^Mem:/{print $7}')
  if [[ "${avail:-0}" -lt 1500 ]]; then
    echo ""
    echo "⚠ Poca RAM libre (${avail} MB). Cierra apps gráficas o reinicia antes del pipeline."
  fi
fi

echo ""
echo "Preparación lista."
echo ""
