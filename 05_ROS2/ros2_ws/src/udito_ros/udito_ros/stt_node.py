"""Arquitectura 3T - UDITO · Capa reactiva · Sensor OÍDO (STT Whisper).

Escucha el micrófono con detección de voz por energía, transcribe con el
motor Whisper del repo y publica el texto en /udito/stt/text.
El C.C. lo silencia (/udito/stt/enable = false) mientras el robot habla.
"""
from __future__ import annotations

import collections
import json
import queue
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import topics
from udito_ros.paths import SERVICES, add_engine_paths


class SttNode(Node):
    def __init__(self) -> None:
        super().__init__("udito_stt")
        self.declare_parameter("energy_factor", 3.0)   # umbral = ruido * factor
        self.declare_parameter("min_rms", 0.010)        # umbral mínimo absoluto
        self.declare_parameter("silence_sec", 0.9)      # silencio que cierra la frase
        self.declare_parameter("max_sec", 8.0)          # duración máxima de una frase
        self.declare_parameter("min_speech_sec", 0.4)   # descarta ruidos cortos
        self.declare_parameter("calib_sec", 1.5)        # calibración de ruido al arrancar
        self.declare_parameter("wake_word", "")         # p. ej. "udito" (vacío = sin palabra clave)

        add_engine_paths("stt-engine")
        import robot_common as rc
        from whisper_stt import WhisperSTT

        self.rc = rc
        self.stt = WhisperSTT(
            config_path=str(SERVICES / "stt-engine" / "config" / "STT_config.json"),
            project_root=str(SERVICES / "stt-engine"),
        )
        self.enabled = True
        self._q: queue.Queue[np.ndarray] = queue.Queue()

        self.pub_text = self.create_publisher(String, topics.STT_TEXT, 10)
        self.pub_state = self.create_publisher(String, topics.STATE, 10)
        self.create_subscription(Bool, topics.STT_ENABLE, self._on_enable, 10)

        threading.Thread(target=self._loop, daemon=True).start()

    # ---- control desde el C.C. ----
    def _on_enable(self, msg: Bool) -> None:
        self.enabled = bool(msg.data)
        self._drain()
        self.get_logger().info("micrófono " + ("ABIERTO" if self.enabled else "cerrado"))

    def _drain(self) -> None:
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _state(self, state: str) -> None:
        m = String()
        m.data = json.dumps({"state": state})
        self.pub_state.publish(m)

    def _p(self, name: str):
        return self.get_parameter(name).value

    # ---- bucle de audio ----
    def _loop(self) -> None:
        import sounddevice as sd

        rc = self.rc
        dev = rc.audio_input_device()
        rate = rc.input_device_sample_rate(dev, 16000)
        channels, _ = rc.input_capture_channels(dev)
        block = int(rate * 0.03)

        def cb(indata, frames, t, status):  # noqa: ANN001
            self._q.put(rc.mono_from_capture(indata))

        with sd.InputStream(
            device=dev, samplerate=rate, channels=channels, dtype="float32",
            blocksize=block, callback=cb,
        ):
            # calibración de ruido ambiente
            self.get_logger().info("Calibrando ruido ambiente (silencio, por favor)…")
            levels = []
            t_end = time.time() + float(self._p("calib_sec"))
            while time.time() < t_end:
                levels.append(rc.block_rms(self._q.get()))
            floor = float(np.median(levels)) if levels else 0.0
            thresh = max(float(self._p("min_rms")), floor * float(self._p("energy_factor")))
            self.get_logger().info(f"STT listo — ruido={floor:.4f} umbral={thresh:.4f} (dev={dev}, {rate} Hz)")
            self._state("session_listening")

            preroll: collections.deque = collections.deque(maxlen=max(1, int(0.3 / 0.03)))
            recording = False
            buf: list[np.ndarray] = []
            silence = 0.0
            speech = 0.0
            while rclpy.ok():
                chunk = self._q.get()
                if not self.enabled:
                    recording, buf = False, []
                    continue
                dur = len(chunk) / rate
                rms = rc.block_rms(chunk)
                if not recording:
                    preroll.append(chunk)
                    if rms > thresh:
                        recording, buf, silence, speech = True, list(preroll), 0.0, dur
                    continue
                buf.append(chunk)
                if rms > thresh:
                    silence, speech = 0.0, speech + dur
                else:
                    silence += dur
                total = sum(len(b) for b in buf) / rate
                if silence >= float(self._p("silence_sec")) or total >= float(self._p("max_sec")):
                    recording = False
                    audio = np.concatenate(buf)
                    buf = []
                    preroll.clear()
                    if speech >= float(self._p("min_speech_sec")):
                        self._transcribe(audio, rate)
                    self._drain()
                    if self.enabled:
                        self._state("session_listening")

    def _transcribe(self, audio: np.ndarray, rate: int) -> None:
        if rate != 16000:
            audio = self.rc.resample_mono(audio, rate, 16000)
        t0 = time.time()
        try:
            text = self.stt.transcribe_pcm(audio, 16000) or ""
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f"Whisper error: {e}")
            return
        text = text.strip()
        if not text:
            return
        wake = str(self._p("wake_word") or "").strip().lower()
        if wake and wake != "none":
            low = text.lower()
            if wake not in low:
                self.get_logger().info(f"(ignorado, sin «{wake}»): {text}")
                return
            text = low.split(wake, 1)[1].strip(" ,.!¿?¡") or "hola"
        self.get_logger().info(f"[oído] «{text}» ({time.time() - t0:.1f}s)")
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
