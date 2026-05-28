#!/usr/bin/env bash
# Arranca UDITO en primer plano (mensajes en esta terminal + log).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs
LOG="$ROOT/logs/udito-standalone.log"

export UDITO_MODE="${UDITO_MODE:-offline}"
export ROBITA_VERBOSE="${ROBITA_VERBOSE:-0}"

if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env"; set +a; fi
if [[ -n "${ROBITA_AUDIO_OUTPUT:-}" ]] && command -v pactl >/dev/null; then
  case "${ROBITA_AUDIO_OUTPUT,,}" in
    hdmi) SINK="alsa_output.platform-3510000.hda.hdmi-stereo" ;;
    respeaker) SINK="alsa_output.usb-SEEED_ReSpeaker_4_Mic_Array__UAC1.0_-00.analog-stereo" ;;
    platform|placa) SINK="alsa_output.platform-sound.analog-stereo" ;;
    *) SINK="${ROBITA_PULSE_SINK:-}" ;;
  esac
  if [[ -n "$SINK" ]]; then
    pactl suspend-sink "$SINK" 0 2>/dev/null || true
    pactl set-sink-volume "$SINK" 100% 2>/dev/null || true
    pactl set-default-sink "$SINK" 2>/dev/null || true
    echo "Audio: sink PulseAudio → $SINK"
  fi
fi

echo ""
echo "══════════════════════════════════════════════════════"
echo "  UDITO — arranque visible"
echo "  Verás mensajes aquí. Di «udito» para activar."
echo "  Log adicional: $LOG"
echo "  Ctrl+C para parar"
echo "══════════════════════════════════════════════════════"
echo ""

exec > >(tee -a "$LOG") 2>&1
exec "$ROOT/scripts/udito-run.sh"
