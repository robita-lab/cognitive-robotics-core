import time
import queue
from pathlib import Path
from collections import deque
import numpy as np
import sounddevice as sd
import tensorflow as tf
import logging

logger = logging.getLogger("voice_assistant.wakeword")

try:
    from openwakeword import Model as OWWModel
except Exception as _oww_exc:
    OWWModel = None

# Modelo en la misma carpeta que este script (voice-assistant/wakeword)
_WAKEWORD_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(_WAKEWORD_DIR / "micro_model.tflite")
if not Path(MODEL_PATH).exists():
    MODEL_PATH = str(_WAKEWORD_DIR / "wakeword_model.tflite")
SAMPLE_RATE = 16000
BLOCK_DURATION = 1.0  # segundos de audio por evaluación
THRESHOLD_VOICE = 0.0002  # energía mínima para considerar voz (ajustada)
WAKEWORD_THRESHOLD = 0.49  # umbral de probabilidad para afirmar wakeword
WAKEWORD_CLASS_INDEX = 1  # índice de clase wakeword cuando la salida es softmax de 2 clases
ORIENTATION_AUTO = True   # probar H=num_mfcc,W=tiempo y H=tiempo,W=num_mfcc
PREEMPH_AUTO = True       # probar con y sin pre-énfasis
CHUNK_MS = 80  # tamaño del fragmento para OWW (80 ms recomendado)
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)
WAKEWORD_NAME = "udito"  # nombre esperado de la palabra clave en OWW
SENSITIVITY = 0.6  # 0.0 (estricto) .. 1.0 (muy sensible)
CALIBRATE_SECS = 3.0  # segundos de calibración inicial del umbral con ambiente
COOL_DOWN_SEC = 1.0  # tiempo de bloqueo tras activación para evitar re-disparos

# --- Cargar modelo TFLite ---
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
_printed_model_info_once = False
_last_prob_vector = None  # almacena la última prob vector normalizada si existe
_debug_voice_prints_remaining = 6  # imprime detalles de salida algunas veces al detectar voz
_oww_info_printed = False
_last_chosen_mode = ""

def _oww_get_prob(preds) -> float:
    """Extrae probabilidad de wakeword del resultado de OWW."""
    global _oww_info_printed
    if isinstance(preds, dict):
        if not _oww_info_printed:
            try:
                print(f"[OWW] keys={list(preds.keys())}")
            except Exception:
                pass
            _oww_info_printed = True
        # mapa insensible a mayúsculas
        try:
            lower_keys = {k.lower(): k for k in preds.keys()}
            # preferir 'udito'
            if 'udito' in lower_keys:
                return float(preds[lower_keys['udito']])
            # luego 'wakeword'
            if 'wakeword' in lower_keys:
                return float(preds[lower_keys['wakeword']])
        except Exception:
            pass
        # intentar por nombre del archivo sin extensión
        try:
            key_alt = MODEL_PATH.split('/')[-1].split('\\')[-1].rsplit('.', 1)[0]
            if key_alt in preds:
                return float(preds[key_alt])
        except Exception:
            pass
        # si hay una sola clave, usarla
        try:
            if len(preds) == 1:
                return float(list(preds.values())[0])
        except Exception:
            pass
        # si no, usar el máximo
        try:
            return float(max(preds.values()))
        except Exception:
            return 0.0
    # si viene como lista/array
    try:
        arr = np.array(preds).astype(np.float32).ravel()
        if arr.size == 0:
            return 0.0
        return float(np.max(arr))
    except Exception:
        return 0.0

