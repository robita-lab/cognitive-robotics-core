#!/usr/bin/env bash
# Menú interactivo para elegir y probar audio de entrada/salida.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
ENV_FILE="$ROOT/.env"
PY="$ROOT/.venv/bin/python"
WAV="${WAV:-/tmp/udito-jetson-tts-test.wav}"

[[ -x "$PY" ]] || { echo "No existe $PY. Activa/crea el venv primero."; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "No existe $ENV_FILE"; exit 1; }

if [[ ! -f "$WAV" ]]; then
  bash "$ROOT/scripts/udito/audio-test.sh" >/dev/null 2>&1 || true
fi
[[ -f "$WAV" ]] || { echo "No hay WAV de prueba. Ejecuta ./scripts/udito/audio-test.sh"; exit 1; }

declare -a OUTPUT_LABELS OUTPUT_TYPES OUTPUT_VALUES
declare -a INPUT_LABELS INPUT_VALUES

pause() {
  read -r -p "Pulsa Enter para continuar..." _
}

set_env_var() {
  local key="$1"
  local value="$2"
  "$PY" - "$ENV_FILE" "$key" "$value" <<'PY'
import re
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
text = env_path.read_text(encoding="utf-8")
pattern = re.compile(rf"(?m)^({re.escape(key)}=).*$")
if pattern.search(text):
    text = pattern.sub(lambda m: f"{m.group(1)}{value}", text)
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"{key}={value}\n"
env_path.write_text(text, encoding="utf-8")
print(f"{key}={value}")
PY
}

reload_devices() {
  mapfile -t lines < <("$PY" - <<'PY'
import sounddevice as sd
for idx, d in enumerate(sd.query_devices()):
    name = str(d.get("name", "")).replace("|", "/")
    in_ch = int(d.get("max_input_channels", 0))
    out_ch = int(d.get("max_output_channels", 0))
    if out_ch > 0:
        print(f"OUT|sounddevice|{idx}|{name} (out:{out_ch})")
    if in_ch > 0:
        print(f"IN|{idx}|{name} (in:{in_ch})")
PY
)

  OUTPUT_LABELS=()
  OUTPUT_TYPES=()
  OUTPUT_VALUES=()
  INPUT_LABELS=()
  INPUT_VALUES=()

  local line mode a b c
  for line in "${lines[@]}"; do
    IFS='|' read -r mode a b c <<<"$line"
    if [[ "$mode" == "OUT" ]]; then
      # Filtrar rutas internas APE (suelen no sonar en altavoces reales).
      if [[ "$c" == *"NVIDIA Jetson Orin Nano APE"* ]]; then
        continue
      fi
      OUTPUT_TYPES+=("$a")
      OUTPUT_VALUES+=("$b")
      OUTPUT_LABELS+=("$c")
    elif [[ "$mode" == "IN" ]]; then
      INPUT_VALUES+=("$a")
      INPUT_LABELS+=("$b")
    fi
  done

  if command -v pactl >/dev/null; then
    while read -r _idx name _rest; do
      OUTPUT_TYPES+=("pulse")
      OUTPUT_VALUES+=("$name")
      OUTPUT_LABELS+=("Pulse sink: $name")
    done < <(pactl list short sinks)
  fi
}

