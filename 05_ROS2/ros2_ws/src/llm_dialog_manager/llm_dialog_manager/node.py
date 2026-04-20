"""ROS2 node wrapping the two-tier dialog flow.

Subscribes to Speech2Text, routes each turn via router.route(), dispatches
the LLM call to a worker thread (so the rclpy executor doesn't block on
HTTP), and forwards the reply to the ComAct service.

Configuration (ROS parameters, all overridable at launch):
  server_url              FastAPI server tier base URL
  local_url               FastAPI local tier base URL
  conversation_id         stable id used for server-side memory keying
  stt_confidence_threshold  below this, ask user to repeat
  default_gesture         gesture label used alongside every spoken reply
  default_duration        'data' field of ComActMsg (int64)
  response_max_tokens     cap per turn
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import rclpy
from body_interfaces.msg import Speech2Text
from body_interfaces.srv import ComActMsg
from rclpy.node import Node

from llm_dialog_manager.llm_client import LLMClient
from llm_dialog_manager.router import RoutingDecision, route


class LLMDialogManager(Node):
    def __init__(self) -> None:
        super().__init__("llm_dialog_manager")

        self.declare_parameter("server_url", "http://localhost:8080")
        self.declare_parameter("local_url", "http://localhost:8080")
        self.declare_parameter("conversation_id", "udito-session-default")
        self.declare_parameter("stt_confidence_threshold", 0.6)
        self.declare_parameter("default_gesture", "NEUTRAL")
        self.declare_parameter("default_duration", 7)
        self.declare_parameter("response_max_tokens", 80)

        server_url = self.get_parameter("server_url").get_parameter_value().string_value
        local_url = self.get_parameter("local_url").get_parameter_value().string_value

        self._clients: dict[str, LLMClient] = {
            "server": LLMClient(server_url),
            "local": LLMClient(local_url),
        }
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm-dispatch")
        self._last_decision: Optional[RoutingDecision] = None

        self.stt_sub = self.create_subscription(
            Speech2Text, "stt_topic", self._on_stt, 10
        )

        self.com_act_client = self.create_client(ComActMsg, "com_act_server")
        self._wait_for_comact()

        self.get_logger().info(
            "llm_dialog_manager up — server=%s local=%s" % (server_url, local_url)
        )

    def _wait_for_comact(self) -> None:
        while not self.com_act_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("com_act_server not available, waiting...")

    def _on_stt(self, msg: Speech2Text) -> None:
        threshold = self.get_parameter("stt_confidence_threshold").value
        if msg.confidence < threshold:
            self.get_logger().info(
                "low-confidence stt (%.2f < %.2f): %r" % (msg.confidence, threshold, msg.text)
            )
            self._send_comact("Perdona, ¿puedes repetirlo?", "NEUTRAL")
            return

        decision = route(msg.text, last_decision=self._last_decision)
        self._last_decision = decision
        self.get_logger().info(
            "routed intent=%s tier=%s text=%r" % (decision.intent, decision.tier, msg.text)
        )

        self._pool.submit(self._handle_turn, msg.text, decision)

    def _handle_turn(self, user_text: str, decision: RoutingDecision) -> None:
        client = self._clients[decision.tier]
        conv_id = self.get_parameter("conversation_id").value
        max_tokens = int(self.get_parameter("response_max_tokens").value)
        try:
            reply = client.chat(conv_id, user_text, max_tokens=max_tokens)
            self.get_logger().info(
                "%s tier replied in %dms: %r" % (decision.tier, reply.latency_ms, reply.reply)
            )
            self._send_comact(reply.reply, self.get_parameter("default_gesture").value)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(
                "llm request failed (tier=%s): %s" % (decision.tier, exc)
            )
            self._send_comact("Perdona, ahora no te oigo bien.", "SAD")

    def _send_comact(self, text: str, gesture: str, cmd: str = "speak") -> None:
        req = ComActMsg.Request()
        req.cmd = cmd
        req.text = text
        req.gesture = gesture
        req.data = int(self.get_parameter("default_duration").value)
        self.com_act_client.call_async(req)

    def destroy_node(self) -> bool:
        self._pool.shutdown(wait=False, cancel_futures=True)
        for client in self._clients.values():
            client.close()
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = LLMDialogManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
