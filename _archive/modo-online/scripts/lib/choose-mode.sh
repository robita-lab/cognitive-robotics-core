#!/usr/bin/env bash
# Elige modo online (cerebro en servidor) u offline (todo en esta Jetson).
# Uso no interactivo: UDITO_MODE=offline|online
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

if [[ -n "${UDITO_MODE:-}" ]]; then
  case "${UDITO_MODE,,}" in
    offline|online) export UDITO_MODE="${UDITO_MODE,,}"; return 0 2>/dev/null || exit 0 ;;
    *) echo "UDITO_MODE inválido: $UDITO_MODE (use offline u online)" >&2; exit 1 ;;
  esac
fi

echo ""
echo "════════════════════════════════════════"
echo "  UDITO — ¿Cómo quieres ejecutar el pipeline?"
echo "════════════════════════════════════════"
echo ""
echo "  1) Offline — todo en esta Jetson (sin servidor)"
echo "     wakeword + STT + RAG + TTS locales"
echo ""
echo "  2) Online  — cuerpo aquí, cerebro en servidor (ROBITA_SERVER_URL)"
echo "     requiere que el servidor esté encendido y en red"
echo ""
echo "  [Enter] = Offline (recomendado si no hay servidor)"
echo ""

if [[ ! -t 0 ]]; then
  export UDITO_MODE=offline
  echo "Sin terminal interactiva → modo offline."
  return 0 2>/dev/null || exit 0
fi

read -r -p "Elige 1/2 [Enter=offline]: " choice
case "${choice:-1}" in
  1|""|o|O|offline|OFFLINE)
    export UDITO_MODE=offline
    ;;
  2|online|ONLINE)
    export UDITO_MODE=online
    ;;
  *)
    echo "Opción no válida. Usando offline."
    export UDITO_MODE=offline
    ;;
esac
