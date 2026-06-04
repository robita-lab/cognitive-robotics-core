#!/usr/bin/env bash
# Arranque con elección online / offline (avanzado).
# En Jetson sin servidor usa el comando principal: ./scripts/Principal-UDITO.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/scripts/choose-udito-mode.sh"

_ensure_venv() {
  [[ -x "$ROOT/.venv/bin/python" ]] || "$ROOT/scripts/setup-jetson-offline.sh"
  bash "$ROOT/scripts/install-piper-aarch64.sh" >/dev/null 2>&1 || true
}

_run_offline() {
  echo ""
  echo "▶ Modo OFFLINE — pipeline completo en esta Jetson"
  echo "  Di «udito» para activar. Ctrl+C para salir."
  echo ""
  exec "$ROOT/scripts/Principal-UDITO.sh"
}

_run_online() {
  if [[ -t 0 ]] && { [[ -z "${ROBITA_SERVER_URL:-}" ]] || [[ "${ROBITA_SERVER_URL:-}" == "http://192.168.1.100:8000" ]]; }; then
    read -r -p "URL del cerebro (ej. http://192.168.1.50:8000): " url_in
    [[ -n "$url_in" ]] && export ROBITA_SERVER_URL="${url_in%/}"
  fi
  : "${ROBITA_SERVER_URL:=http://127.0.0.1:8000}"
  export ROBITA_SERVER_URL

  echo ""
  echo "▶ Modo ONLINE — cuerpo en Jetson, cerebro en: $ROBITA_SERVER_URL"
  if ! curl -sf --max-time 3 "${ROBITA_SERVER_URL}/health" >/dev/null 2>&1 \
     && ! curl -sf --max-time 3 "${ROBITA_SERVER_URL}/services/status" >/dev/null 2>&1; then
    echo ""
    echo "⚠ No responde el servidor en $ROBITA_SERVER_URL"
    echo "  (servidor apagado, sin red o URL incorrecta)"
    echo ""
    if [[ -t 0 ]]; then
      read -r -p "¿Arrancar en modo OFFLINE en su lugar? [S/n]: " fallback
      case "${fallback:-S}" in
        n|N|no|No) echo "Cancelado."; exit 1 ;;
        *) _run_offline ;;
      esac
    else
      echo "Usa UDITO_MODE=offline si el servidor no está disponible."
      exit 1
    fi
  fi
  echo "  Cerebro OK. Di «udito» para activar."
  echo ""
  exec "$ROOT/scripts/udito.sh"
}

if [[ "${ROBITA_SKIP_PREPARE:-0}" != "1" ]]; then
  bash "$ROOT/scripts/prepare-pipeline.sh"
fi

_ensure_venv

case "${UDITO_MODE}" in
  offline) _run_offline ;;
  online)  _run_online ;;
  *) echo "Modo desconocido: $UDITO_MODE"; exit 1 ;;
esac