def main_oww():
    print("🎧 OpenWakeWord: escuchando continuamente. (Ctrl+C para salir)")
    if OWWModel is None:
        print("[OWW] Librería no disponible; usando ruta TFLite.")
        return main()

    try:
        model = OWWModel(wakeword_models=[MODEL_PATH], vad_threshold=0.5)
    except Exception as e:
        print("[OWW] Error cargando modelo:", e)
        return main()

    audio_q = queue.Queue()

    def callback(indata, frames, ctime, status):
        if status:
            print(f"⚠️  Estado de audio: {status}", flush=True)
        audio_q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE,
                               channels=1,
                               dtype='int16',
                               blocksize=CHUNK_SAMPLES,
                               callback=callback):
            print("Esperando voz...")
            # --- Calibración inicial ---
            cal_deadline = time.time() + CALIBRATE_SECS
            cal_probs = []
            cal_rms = []
            while time.time() < cal_deadline:
                try:
                    chunk_bytes = audio_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                data_i16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                data = (data_i16.astype(np.float32) / 32768.0).astype(np.float32)
                try:
                    preds = model.predict(data)
                    prob_inst = _oww_get_prob(preds)
                    cal_probs.append(float(prob_inst))
                    cal_rms.append(float(np.sqrt(np.mean(data ** 2)) + 1e-12))
                except Exception:
                    pass

            # Umbrales relativos dinámicos basados en línea base
            if len(cal_probs) >= 5:
                baseline_prob = float(np.median(cal_probs))
            else:
                baseline_prob = 0.5
            alpha = 0.05 if SENSITIVITY >= 0.5 else 0.03  # suavizado de baseline
            delta_up = max(0.05, 0.12 - 0.07 * SENSITIVITY)  # salto necesario para activar
            delta_down = delta_up * 0.5  # histéresis
            hits_required = 1 if SENSITIVITY >= 0.8 else (2 if SENSITIVITY >= 0.5 else 3)
            print(f"[CAL] base={baseline_prob:.2f} du={delta_up:.2f} dd={delta_down:.2f} hits={hits_required} rms_med={np.mean(cal_rms) if cal_rms else 0:.4f}")

            probs_hist = deque(maxlen=5)
            consecutive_hits = 0
            active = False
            last_activation_ts = 0.0
            was_voice = False
            armed = True
            consecutive_silence = 0
            silence_required_chunks = max(1, int(0.30 / (CHUNK_MS / 1000.0)))

            while True:
                try:
                    chunk_bytes = audio_q.get(timeout=1.0)
                except queue.Empty:
                    continue

                data_i16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                # normalizar a float32 [-1,1]
                data = (data_i16.astype(np.float32) / 32768.0).astype(np.float32)
                try:
                    preds = model.predict(data)
                except Exception as e:
                    print("[OWW] Error en predict:", e)
                    continue

                prob_inst = _oww_get_prob(preds)
                # Energía y RMS para VAD simple
                energy = float(np.mean(data ** 2))
                rms = float(np.sqrt(energy) + 1e-12)

                # Voz detectada (flanco de subida)
                is_voice_now = energy > THRESHOLD_VOICE
                if is_voice_now and not was_voice:
                    print("Voz detectada... esperando palabra clave...", flush=True)
                was_voice = is_voice_now

                # Gestión de armado/desarmado con silencio
                if not is_voice_now:
                    consecutive_silence += 1
                    if not armed and consecutive_silence >= silence_required_chunks:
                        armed = True
                        consecutive_hits = 0
                        probs_hist.clear()
                    # actualizar baseline lentamente en silencio si hay historial
                    if len(probs_hist):
                        baseline_prob = (1.0 - alpha) * baseline_prob + alpha * float(probs_hist[-1])
                    continue
                else:
                    consecutive_silence = 0

                # Si no está armado, no evaluar todavía
                if not armed:
                    continue

                # cooldown tras activación (adicional)
                if time.time() - last_activation_ts < COOL_DOWN_SEC:
                    print(f"Wakeword: No | acierto=0%", flush=True)
                    continue

                # Actualizar historial y promedio
                probs_hist.append(prob_inst)
                avg_prob = float(np.mean(probs_hist))

                # Detección relativa sobre línea base
                if avg_prob >= (baseline_prob + delta_up):
                    consecutive_hits += 1
                elif avg_prob <= (baseline_prob + delta_down):
                    consecutive_hits = 0

                detected = consecutive_hits >= hits_required
                yesno = "Sí" if detected else "No"
                if detected:
                    acierto = int(round(avg_prob * 100))
                    print(f"Wakeword: Sí | acierto={acierto}%", flush=True)
                    last_activation_ts = time.time()
                    active = False
                    armed = False
                    consecutive_hits = 0
                    probs_hist.clear()
                    continue

                # No detectado aún: informar
                acierto = int(round(avg_prob * 100))
                print(f"Wakeword: No | acierto={acierto}%", flush=True)

    except KeyboardInterrupt:
        print("🛑 Interrupción recibida. Cerrando...")
    except Exception as e:
        print("Error:", e)

