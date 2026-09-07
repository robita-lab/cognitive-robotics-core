#!/usr/bin/env bash
# Comando principal UDITO — 100 % offline en esta Jetson (wakeword + STT + RAG + TTS).
# Uso: ./scripts/udito/start.sh   o   ./UDITO   desde /opt/robita-lab
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p logs
chmod u+rwx logs 2>/dev/null || true

export UDITO_MODE=offline
export ROBITA_VERBOSE="${ROBITA_VERBOSE:-0}"

# Guardar flags de la línea de comandos (source .env no debe pisarlos)
_CLI_SKIP_PREPARE="${ROBITA_SKIP_PREPARE:-}"
_CLI_CLEANUP="${ROBITA_CLEANUP_PROJECT:-}"

# shellcheck source=/dev/null
[[ -f "$ROOT/scripts/lib/jetson-env.sh" ]] && source "$ROOT/scripts/lib/jetson-env.sh"
if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env"; set +a; fi
[[ -n "$_CLI_SKIP_PREPARE" ]] && export ROBITA_SKIP_PREPARE="$_CLI_SKIP_PREPARE"
[[ -n "$_CLI_CLEANUP" ]] && export ROBITA_CLEANUP_PROJECT="$_CLI_CLEANUP"

if command -v pactl >/dev/null; then
  _RS_SRC="${ROBITA_PULSE_SOURCE:-alsa_input.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.multichannel-input}"
  _RS_SNK="${ROBITA_PULSE_SINK:-alsa_output.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.analog-stereo}"
  _IN="${ROBITA_AUDIO_INPUT:-}"
  _OUT="${ROBITA_AUDIO_OUTPUT:-}"
  if [[ "${_IN,,}" == "respeaker" ]] || [[ "${_IN,,}" == "pulse" && "${_OUT,,}" == "respeaker" ]]; then
    pactl suspend-source "$_RS_SRC" 0 2>/dev/null || true
    pactl set-source-volume "$_RS_SRC" 100% 2>/dev/null || true
    pactl set-default-source "$_RS_SRC" 2>/dev/null || true
    echo "Audio: micrófono Pulse → $_RS_SRC"
  fi
  case "${_OUT,,}" in
    hdmi) SINK="alsa_output.platform-3510000.hda.hdmi-stereo" ;;
    respeaker) SINK="$_RS_SNK" ;;
    platform|placa) SINK="alsa_output.platform-sound.analog-stereo" ;;
    pulse) SINK="" ;;
    *) SINK="${ROBITA_PULSE_SINK:-}" ;;
  esac
  if [[ -n "$SINK" ]]; then
    pactl suspend-sink "$SINK" 0 2>/dev/null || true
    pactl set-sink-volume "$SINK" 100% 2>/dev/null || true
    pactl set-default-sink "$SINK" 2>/dev/null || true
    echo "Audio: altavoz Pulse → $SINK"
  fi
fi

[[ -x "$ROOT/.venv/bin/python" ]] || "$ROOT/scripts/setup/jetson.sh"
bash "$ROOT/scripts/setup/piper-jetson.sh" >/dev/null 2>&1 || true

if [[ "${ROBITA_SKIP_PREPARE:-0}" != "1" ]]; then
  bash "$ROOT/scripts/lib/prepare-pipeline.sh"
fi

LOG="$ROOT/logs/udito-standalone.log"
if [[ -e "$LOG" ]] && [[ ! -w "$LOG" ]]; then
  rm -f "$LOG" 2>/dev/null || true
fi
if ! touch "$LOG" 2>/dev/null || [[ ! -w "$LOG" ]]; then
  LOG="/tmp/udito-standalone.log"
  touch "$LOG" 2>/dev/null || true
fi

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Principal UDITO — modo OFFLINE (todo en esta Jetson)"
echo "  Di «${ROBITA_WAKEWORD:-udito}» para activar. Mensajes en esta terminal."
echo "  Log: $LOG"
echo "  Ctrl+C para parar"
echo "══════════════════════════════════════════════════════"
echo ""

if [[ -w "$LOG" ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  echo "Aviso: no se puede escribir en $LOG — salida solo en esta terminal." >&2
fi
exec "$ROOT/scripts/udito/run-standalone.sh"
