"""Arquitectura 3T - UDITO · Capa reactiva · Sensor OÍDO (STT Whisper).

Dos modos (parámetro `mode`):
  - ptt (por defecto): «mantén para hablar». Graba solo mientras /udito/stt/ptt = true
    (botón de la consola o barra espaciadora). Sin bucles ni ruidos falsos.
  - vad: escucha continua; detecta la voz por energía.
Transcribe con el Whisper del repo, orientado con el vocabulario de órdenes
(config/intents.yaml), y publica el texto en /udito/stt/text.
"""
from __future__ import annotations

import collections
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import intents as I
from udito_ros import topics
from udito_ros.paths import SERVICES, add_engine_paths


class SttNode(Node):
    def __init__(self) -> None:
        super().__init__("udito_stt")
        self.declare_parameter("mode", "ptt")            # ptt | vad
        self.declare_parameter("energy_factor", 3.0)     # vad: umbral = ruido * factor
        self.declare_parameter("min_rms", 0.010)         # vad: umbral mínimo absoluto
        self.declare_parameter("silence_sec", 0.9)       # vad: silencio que cierra la frase
        self.declare_parameter("max_sec", 8.0)           # duración máxima de una frase
        self.declare_parameter("min_speech_sec", 0.3)    # descarta toques muy cortos
        self.declare_parameter("calib_sec", 1.5)         # vad: calibración de ruido
        self.declare_parameter("model", "base")          # tiny (más rápido) · base · small (más preciso)
        self.declare_parameter("threads", 4)             # núcleos de CPU para Whisper

        add_engine_paths("stt-engine")
        import robot_common as rc
        from whisper_stt import WhisperSTT

        self.rc = rc
        self.stt = WhisperSTT(
            config_path=str(SERVICES / "stt-engine" / "config" / "STT_config.json"),
            project_root=str(SERVICES / "stt-engine"),
        )
        # Whisper propio del nodo: modelo ligero y varios núcleos (la config de bajo
        # consumo de la Jetson lo dejaba en 1 núcleo → ~13 s por frase).
        from faster_whisper import WhisperModel

        t0 = time.time()
        model = str(self.get_parameter("model").value)
        threads = int(self.get_parameter("threads").value)
        self.stt._model = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=threads)
        self.get_logger().info(f"Whisper «{model}» ({threads} núcleos) cargado en {time.time() - t0:.1f}s")
        try:
            self.prompt = I.vocabulary_prompt(I.load()["intents"])
        except Exception:  # noqa: BLE001
            self.prompt = None

        self.mode = str(self.get_parameter("mode").value)
        self.enabled = True
        self.ptt = False
        self._q: queue.Queue[np.ndarray] = queue.Queue()

        self.pub_text = self.create_publisher(String, topics.STT_TEXT, 10)
        self.pub_state = self.create_publisher(String, topics.STATE, 10)
        self.create_subscription(Bool, topics.STT_ENABLE, self._on_enable, 10)
        self.create_subscription(Bool, topics.STT_PTT, self._on_ptt, 10)

        threading.Thread(target=self._loop, daemon=True).start()

    # ---- control ----
    def _on_enable(self, msg: Bool) -> None:  # el C.C. cierra el micro mientras el robot habla
        self.enabled = bool(msg.data)

    def _on_ptt(self, msg: Bool) -> None:     # botón «mantén para hablar»
        self.ptt = bool(msg.data)

    def _drain(self) -> None:
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _state(self, state: str, **extra) -> None:
        m = String()
        m.data = json.dumps({"state": state, **extra})
        self.pub_state.publish(m)

    def _p(self, name: str):
        return self.get_parameter(name).value

    # ---- audio ----
    def _loop(self) -> None:
        import sounddevice as sd

        rc = self.rc
        dev = rc.audio_input_device()
        src = os.getenv("ROBITA_PULSE_SOURCE", "").strip()
        if dev == "pulse" and src:
            subprocess.run(["pactl", "set-default-source", src], capture_output=True)
        rate = rc.input_device_sample_rate(dev, 16000)
        channels, _ = rc.input_capture_channels(dev)
        block = int(rate * 0.03)

        def cb(indata, frames, t, status):  # noqa: ANN001
            self._q.put(rc.mono_from_capture(indata))

        with sd.InputStream(device=dev, samplerate=rate, channels=channels, dtype="float32",
                            blocksize=block, callback=cb):
            self.get_logger().info(f"STT listo — modo {self.mode.upper()} (micro={dev}, {rate} Hz)")
            if self.mode == "vad":
                self._vad_loop(rate)
            else:
                self._ptt_loop(rate)

    def _ptt_loop(self, rate: int) -> None:
        self._state("idle")
        while rclpy.ok():
            if not self.ptt:
                self._drain()
                time.sleep(0.03)
                continue
            self._drain()
            self._state("hearing")
            buf: list[np.ndarray] = []
            t0 = time.time()
            while self.ptt and rclpy.ok() and time.time() - t0 < float(self._p("max_sec")):
                try:
                    buf.append(self._q.get(timeout=0.1))
                except queue.Empty:
                    pass
            if buf:
                audio = np.concatenate(buf)
                if len(audio) / rate >= float(self._p("min_speech_sec")):
                    self._transcribe(audio, rate)
            self._state("idle")
            while self.ptt:  # si se pasó de max_sec, espera a que suelte
                time.sleep(0.05)

    def _vad_loop(self, rate: int) -> None:
        rc = self.rc
        levels, t_end = [], time.time() + float(self._p("calib_sec"))
        while time.time() < t_end:
            levels.append(rc.block_rms(self._q.get()))
        floor = float(np.median(levels)) if levels else 0.0
        thresh = max(float(self._p("min_rms")), floor * float(self._p("energy_factor")))
        self.get_logger().info(f"VAD — ruido={floor:.4f} umbral={thresh:.4f}")
        self._state("session_listening")
        preroll: collections.deque = collections.deque(maxlen=10)
        recording, buf, silence, speech = False, [], 0.0, 0.0
        while rclpy.ok():
            chunk = self._q.get()
            if not self.enabled:
                recording, buf = False, []
                continue
            dur, rms = len(chunk) / rate, rc.block_rms(chunk)
            if not recording:
                preroll.append(chunk)
                if rms > thresh:
                    recording, buf, silence, speech = True, list(preroll), 0.0, dur
                    self._state("hearing")
                continue
            buf.append(chunk)
            silence, speech = (0.0, speech + dur) if rms > thresh else (silence + dur, speech)
            total = sum(len(b) for b in buf) / rate
            if silence >= float(self._p("silence_sec")) or total >= float(self._p("max_sec")):
                recording = False
                audio, buf = np.concatenate(buf), []
                preroll.clear()
                if speech >= float(self._p("min_speech_sec")):
                    self._transcribe(audio, rate)
                self._drain()
                if self.enabled:
                    self._state("session_listening")

    def _transcribe(self, audio: np.ndarray, rate: int) -> None:
        self._state("transcribing")
        if rate != 16000:
            audio = self.rc.resample_mono(audio, rate, 16000)
        t0 = time.time()
        path = self.stt._pcm_to_wav(audio, 16000)
        try:
            segments, _ = self.stt._model.transcribe(
                path, language="es", beam_size=1, initial_prompt=self.prompt,
                condition_on_previous_text=False, vad_filter=False,
            )
            text = " ".join(s.text for s in segments).strip()
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f"Whisper error: {e}")
            return
        finally:
            Path(path).unlink(missing_ok=True)
        secs = time.time() - t0
        self._state("idle", stt_sec=round(secs, 2))
        if not text:
            self.get_logger().info(f"[oído] (nada entendido, {secs:.1f}s)")
            return
        self.get_logger().info(f"[oído] «{text}» ({secs:.1f}s)")
        m = String()
        m.data = text
        self.pub_text.publish(m)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SttNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