def compute_mfcc(audio, sample_rate=SAMPLE_RATE, num_mfcc=13,
                 frame_length_ms=25, frame_step_ms=10, num_mel_bins=40, fft_length=512):
    """Devuelve MFCC en shape (num_frames, num_mfcc)."""
    audio = tf.convert_to_tensor(audio, dtype=tf.float32)
    frame_length = int(sample_rate * frame_length_ms / 1000)
    frame_step = int(sample_rate * frame_step_ms / 1000)
    stft = tf.signal.stft(audio,
                          frame_length=frame_length,
                          frame_step=frame_step,
                          fft_length=fft_length,
                          window_fn=tf.signal.hann_window)
    spectrogram = tf.abs(stft)
    num_spectrogram_bins = spectrogram.shape[-1]
    mel_w = tf.signal.linear_to_mel_weight_matrix(
        num_mel_bins=num_mel_bins,
        num_spectrogram_bins=num_spectrogram_bins,
        sample_rate=sample_rate
    )
    mel_spectrogram = tf.tensordot(spectrogram, mel_w, 1)
    mel_spectrogram.set_shape(spectrogram.shape[:-1].concatenate(mel_w.shape[-1:]))
    log_mel = tf.math.log(mel_spectrogram + 1e-6)
    mfcc = tf.signal.mfccs_from_log_mel_spectrograms(log_mel)[..., :num_mfcc]
    return mfcc.numpy()

def _fit_length_along_last_axis(arr: np.ndarray, desired_len: int) -> np.ndarray:
    """Recorta o rellena con ceros arr a lo largo del último eje hasta desired_len."""
    current = arr.shape[-1]
    if current == desired_len:
        return arr
    if current > desired_len:
        return arr[..., :desired_len]
    pad_shape = list(arr.shape)
    pad_shape[-1] = desired_len - current
    padding = np.zeros(pad_shape, dtype=arr.dtype)
    return np.concatenate([arr, padding], axis=-1)

def prepare_input_for_model_oriented(mfcc_frames: np.ndarray, orientation: str) -> np.ndarray:
    """Adapta MFCC a la forma y tipo del modelo TFLite con orientación:
    orientation in {"hw", "wh"} => "hw": H=num_mfcc, W=tiempo; "wh": H=tiempo, W=num_mfcc."""
    target_shape = input_details[0]['shape']  # p.ej., [1, H, W, 1] o [1, N]
    target_dtype = input_details[0]['dtype']

    # MFCC en (frames, num_mfcc)
    if mfcc_frames.ndim != 2:
        mfcc_frames = np.reshape(mfcc_frames, (-1, mfcc_frames.shape[-1]))

    num_frames, num_coeffs = mfcc_frames.shape

    def to_nhwc(h: int, w: int) -> np.ndarray:
        if orientation == "hw":
            # H=num_mfcc, W=tiempo
            feat = mfcc_frames.T  # (num_mfcc, num_frames)
        else:
            # H=tiempo, W=num_mfcc
            feat = mfcc_frames  # (num_frames, num_mfcc)
        feat = _fit_length_along_last_axis(feat, w)  # ajustar W
        if feat.shape[0] != h:
            if feat.shape[0] > h:
                feat = feat[:h, :]
            else:
                feat = np.pad(feat, ((0, h - feat.shape[0]), (0, 0)))
        feat = feat[..., np.newaxis]  # (H, W, 1)
        feat = np.expand_dims(feat, 0)  # (1, H, W, 1)
        return feat.astype(np.float32)

    rank = len(target_shape)
    if rank == 4:
        _, H, W, C = target_shape
        x = to_nhwc(H, W)
    elif rank == 2:
        # Aplanado
        _, N = target_shape
        flat = mfcc_frames.flatten()
        if flat.size < N:
            flat = np.pad(flat, (0, N - flat.size))
        elif flat.size > N:
            flat = flat[:N]
        x = np.expand_dims(flat.astype(np.float32), 0)
    else:
        # Forma desconocida: mejor devolver ceros con esa forma
        x = np.zeros(target_shape, dtype=np.float32)

    # Cuantización de entrada si aplica
    if target_dtype in (np.uint8, np.int8):
        scale, zero_point = input_details[0].get('quantization', (0.0, 0))
        if scale and scale > 0:
            q = np.round(x / scale + zero_point)
            info = np.iinfo(target_dtype)
            q = np.clip(q, info.min, info.max).astype(target_dtype)
            return q
    return x