show_devices() {
  reload_devices
  echo ""
  echo "=== SALIDAS DISPONIBLES ==="
  if [[ ${#OUTPUT_LABELS[@]} -eq 0 ]]; then
    echo "  (sin salidas detectadas)"
  else
    for i in "${!OUTPUT_LABELS[@]}"; do
      printf "  %2d) %s\n" "$((i + 1))" "${OUTPUT_LABELS[$i]}"
    done
  fi
  echo ""
  echo "=== ENTRADAS DISPONIBLES ==="
  if [[ ${#INPUT_LABELS[@]} -eq 0 ]]; then
    echo "  (sin entradas detectadas)"
  else
    for i in "${!INPUT_LABELS[@]}"; do
      printf "  %2d) %s\n" "$((i + 1))" "${INPUT_LABELS[$i]}"
    done
  fi
  echo ""
}

show_outputs_only() {
  reload_devices
  echo ""
  echo "=== SALIDAS DISPONIBLES ==="
  if [[ ${#OUTPUT_LABELS[@]} -eq 0 ]]; then
    echo "  (sin salidas detectadas)"
  else
    for i in "${!OUTPUT_LABELS[@]}"; do
      printf "  %2d) %s\n" "$((i + 1))" "${OUTPUT_LABELS[$i]}"
    done
  fi
  echo ""
}

show_inputs_only() {
  reload_devices
  echo ""
  echo "=== ENTRADAS DISPONIBLES ==="
  if [[ ${#INPUT_LABELS[@]} -eq 0 ]]; then
    echo "  (sin entradas detectadas)"
  else
    for i in "${!INPUT_LABELS[@]}"; do
      printf "  %2d) %s\n" "$((i + 1))" "${INPUT_LABELS[$i]}"
    done
  fi
  echo ""
}

test_output_by_number() {
  reload_devices
  if [[ ${#OUTPUT_LABELS[@]} -eq 0 ]]; then
    echo "No hay salidas para probar."
    return
  fi
  show_outputs_only
  read -r -p "Número de salida a probar: " n
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Número inválido."; return; }
  (( n >= 1 && n <= ${#OUTPUT_LABELS[@]} )) || { echo "Fuera de rango."; return; }
  local idx=$((n - 1))
  local type="${OUTPUT_TYPES[$idx]}"
  local val="${OUTPUT_VALUES[$idx]}"
  echo "Probando: ${OUTPUT_LABELS[$idx]}"
  if [[ "$type" == "pulse" ]]; then
    pactl suspend-sink "$val" 0 2>/dev/null || true
    if timeout 12 paplay --device "$val" "$WAV" 2>/dev/null; then
      echo "Reproducción enviada a Pulse sink."
    else
      echo "No se pudo reproducir en ese Pulse sink."
    fi
  else
    "$PY" - "$WAV" "$val" 2>/dev/null <<'PY'
import sys
import wave
import numpy as np
import sounddevice as sd

wav_path = sys.argv[1]
dev_idx = int(sys.argv[2])
with wave.open(wav_path, "rb") as wf:
    ch = wf.getnchannels()
    rate = wf.getframerate()
    sw = wf.getsampwidth()
    frames = wf.readframes(wf.getnframes())

if sw != 2:
    raise RuntimeError("Solo se soporta WAV PCM 16-bit para la prueba")

audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
if ch > 1:
    audio = audio.reshape(-1, ch)
else:
    audio = audio.reshape(-1, 1)

def resample_linear(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return x
    n_src = x.shape[0]
    n_dst = max(1, int(round(n_src * (dst_rate / float(src_rate)))))
    src_pos = np.linspace(0.0, n_src - 1, num=n_src, dtype=np.float64)
    dst_pos = np.linspace(0.0, n_src - 1, num=n_dst, dtype=np.float64)
    cols = []
    for c in range(x.shape[1]):
        cols.append(np.interp(dst_pos, src_pos, x[:, c]))
    y = np.stack(cols, axis=1).astype(np.float32)
    return y

def try_play(buf: np.ndarray, sr: int) -> bool:
    try:
        sd.play(buf, samplerate=sr, device=dev_idx)
        sd.wait()
        return True
    except Exception:
        return False

try:
    # Primer intento con frecuencia original del WAV
    if try_play(audio, rate):
        print("Reproducción enviada al dispositivo sounddevice.")
    else:
        # Fallback típico para HDMI / algunos DACs.
        print("Reintentando con frecuencias compatibles...")
        ok = False
        for sr in (48000, 44100, 16000):
            buf = resample_linear(audio, rate, sr)
            if try_play(buf, sr):
                print(f"Reproducción enviada al dispositivo sounddevice ({sr} Hz).")
                ok = True
                break
        if not ok:
            print("No se pudo reproducir en ese dispositivo (ni con frecuencias alternativas).")
except Exception:
    print("No se pudo reproducir en ese dispositivo.")
PY
  fi
}

test_input_by_number() {
  reload_devices
  if [[ ${#INPUT_LABELS[@]} -eq 0 ]]; then
    echo "No hay entradas para probar."
    return
  fi
  show_inputs_only
  read -r -p "Número de entrada a probar: " n
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Número inválido."; return; }
  (( n >= 1 && n <= ${#INPUT_LABELS[@]} )) || { echo "Fuera de rango."; return; }
  local idx=$((n - 1))
  local val="${INPUT_VALUES[$idx]}"
  echo "Probando entrada: ${INPUT_LABELS[$idx]}"
  echo "Habla durante 5 segundos..."
  "$PY" - "$val" 2>/dev/null <<'PY'
import os
import sys
import tempfile
import wave
import numpy as np
import sounddevice as sd

dev_idx = int(sys.argv[1])
rate = 16000
seconds = 5

tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
tmp_path = tmp.name
tmp.close()

try:
    audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="float32", device=dev_idx)
    sd.wait()
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)
    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    print("Reproduciendo lo grabado...")
    sd.play(audio, samplerate=rate)
    sd.wait()
    print("Prueba de micrófono completada.")
except Exception:
    print("No se pudo grabar/reproducir con ese dispositivo de entrada.")
finally:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
PY
  read -r -p "¿Escuchaste algo de tu grabación? [s/n]: " ans
  case "${ans,,}" in
    s|si|sí|y|yes) echo "Perfecto, ese micrófono funciona." ;;
    *) echo "Ok, prueba otro número de entrada." ;;
  esac
}

set_default_output_by_number() {
  reload_devices
  if [[ ${#OUTPUT_LABELS[@]} -eq 0 ]]; then
    echo "No hay salidas para configurar."
    return
  fi
  show_outputs_only
  read -r -p "Número de salida predeterminada: " n
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Número inválido."; return; }
  (( n >= 1 && n <= ${#OUTPUT_LABELS[@]} )) || { echo "Fuera de rango."; return; }
  local idx=$((n - 1))
  local type="${OUTPUT_TYPES[$idx]}"
  local val="${OUTPUT_VALUES[$idx]}"
  echo "Guardando salida: ${OUTPUT_LABELS[$idx]}"
  if [[ "$type" == "pulse" ]]; then
    set_env_var "ROBITA_AUDIO_OUTPUT" "pulse"
    set_env_var "ROBITA_PULSE_SINK" "$val"
    echo "Salida por Pulse sink configurada."
  else
    set_env_var "ROBITA_AUDIO_OUTPUT" "$val"
    echo "Salida por índice sounddevice configurada."
  fi
}

set_default_input_by_number() {
  reload_devices
  if [[ ${#INPUT_LABELS[@]} -eq 0 ]]; then
    echo "No hay entradas para configurar."
    return
  fi
  show_inputs_only
  read -r -p "Número de entrada predeterminada: " n
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Número inválido."; return; }
  (( n >= 1 && n <= ${#INPUT_LABELS[@]} )) || { echo "Fuera de rango."; return; }
  local idx=$((n - 1))
  local val="${INPUT_VALUES[$idx]}"
  echo "Guardando entrada: ${INPUT_LABELS[$idx]}"
  set_env_var "ROBITA_AUDIO_INPUT" "$val"
}

menu() {
  while true; do
    clear 2>/dev/null || true
    echo "=============================================="
    echo "  UDITO Audio Menu"
    echo "=============================================="
    echo "  1) Ver todos los dispositivos"
    echo "  2) Probar salida por número"
    echo "  3) Fijar salida predeterminada por número"
    echo "  4) Fijar entrada predeterminada por número"
    echo "  5) Probar entrada (graba 5s y reproduce)"
    echo "  6) Salir"
    echo ""
    read -r -p "Opción: " opt
    echo ""
    case "${opt:-}" in
      1) show_devices; pause ;;
      2) test_output_by_number; pause ;;
      3) set_default_output_by_number; pause ;;
      4) set_default_input_by_number; pause ;;
      5) test_input_by_number; pause ;;
      6|q|Q|0) echo "Hecho."; exit 0 ;;
      *) echo "Opción inválida."; pause ;;
    esac
  done
}

menu
