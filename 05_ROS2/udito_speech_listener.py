#!/usr/bin/env python3
"""Ejemplo ROS2 offline: escucha /udito/speech_out y muestra emoción + texto."""
from __future__ import annotations

import json
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class UditoSpeechListener(Node):
    def __init__(self) -> None:
        super().__init__("udito_speech_listener")
        self.create_subscription(String, "/udito/speech_out", self._on_msg, 10)
        self.get_logger().info("Escuchando /udito/speech_out (Ctrl+C para salir)")

    def _on_msg(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn("JSON inválido")
            return
        em = data.get("emotion", "?")
        src = data.get("source", "")
        text = (data.get("text") or "")[:80]
        self.get_logger().info(f"[{em}] {src} — {text}")


def main() -> None:
    rclpy.init()
    node = UditoSpeechListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
