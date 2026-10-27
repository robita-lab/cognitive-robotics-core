"""Arquitectura 3T - UDITO · EJEMPLO para el responsable del orquestador del CUERPO.

Este nodo NO mueve motores: muestra cómo recibir las órdenes del C.C. y dónde
conectar cada una con el cuerpo real (cuello = head_package, base = Nav2 / robot_base_nav).

Mensaje que llega por /udito/intent (std_msgs/String con JSON):
    {
      "name":   "follow",                 # acción para el cuerpo
      "args":   {"target": "person"},     # parámetros
      "intent": "follow_me",              # id de la orden en config/intents.yaml
      "text":   "sígueme",                # lo que dijo la persona
      "source": "udito_cc",
      "stamp":  1791238809.57
    }

Para probarlo sin voz:
    ros2 topic pub --once /udito/stt/text std_msgs/String "{data: sigueme}"
    ros2 topic echo /udito/intent
"""
from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from udito_ros import topics


class BodyExample(Node):
    def __init__(self) -> None:
        super().__init__("udito_body_example")
        self.create_subscription(String, topics.INTENT, self.on_intent, 10)
        # Tabla de despacho: acción → función. Añadir aquí las nuevas acciones del cuerpo.
        self.handlers = {
            "look": self.look,
            "head_gesture": self.head_gesture,
            "follow": self.follow,
            "stop": self.stop,
            "go_to": self.go_to,
            "rotate": self.rotate,
        }
        self.get_logger().info(f"[cuerpo-ejemplo] escuchando {topics.INTENT}")

    def on_intent(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning(f"mensaje no JSON: {msg.data}")
            return
        handler = self.handlers.get(data.get("name", ""))
        if handler is None:
            self.get_logger().info(f"[cuerpo-ejemplo] acción sin implementar: {data.get('name')}")
            return
        handler(data.get("args", {}))

    # ---- CUELLO (head_package: servicio HeadMove de body_interfaces) ----
    def look(self, args: dict) -> None:
        self.get_logger().info(
            f"[cuerpo-ejemplo] CUELLO gira {args.get('degrees', 45)}° a la {args.get('direction')} "
            "→ aquí: cliente del servicio head_package/HeadMove")

    def head_gesture(self, args: dict) -> None:
        self.get_logger().info(
            f"[cuerpo-ejemplo] CUELLO gesto «{args.get('gesture')}» x{args.get('times', 1)} "
            "→ aquí: secuencia de HeadMove (arriba/abajo o izq/der)")

    # ---- BASE (robot_base_nav / Nav2) ----
    def follow(self, args: dict) -> None:
        self.get_logger().info(
            f"[cuerpo-ejemplo] BASE sigue a «{args.get('target')}» "
            "→ aquí: activar seguimiento (lidar/cámara) y enviar metas a Nav2")

    def stop(self, args: dict) -> None:
        self.get_logger().info("[cuerpo-ejemplo] BASE y CUELLO se detienen → aquí: cancelar metas Nav2 + /cmd_vel = 0")

    def go_to(self, args: dict) -> None:
        self.get_logger().info(
            f"[cuerpo-ejemplo] BASE va hacia «{args.get('target')}» → aquí: acción NavigateToPose de Nav2")

    def rotate(self, args: dict) -> None:
        self.get_logger().info(
            f"[cuerpo-ejemplo] BASE gira {args.get('degrees', 360)}° → aquí: /cmd_vel angular o Spin de Nav2")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BodyExample()
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