def run_inference(block_audio: np.ndarray) -> float:
    """Ejecuta el modelo y devuelve probabilidad (float), probando variantes de orientación/preénfasis si están en AUTO."""
    x_raw = block_audio.astype(np.float32)
    x_raw = np.clip(x_raw, -1.0, 1.0)
    # Variante con pre-énfasis: centrar y normalizar por RMS
    x = x_raw - np.mean(x_raw)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-8
    x = x / rms
    x_pre = np.append(x[0], x[1:] - 0.97 * x[:-1])

    variants_pre = [("pre", x_pre), ("raw", x_raw)] if PREEMPH_AUTO else [("pre", x_pre)]
    variants_orient = ["hw", "wh"] if ORIENTATION_AUTO else ["hw"]

    best_prob = None
    best_conf = -1.0
    best_mode = ""

    for pre_name, sig in variants_pre:
        mfcc = compute_mfcc(sig)
        for orient in variants_orient:
            model_input = prepare_input_for_model_oriented(mfcc, orient)
            interpreter.set_tensor(input_details[0]['index'], model_input)
            interpreter.invoke()
            output = interpreter.get_tensor(output_details[0]['index'])

            # De-cuantizar salida si aplica
            out = output
            out_dtype = output_details[0]['dtype']
            if out_dtype in (np.uint8, np.int8):
                scale, zero_point = output_details[0].get('quantization', (0.0, 0))
                if scale and scale > 0:
                    out = (out.astype(np.float32) - zero_point) * scale

            prob = float(_extract_probability(out))
            conf = abs(prob - 0.5)
            if conf > best_conf:
                best_conf = conf
                best_prob = prob
                best_mode = f"mode={orient}+{pre_name}"

    # Guardar modo elegido en el debug tail si aplica en impresión posterior
    global _last_chosen_mode
    try:
        _last_chosen_mode = best_mode
    except Exception:
        pass
    return float(best_prob if best_prob is not None else 0.5)

def _extract_probability(output: np.ndarray) -> float:
    """Devuelve probabilidad de wakeword a partir de distintas formas de salida."""
    global _printed_model_info_once
    global _last_prob_vector
    out = np.array(output).astype(np.float32)

    # Log único para depurar
    if not _printed_model_info_once:
        try:
            print(f"[INFO] input_shape={input_details[0]['shape']}, input_dtype={input_details[0]['dtype']}")
            print(f"[INFO] output_shape={output_details[0]['shape']}, output_dtype={output_details[0]['dtype']}")
            print(f"[INFO] sample_output_minmax=({out.min():.4f}, {out.max():.4f})")
        except Exception:
            pass
        _printed_model_info_once = True

    # Quitar dimensión batch si está presente
    if out.ndim >= 2 and out.shape[0] == 1:
        out = out[0]

    # Casos típicos
    if out.ndim == 0:
        return float(out)

    if out.ndim == 1:
        n = out.shape[0]
        # 1 salida: asume sigmoide/logit; si fuera logit aplica sigmoide
        if n == 1:
            val = out[0]
            if val < 0.0 or val > 1.0:
                # probable logit
                return 1.0 / (1.0 + np.exp(-val))
            return float(np.clip(val, 0.0, 1.0))
        # 2 salidas: softmax y usamos clase 1 como wakeword
        if n == 2:
            # si parecen logits o no suman 1, aplicar softmax
            if not np.isclose(np.sum(out), 1.0, atol=1e-3):
                e = np.exp(out - np.max(out))
                sm = e / np.sum(e)
            else:
                sm = out
            _last_prob_vector = sm
            idx = WAKEWORD_CLASS_INDEX if WAKEWORD_CLASS_INDEX < sm.shape[0] else 1
            return float(np.clip(sm[idx], 0.0, 1.0))
        # >2 salidas: tomar la mayor prob tras softmax
        e = np.exp(out - np.max(out))
        sm = e / np.sum(e)
        _last_prob_vector = sm
        return float(np.clip(np.max(sm), 0.0, 1.0))

    # Si llega en 2D (p.ej., [N, 1] o [N, 2])
    if out.ndim == 2:
        if out.shape[1] == 1:
            val = out[0, 0]
            if val < 0.0 or val > 1.0:
                return 1.0 / (1.0 + np.exp(-val))
            return float(np.clip(val, 0.0, 1.0))
        if out.shape[1] == 2:
            row = out[0]
            if not np.isclose(np.sum(row), 1.0, atol=1e-3):
                e = np.exp(row - np.max(row))
                sm = e / np.sum(e)
            else:
                sm = row
            _last_prob_vector = sm
            idx = WAKEWORD_CLASS_INDEX if WAKEWORD_CLASS_INDEX < sm.shape[0] else 1
            return float(np.clip(sm[idx], 0.0, 1.0))
        # genérico
        row = out[0]
        e = np.exp(row - np.max(row))
        sm = e / np.sum(e)
        _last_prob_vector = sm
        return float(np.clip(np.max(sm), 0.0, 1.0))

    # fallback
    flat = out.ravel()
    if flat.size == 0:
        return 0.0
    val = flat[0]
    if val < 0.0 or val > 1.0:
        return 1.0 / (1.0 + np.exp(-val))
    return float(np.clip(val, 0.0, 1.0))

