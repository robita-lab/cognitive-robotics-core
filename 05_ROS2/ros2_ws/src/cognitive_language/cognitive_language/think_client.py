"""Cliente de prueba de la acción Think.

  ros2 run cognitive_language think_client "¿quién eres?"
  ros2 run cognitive_language think_client --cancel-after 0.05 "pregunta larga"
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from cognitive_language_interfaces.action import Think


def main(argv: list[str] | None = None) -> int:
    argv = rclpy.utilities.remove_ros_args(argv if argv is not None else sys.argv)[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="+")
    ap.add_argument("--action", default="/udito/cognitive/think")
    ap.add_argument("--session", default=f"cli-{uuid.uuid4().hex[:6]}")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--cancel-after", type=float, default=0.0, help="cancela el goal tras N segundos")
    args = ap.parse_args(argv)

    rclpy.init()
    node = Node("think_client")
    client = ActionClient(node, Think, args.action)
    if not client.wait_for_server(timeout_sec=10.0):
        print(f"no hay servidor en {args.action}", file=sys.stderr)
        return 2

    goal = Think.Goal()
    goal.header.stamp = node.get_clock().now().to_msg()
    goal.session_id = args.session
    goal.turn_id = uuid.uuid4().hex[:8]
    goal.text = " ".join(args.text)

    def on_feedback(msg) -> None:
        print(f"  [{msg.feedback.index}] {msg.feedback.partial_text}", flush=True)

    send = client.send_goal_async(goal, feedback_callback=on_feedback)
    rclpy.spin_until_future_complete(node, send, timeout_sec=args.timeout)
    handle = send.result()
    if handle is None or not handle.accepted:
        print("goal rechazado", file=sys.stderr)
        return 3
    if args.cancel_after > 0:
        end = time.monotonic() + args.cancel_after
        while time.monotonic() < end:  # spin_once vuelve con cada mensaje: esperar el tiempo pedido
            rclpy.spin_once(node, timeout_sec=max(0.01, end - time.monotonic()))
        print(f"  (cancelando tras {args.cancel_after:.1f} s)", flush=True)
        rclpy.spin_until_future_complete(node, handle.cancel_goal_async(), timeout_sec=5.0)
    res_f = handle.get_result_async()
    rclpy.spin_until_future_complete(node, res_f, timeout_sec=args.timeout)
    wrapped = res_f.result()
    if wrapped is None:
        print("sin resultado (timeout)", file=sys.stderr)
        return 4
    r = wrapped.result
    print(f"status={wrapped.status} source={r.source} emotion={r.emotion} latency_ms={r.latency_ms:.0f}")
    print(r.text)
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
