"""Mock ComAct service — logs every request and returns ACK.

Used by the test launch file so the dialog manager node can be exercised
without the real head / TTS subsystems attached. Matches the ComActMsg.srv
contract so the dialog manager treats it as the real thing.
"""

from __future__ import annotations

import rclpy
from body_interfaces.srv import ComActMsg
from rclpy.node import Node


class MockComActServer(Node):
    def __init__(self) -> None:
        super().__init__("mock_com_act_server")
        self.srv = self.create_service(ComActMsg, "com_act_server", self._on_request)
        self.get_logger().info("mock com_act_server up — logging requests, replying ACK")

    def _on_request(self, request: ComActMsg.Request, response: ComActMsg.Response):
        self.get_logger().info(
            "[mock com_act] cmd=%r gesture=%r data=%d text=%r"
            % (request.cmd, request.gesture, request.data, request.text)
        )
        response.rta = "ACK"
        return response


def main() -> None:
    rclpy.init()
    node = MockComActServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
