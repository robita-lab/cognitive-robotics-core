#!/usr/bin/env bash
# Prueba voces masculinas Piper, una a una; pregunta si te gusta cada una.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] && set -a && source .env && set +a

VOICES_DIR="$ROOT/01_SERVICES/tts-engine/piper/voices"
CFG="$ROOT/01_SERVICES/tts-engine/config/tts_config.json"
PY="$ROOT/.venv/bin/python"
TEXT="Hola, soy Udito. Esta es mi voz."

# Masculinas español — baja / media (sin sharvard ni mls)
declare -A LABEL=(
  ["es_ES-carlfm-x_low.onnx"]="España · muy baja (robótica) · carlfm"
  ["es_ES-davefx-medium.onnx"]="España · media · davefx"
  ["es_MX-ald-medium.onnx"]="México · media · ald"
)
MODELS=(
  "es_ES-carlfm-x_low.onnx"
  "es_ES-davefx-medium.onnx"
  "es_MX-ald-medium.onnx"
)

ask() {
  while true; do
    read -r -p "¿Te gusta esta voz? [s/n]: " ans
    case "${ans,,}" in
      s|si|sí|y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "  Responde s o n" ;;
    esac
  done
}

liked=()
disliked=()

for model in "${MODELS[@]}"; do
  f="$VOICES_DIR/$model"
  if [[ ! -f "$f" ]]; then
    echo "Falta $model — ejecuta: ./scripts/download-piper-voices-male.sh"
    continue
  fi
  label="${LABEL[$model]:-$model}"
  echo ""
  echo "────────────────────────────────────────"
  echo "  $label"
  echo "────────────────────────────────────────"
  ROBITA_AUDIO_OUTPUT="${ROBITA_AUDIO_OUTPUT:-platform}" "$PY" <<PY
import json, sys
from pathlib import Path
sys.path.insert(0, "$ROOT/01_SERVICES/tts-engine")
sys.path.insert(0, "$ROOT/03_ADAPTERS/robot-udit-physical")
from piper_tts_real import PiperTTS
from robot_common import play_wav_file

cfg = json.loads(Path("$CFG").read_text(encoding="utf-8"))
cfg["voice_model"] = "$model"
if "x_low" in "$model":
    cfg["length_scale"] = 1.2
    cfg["noise_scale"] = 0.5
    cfg["noise_w"] = 0.6
elif "low" in "$model":
    cfg["length_scale"] = 1.1
tmp = Path("$ROOT/01_SERVICES/tts-engine/config/.voice-test.json")
tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
tts = PiperTTS(config_path=str(tmp))
wav = tts.synthesize_to_bytes("""$TEXT""")
if not wav:
    raise SystemExit("Error generando audio")
out = Path("/tmp/udito-voice-test.wav")
out.write_bytes(wav)
if not play_wav_file(str(out)):
    raise SystemExit("Error reproduciendo audio")
PY
  if ask; then
    liked+=("$model")
    echo "  ✓ Anotada como me gusta"
  else
    disliked+=("$model")
    echo "  ✗ Anotada como no"
  fi
done

echo ""
echo "═══ Resumen ═══"
[[ ${#liked[@]} -gt 0 ]] && { echo "Te gustaron:"; printf '  • %s\n' "${liked[@]}"; }
[[ ${#disliked[@]} -gt 0 ]] && { echo "No te gustaron:"; printf '  • %s\n' "${disliked[@]}"; }
if [[ ${#liked[@]} -gt 0 ]]; then
  pick="${liked[0]}"
  echo ""
  echo "Para usar «$pick», en tts_config.json:"
  echo '  "voice_model": "'"$pick"'"'
fi
