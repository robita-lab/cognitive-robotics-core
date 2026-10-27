"""Arquitectura 3T - UDITO · Capa reactiva · Actuador VOZ (TTS Piper).

Solo obedece al C.C.: escucha /udito/tts/say, habla, y avisa en /udito/tts/done.
Publica la emoción en /udito/speech_out para que el rostro se sincronice.
"""
from __future__ import annotations

import json
import os
import queue
import threading

os.environ.setdefault("ROBITA_ROS2_SPEECH", "0")  # publicamos nosotros, sin nodos paralelos

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from udito_ros import topics  # noqa: E402
from udito_ros.paths import SERVICES, add_engine_paths  # noqa: E402


class TtsNode(Node):
    def __init__(self) -> None:
        super().__init__("udito_tts")
        add_engine_paths("tts-engine")
        from piper_tts_real import PiperTTS
        import robot_common
        import udito_speech

        self._speech = udito_speech
        self._play_raw = robot_common.play_wav_bytes
        cfg = os.getenv(
            "ROBITA_TTS_CONFIG", str(SERVICES / "tts-engine" / "config" / "tts_config.json")
        )
        self.tts = PiperTTS(config_path=cfg)
        # Volumen guardado en la pantalla de audio (software + hardware si se puede)
        import udito_audio

        self._audio = udito_audio
        self._volume = udito_audio.env_volume()
        try:
            udito_audio.apply_env_volume()
        except Exception as e:  # noqa: BLE001
            self.get_logger().warning(f"Volumen hardware no aplicado: {e}")
        self.get_logger().info(f"Volumen voz: {self._volume}%")

        self.pub_face = self.create_publisher(String, topics.SPEECH_OUT, 10)
        self.pub_state = self.create_publisher(String, topics.STATE, 10)
        self.pub_done = self.create_publisher(String, topics.TTS_DONE, 10)
        self.create_subscription(String, topics.TTS_SAY, self._on_say, 10)

        self._q: queue.Queue[dict] = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()
        self.get_logger().info(f"TTS listo — escuchando {topics.TTS_SAY}")

    def _play(self, wav: bytes) -> None:
        self._play_raw(self._audio.scale_wav(wav, self._volume))

    def _on_say(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            if not isinstance(data, dict):
                data = {"text": str(data)}
        except json.JSONDecodeError:
            data = {"text": msg.data}
        self._q.put(data)

    def _pub(self, pub, payload: dict) -> None:
        m = String()
        m.data = json.dumps(payload, ensure_ascii=False)
        pub.publish(m)

    def _worker(self) -> None:
        while rclpy.ok():
            data = self._q.get()
            req_id = str(data.get("id", ""))
            text = self._speech.normalize_for_speech(str(data.get("text", "")))
            emotion = str(data.get("emotion", "neutral"))
            self._pub(self.pub_state, {"state": "speaking", "id": req_id})
            try:
                if text:
                    self.get_logger().info(f"[hablar] ({emotion}) {text}")
                    wav, event = self._speech.synthesize_with_pauses(self.tts, text, emotion)
                    event.source = str(data.get("source", "cc"))
                    event.label = str(data.get("label", ""))
                    self._pub(self.pub_face, event.to_dict())
                    if wav:
                        self._play(wav)
                if data.get("laugh"):
                    self._pub(
                        self.pub_face,
                        {"text": "", "emotion": "laugh", "source": "tts", "label": "risa"},
                    )
                    self._speech.play_laugh_sound(self._play)
            except Exception as e:  # noqa: BLE001
                self.get_logger().error(f"TTS error: {e}")
            finally:
                self._pub(self.pub_state, {"state": "idle", "id": req_id})
                self._pub(self.pub_done, {"id": req_id})


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TtsNode()
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
