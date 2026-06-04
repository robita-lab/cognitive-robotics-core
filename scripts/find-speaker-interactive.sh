#!/usr/bin/env bash
# Alternativa guiada (prueba salidas una a una). Para fijar mic/altavoz en .env: ./scripts/find-speaker.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] && set -a && source .env && set +a

WAV="/tmp/udito-jetson-tts-test.wav"
if [[ ! -f "$WAV" ]]; then
  echo "Generando audio de prueba…"
  bash "$ROOT/scripts/test-audio-standalone.sh" >/dev/null 2>&1 || true
fi
[[ -f "$WAV" ]] || { echo "No hay $WAV — ejecuta: ./scripts/test-audio-standalone.sh"; exit 1; }

PY="$ROOT/.venv/bin/python"
heard=()
not_heard=()

ask_yesno() {
  local prompt="$1"
  while true; do
    read -r -p "$prompt [s/n]: " ans
    case "${ans,,}" in
      s|si|sí|y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "  Responde s (sí) o n (no)" ;;
    esac
  done
}

play_pulse() {
  local sink="$1"
  pactl suspend-sink "$sink" 0 2>/dev/null || true
  pactl set-sink-volume "$sink" 100% 2>/dev/null || true
  pactl set-default-sink "$sink" 2>/dev/null || true
  timeout 15 paplay --device "$sink" "$WAV" 2>/dev/null
}

play_alias() {
  local alias="$1"
  ROBITA_AUDIO_OUTPUT="$alias" "$PY" -c "
import sys
sys.path.insert(0, '$ROOT/03_ADAPTERS/robot-udit-physical')
from robot_common import play_wav_file
play_wav_file('$WAV')
" 2>/dev/null
}

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Prueba de altavoz — UNA salida cada vez"
echo "  Escucha el mensaje y responde s / n"
echo "══════════════════════════════════════════════════════"
echo ""

if command -v pactl >/dev/null; then
  n=1
  while read -r _idx name _rest; do
    echo "──────────────────────────────────────────────────────"
    echo "  Prueba $n — PulseAudio: $name"
    echo "──────────────────────────────────────────────────────"
    play_pulse "$name"
    if ask_yesno "  ¿Oíste esta prueba?"; then
      heard+=("pulse:$name")
      echo "  ✓ Anotado: SÍ"
    else
      not_heard+=("pulse:$name")
      echo "  ✗ Anotado: NO"
    fi
    echo ""
    n=$((n + 1))
  done < <(pactl list short sinks)
fi

for alias in hdmi respeaker platform; do
  echo "──────────────────────────────────────────────────────"
  echo "  Prueba — alias UDITO: ROBITA_AUDIO_OUTPUT=$alias"
  echo "──────────────────────────────────────────────────────"
  play_alias "$alias"
  if ask_yesno "  ¿Oíste esta prueba?"; then
    heard+=("alias:$alias")
    echo "  ✓ Anotado: SÍ"
  else
    not_heard+=("alias:$alias")
    echo "  ✗ Anotado: NO"
  fi
  echo ""
done

for dev in plughw:0,0 plughw:1,3; do
  echo "──────────────────────────────────────────────────────"
  echo "  Prueba — ALSA directo: $dev"
  echo "──────────────────────────────────────────────────────"
  timeout 15 aplay -q -D "$dev" "$WAV" 2>/dev/null || true
  if ask_yesno "  ¿Oíste esta prueba?"; then
    heard+=("alsa:$dev")
    echo "  ✓ Anotado: SÍ"
  else
    not_heard+=("alsa:$dev")
    echo "  ✗ Anotado: NO"
  fi
  echo ""
done

echo "══════════════════════════════════════════════════════"
echo "  RESUMEN"
echo "══════════════════════════════════════════════════════"
if [[ ${#heard[@]} -eq 0 ]]; then
  echo "  No marcaste ninguna salida. Revisa volumen y cable."
else
  echo "  Sí oíste:"
  for h in "${heard[@]}"; do echo "    • $h"; done
  echo ""
  best=""
  for h in "${heard[@]}"; do
    if [[ "$h" == alias:* ]]; then
      best="${h#alias:}"
      break
    fi
  done
  if [[ -z "$best" ]]; then
    first="${heard[0]}"
    if [[ "$first" == pulse:* ]]; then
      sink="${first#pulse:}"
      case "$sink" in
        *hdmi*) best=hdmi ;;
        *ReSpeaker*|*respeaker*) best=respeaker ;;
        *platform-sound*) best=platform ;;
        *) best="pulse"; echo "  Sugerencia .env: ROBITA_PULSE_SINK=$sink" ;;
      esac
    elif [[ "$first" == alsa:* ]]; then
      best="${first#alsa:}"
    fi
  fi
  if [[ -n "$best" && "$best" != pulse ]]; then
    echo "  Sugerencia .env:"
    echo "    ROBITA_AUDIO_OUTPUT=$best"
  fi
fi
if [[ ${#not_heard[@]} -gt 0 ]]; then
  echo ""
  echo "  No oíste:"
  for h in "${not_heard[@]}"; do echo "    • $h"; done
fi
echo ""
