"""Ejemplo ROS2: escucha /udito/wakeword y /udito/state del pipeline offline."""

from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class UditoWakewordListener(Node):
    def __init__(self) -> None:
        super().__init__("udito_wakeword_listener")
        self.create_subscription(String, "/udito/wakeword", self._on_wakeword, 10)
        self.create_subscription(String, "/udito/state", self._on_state, 10)
        self.get_logger().info("Escuchando /udito/wakeword y /udito/state")

    def _on_wakeword(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            print(f"[wakeword] {msg.data}")
            return
        active = data.get("ros2_active", "?")
        print(
            f"[wakeword] «{data.get('wake_word', '?')}» "
            f"p={data.get('probability', 0):.2f} "
            f"ros2_active={active}"
        )

    def _on_state(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            print(f"[state] {msg.data}")
            return
        print(f"[state] {data.get('state', msg.data)}")


def main() -> None:
    rclpy.init()
    node = UditoWakewordListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
