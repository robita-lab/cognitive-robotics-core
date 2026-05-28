#!/usr/bin/env bash
# Menú interactivo UDITO — pruebas por componente y pipeline completo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
export ROBITA_KNOWLEDGE_CORE="${ROBITA_KNOWLEDGE_CORE:-$ROOT/04_KNOWLEDGE_CORE}"
export HF_HOME="${HF_HOME:-$ROOT/data/huggingface}"
export ROBITA_RAG_CONFIG="${ROBITA_RAG_CONFIG:-$ROOT/01_SERVICES/rag-engine/config/rag_config.jetson.json}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
export ROBITA_VERBOSE="${ROBITA_VERBOSE:-1}"

# shellcheck source=/dev/null
[[ -f "$ROOT/scripts/jetson-env.sh" ]] && source "$ROOT/scripts/jetson-env.sh"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

_bold() { printf '\033[1m%s\033[0m\n' "$*"; }
_pause() { read -r -p "Pulsa Enter para volver al menú..." _; }

_ensure_env() {
  if [[ ! -x "$PY" ]]; then
    echo "No hay .venv. Ejecuta primero:"
    echo "  $ROOT/scripts/setup-jetson-offline.sh"
    return 1
  fi
  bash "$ROOT/scripts/install-piper-aarch64.sh" >/dev/null 2>&1 || true
  return 0
}

_list_mics() {
  echo ""
  echo "Dispositivos de audio (sounddevice):"
  "$PY" -c "import sounddevice as sd; print(sd.query_devices())" 2>/dev/null || echo "  (no disponible)"
  echo ""
  echo "ROBITA_AUDIO_INPUT=${ROBITA_AUDIO_INPUT:-(vacío=default)}"
  echo "ROBITA_AUDIO_OUTPUT=${ROBITA_AUDIO_OUTPUT:-default}"
}

_run_pipeline() {
  _bold "=== Pipeline completo (wakeword → STT → RAG → TTS) ==="
  exec "$ROOT/scripts/udito-run.sh"
}

_run_wakeword() {
  _bold "=== Prueba wakeword ==="
  echo "Escucha continua. Di «udito» varias veces. Ctrl+C para salir."
  _list_mics
  _pause
  export ROOT
  "$PY" -u <<'PY'
import os, sys, queue, time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
ROOT = Path(os.environ["ROOT"])
sys.path.insert(0, str(ROOT / "03_ADAPTERS" / "robot-udit-physical"))
sys.path.insert(0, str(ROOT / "01_SERVICES" / "wakeword-engine"))

from robot_common import (
    setup_wakeword_path, load_detection_cfg, calibrate_noise_floor,
    run_voice_assistant, drain_queue, progress, play_wav_bytes, CHUNK_SEC,
)
setup_wakeword_path()
import Detector_wakeword as ww

sys.path.insert(0, str(ROOT / "01_SERVICES" / "tts-engine"))
sys.path.insert(0, str(ROOT / "04_KNOWLEDGE_CORE"))
from piper_tts_real import PiperTTS
from load_responses import message

tts = PiperTTS(config_path=str(ROOT / "01_SERVICES/tts-engine/config/tts_config.json"))

SAMPLE_RATE = ww.SAMPLE_RATE
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)
cfg = load_detection_cfg()
noise = calibrate_noise_floor(SAMPLE_RATE, float(cfg["calibrate_secs"]))

def greet():
    text = message("greeting", "Hola, ¿en qué te puedo ayudar?")
    progress(f"\n[wake] «udito» detectado — [saludo] {text}")
    wav = tts.synthesize_to_bytes(text)
    if wav:
        play_wav_bytes(wav)
    else:
        progress("[audio] ERROR — Piper no generó audio. Prueba opción 3 del menú.")

def on_session(audio_q: queue.Queue):
    progress("[sesión] Wakeword OK. En pipeline completo aquí grabaría tu pregunta.")
    drain_queue(audio_q, 0.5)

run_voice_assistant(ww, cfg, noise, SAMPLE_RATE, CHUNK_SAMPLES, on_session=on_session, greet=greet)
PY
}

_run_tts() {
  _bold "=== Prueba TTS (Piper) ==="
  TEXT="${1:-Hola, soy UDITO. Esta es una prueba de voz en la Jetson.}"
  echo "Texto: $TEXT"
  bash "$ROOT/scripts/test-audio-standalone.sh" 2>&1 | tail -15
  if [[ -f /tmp/udito-jetson-tts-test.wav ]] && [[ -s /tmp/udito-jetson-tts-test.wav ]]; then
    echo "OK — WAV generado: /tmp/udito-jetson-tts-test.wav"
  else
    echo "ERROR — no se generó audio. Revisa Piper: scripts/install-piper-aarch64.sh"
    return 1
  fi
}