def is_voice(block: np.ndarray) -> bool:
    return float(np.mean(block ** 2)) > THRESHOLD_VOICE


def main():
    print("🎧 Abriendo micrófono y escuchando continuamente. (Ctrl+C para salir)")
    audio_q = queue.Queue()
    buffer = np.zeros(0, dtype=np.float32)
    block_samples = int(SAMPLE_RATE * BLOCK_DURATION)
    hop_samples = max(1, int(block_samples * 0.5))  # 50% solapamiento

    # Suavizado e histéresis
    probs_hist = deque(maxlen=5)
    consecutive_hits = 0
    HI = WAKEWORD_THRESHOLD
    LO = max(0.0, HI - 0.10)
    active = False  # estado actual de wakeword

    def callback(indata, frames, ctime, status):
        if status:
            print(f"⚠️  Estado de audio: {status}", flush=True)
        audio_q.put(indata.copy().reshape(-1))

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE,
                            channels=1,
                            dtype='float32',
                            blocksize=int(SAMPLE_RATE * 0.1),  # ~100 ms
                            callback=callback):
            print("Esperando voz...")
            while True:
                try:
                    data = audio_q.get(timeout=1.0)
                except queue.Empty:
                    continue

                buffer = np.concatenate([buffer, data])

                while buffer.size >= block_samples:
                    block = buffer[:block_samples]
                    buffer = buffer[hop_samples:]

                    if is_voice(block):
                        prob = run_inference(block)
                        probs_hist.append(prob)
                        avg_prob = float(np.mean(probs_hist))

                        if avg_prob >= HI:
                            consecutive_hits += 1
                        elif avg_prob <= LO:
                            consecutive_hits = 0

                        detected = consecutive_hits >= 2
                        yesno = "Sí" if detected else "No"
                        transition = ""
                        if detected and not active:
                            transition = " [ACTIVADO]"
                        elif not detected and active:
                            transition = " [DESACTIVADO]"
                        active = detected

                        # Depuración limitada: imprime vector de probabilidades normalizado cuando exista
                        global _last_prob_vector, _debug_voice_prints_remaining
                        debug_tail = ""
                        if _last_prob_vector is not None and _debug_voice_prints_remaining > 0:
                            try:
                                vec = _last_prob_vector
                                if vec.ndim > 1:
                                    vec = vec.ravel()
                                if vec.size <= 6:
                                    debug_tail = f" | dist={np.round(vec, 2)}"
                                else:
                                    debug_tail = f" | p[wake]={vec[min(WAKEWORD_CLASS_INDEX, vec.size-1)]:.2f}"
                                _debug_voice_prints_remaining -= 1
                            except Exception:
                                pass

                        # anexa modo elegido si existe
                        global _last_chosen_mode
                        mode_tail = f" | {_last_chosen_mode}" if '_last_chosen_mode' in globals() and _last_chosen_mode else ""
                        print(f"Wakeword: {yesno}{transition} | prob_inst={prob:.2f} | prob={avg_prob:.2f}{debug_tail}{mode_tail}", flush=True)

    except KeyboardInterrupt:
        print("🛑 Interrupción recibida. Cerrando...")
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    # Si está disponible OpenWakeWord, usar su pipeline directo
    if OWWModel is not None:
        main_oww()
    else:
        main()