_run_stt_rag() {
  _bold "=== Prueba STT + RAG ==="
  echo "AVISO: carga Whisper + RAG en RAM (~2–3 GB). Si la Jetson se reinicia, usa pipeline (opción 1) con rag_config.jetson.json."
  echo "Tras calibrar, habla tu pregunta (VAD). Ctrl+C aborta."
  _list_mics
  _pause
  ROOT="$ROOT" "$PY" -u <<'PY'
import os, sys, tempfile, queue
from pathlib import Path
import sounddevice as sd

ROOT = Path(os.environ["ROOT"])
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("HF_HOME", str(ROOT / "data" / "huggingface"))
sys.path.insert(0, str(ROOT / "03_ADAPTERS" / "robot-udit-physical"))
sys.path.insert(0, str(ROOT / "04_KNOWLEDGE_CORE"))
sys.path.insert(0, str(ROOT / "01_SERVICES" / "stt-engine"))
sys.path.insert(0, str(ROOT / "01_SERVICES" / "rag-engine"))

from robot_common import (
    load_detection_cfg, calibrate_noise_floor, record_question_vad,
    audio_has_speech, save_wav, progress, setup_wakeword_path, CHUNK_SEC,
    audio_input_device,
)
setup_wakeword_path()
import Detector_wakeword as ww
from whisper_stt import WhisperSTT
from rag_system import RAGSystem

SAMPLE_RATE = ww.SAMPLE_RATE
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SEC)
cfg = load_detection_cfg()
noise = calibrate_noise_floor(SAMPLE_RATE, float(cfg["calibrate_secs"]))

print("Cargando Whisper...")
stt = WhisperSTT(
    config_path=str(ROOT / "01_SERVICES/stt-engine/config/STT_config.json"),
    project_root=str(ROOT / "01_SERVICES/stt-engine"),
)
stt._ensure_model()

rag_cfg = os.getenv("ROBITA_RAG_CONFIG", str(ROOT / "01_SERVICES/rag-engine/config/rag_config.jetson.json"))
print("Cargando RAG (puede tardar ~1 min la primera vez)...")
os.chdir(ROOT / "01_SERVICES/rag-engine")
rag = RAGSystem(
    config_path=rag_cfg,
    settings_path=str(ROOT / "01_SERVICES/rag-engine/config/settings.json"),
)
rag.initialize(force_rebuild=False)

audio_q: queue.Queue = queue.Queue(maxsize=200)

def _cb(indata, frames, ctime, status):
    try:
        audio_q.put_nowait(indata.copy().reshape(-1))
    except queue.Full:
        pass

stream_kw = dict(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK_SAMPLES, callback=_cb)
mic = audio_input_device()
if mic is not None:
    stream_kw["device"] = mic

print("\nHabla ahora (grabación automática por VAD)...\n")
with sd.InputStream(**stream_kw):
    audio = record_question_vad(
        audio_q, noise, cfg, SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE,
    )
if not audio_has_speech(audio, noise, cfg["speech_margin"], SAMPLE_RATE, CHUNK_SAMPLES, ww.THRESHOLD_VOICE):
    print("No se detectó voz clara.")
    sys.exit(1)

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
    path = tmp.name
save_wav(path, audio, SAMPLE_RATE)
result = stt.transcribe(path)
os.unlink(path)
text = (result or {}).get("text", "").strip()
if not text:
    print("STT no devolvió texto.")
    sys.exit(1)
progress(f"[STT] {text}")

ans = rag.process_query(text)
answer = (ans.get("answer") or "").strip()
source = ans.get("source", "?")
print(f"\n[RAG / {source}]\n{answer}\n")
PY
}

_run_rag() {
  _bold "=== Prueba RAG (solo texto) ==="
  DEFAULT_Q="¿Quién eres?"
  read -r -p "Pregunta [$DEFAULT_Q]: " Q
  Q="${Q:-$DEFAULT_Q}"
  echo ""
  ROOT="$ROOT" "$PY" -u <<PY
import os, sys
from pathlib import Path

ROOT = Path("$ROOT")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("HF_HOME", str(ROOT / "data" / "huggingface"))
sys.path.insert(0, str(ROOT / "04_KNOWLEDGE_CORE"))
sys.path.insert(0, str(ROOT / "01_SERVICES" / "rag-engine"))
os.chdir(ROOT / "01_SERVICES/rag-engine")

from rag_system import RAGSystem

rag_cfg = os.getenv("ROBITA_RAG_CONFIG", str(ROOT / "01_SERVICES/rag-engine/config/rag_config.jetson.json"))
print("Cargando RAG...")
rag = RAGSystem(
    config_path=rag_cfg,
    settings_path=str(ROOT / "01_SERVICES/rag-engine/config/settings.json"),
)
rag.initialize(force_rebuild=False)
ans = rag.process_query("""$Q""")
print(f"Fuente: {ans.get('source', '?')}")
print(f"\n{ans.get('answer', '(sin respuesta)')}\n")
PY
}

_show_menu() {
  clear 2>/dev/null || true
  _bold "══════════════ UDITO — Menú de pruebas ══════════════"
  echo "  Ruta: $ROOT"
  echo ""
  echo "  1) Correr pipeline completo"
  echo "  2) Probar wakeword"
  echo "  3) Probar TTS"
  echo "  4) Probar STT + RAG"
  echo "  5) Probar RAG"
  echo "  6) Salir"
  echo ""
}

main() {
  if ! _ensure_env; then
    _pause
    exit 1
  fi

  while true; do
    _show_menu
    read -r -p "Opción: " opt
    echo ""
    case "${opt:-}" in
      1) _run_pipeline ;;
      2) _run_wakeword; _pause ;;
      3) _run_tts; _pause ;;
      4) _run_stt_rag; _pause ;;
      5) _run_rag; _pause ;;
      6|0|q|Q) echo "Hasta luego."; exit 0 ;;
      *) echo "Opción no válida."; _pause ;;
    esac
  done
}

export ROOT
main "$@"
