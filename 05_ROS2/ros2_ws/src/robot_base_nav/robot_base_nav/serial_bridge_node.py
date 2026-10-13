#!/usr/bin/env python3
"""
Puente serie entre ROS 2 y el Arduino que controla las 2 ruedas (PID de bajo nivel).

Protocolo serie:
  ROS2 -> Arduino:  "V <wL> <wR>\n"           wL, wR en rad/s de cada rueda
  Arduino -> ROS2:  "O <ticksL> <ticksR> <measL> <measR>\n"
                     ticksL/R: contador acumulado de pulsos (con signo)
                     measL/R : velocidad angular medida de cada rueda (rad/s)
"""
import math
import threading
import queue
import time

import serial

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile

from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster


def yaw_to_quaternion(yaw):
    """Cuaternión (x, y, z, w) para una rotación pura en yaw (caso 2D)."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


class SerialBridgeNode(Node):

    def __init__(self):
        super().__init__('serial_bridge_node')

        # ---------------- Parámetros ----------------
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('wheel_radius', 0.0325)      # metros, AJUSTAR
        self.declare_parameter('wheel_separation', 0.20)    # metros, AJUSTAR
        self.declare_parameter('cmd_resend_rate', 20.0)     # Hz
        self.declare_parameter('cmd_timeout', 0.5)          # s
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('publish_tf', True)

        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.wheel_separation = self.get_parameter('wheel_separation').value
        self.cmd_timeout = self.get_parameter('cmd_timeout').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.publish_tf = self.get_parameter('publish_tf').value

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value

        # ---------------- Estado odometría ----------------
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.wheel_angle_l = 0.0
        self.wheel_angle_r = 0.0
        self.last_odom_time = self.get_clock().now()

        # ---------------- Estado comando ----------------
        self.target_linear = 0.0
        self.target_angular = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.cmd_lock = threading.Lock()

        # ---------------- Puerto serie ----------------
        try:
            self.ser = serial.Serial(port, baud, timeout=0.05)
        except serial.SerialException as e:
            self.get_logger().error(f'No se pudo abrir el puerto serie {port}: {e}')
            raise

        self.rx_queue = queue.Queue()
        self.stop_thread = False
        self.reader_thread = threading.Thread(target=self._serial_reader_loop, daemon=True)
        self.reader_thread.start()

        # ---------------- ROS I/O ----------------
        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, 'odom', QoSProfile(depth=10))
        self.joint_pub = self.create_publisher(JointState, 'joint_states', QoSProfile(depth=10))
        self.tf_broadcaster = TransformBroadcaster(self)

        resend_period = 1.0 / self.get_parameter('cmd_resend_rate').value
        self.cmd_timer = self.create_timer(resend_period, self.send_cmd_to_arduino)
        self.rx_timer = self.create_timer(0.01, self.process_serial_queue)

        self.get_logger().info(f'Puente serie iniciado en {port} @ {baud} baudios')

    # ---------------- cmd_vel -> Arduino ----------------
    def cmd_vel_callback(self, msg: Twist):
        with self.cmd_lock:
            self.target_linear = msg.linear.x
            self.target_angular = msg.angular.z
            self.last_cmd_time = self.get_clock().now()

    def send_cmd_to_arduino(self):
        with self.cmd_lock:
            elapsed = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9
            if elapsed > self.cmd_timeout:
                lin, ang = 0.0, 0.0
            else:
                lin, ang = self.target_linear, self.target_angular

        v_l = lin - (ang * self.wheel_separation / 2.0)
        v_r = lin + (ang * self.wheel_separation / 2.0)

        w_l = v_l / self.wheel_radius   # rad/s de la rueda
        w_r = v_r / self.wheel_radius

        line = f'V {w_l:.4f} {w_r:.4f}\n'
        try:
            self.ser.write(line.encode('utf-8'))
        except serial.SerialException as e:
            self.get_logger().warn(f'Error escribiendo en el puerto serie: {e}')

    # ---------------- Arduino -> ROS2 ----------------
    def _serial_reader_loop(self):
        buffer = b''
        while not self.stop_thread:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 1)
            except serial.SerialException:
                time.sleep(0.1)
                continue
            if not chunk:
                continue
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                decoded = line.decode('utf-8', errors='ignore').strip()
                if decoded:
                    self.rx_queue.put(decoded)

    def process_serial_queue(self):
        now = self.get_clock().now()
        while not self.rx_queue.empty():
            line = self.rx_queue.get_nowait()
            self._handle_telemetry_line(line, now)

    def _handle_telemetry_line(self, line: str, now):
        parts = line.split()
        if len(parts) != 5 or parts[0] != 'O':
            return
        try:
            _ticks_l = int(parts[1])
            _ticks_r = int(parts[2])
            meas_l = float(parts[3])   # rad/s rueda izquierda
            meas_r = float(parts[4])   # rad/s rueda derecha
        except ValueError:
            self.get_logger().warn(f'Línea de telemetría malformada: "{line}"')
            return

        dt = (now - self.last_odom_time).nanoseconds / 1e9
        self.last_odom_time = now
        if dt <= 0.0:
            return

        self._update_odometry(meas_l, meas_r, dt, now)
        self._publish_joint_states(meas_l, meas_r, dt, now)

    # ---------------- Odometría ----------------
    def _update_odometry(self, meas_l, meas_r, dt, stamp):
        v_l = meas_l * self.wheel_radius
        v_r = meas_r * self.wheel_radius

        v = (v_l + v_r) / 2.0
        w = (v_r - v_l) / self.wheel_separation

        delta_theta = w * dt
        mid_theta = self.theta + delta_theta / 2.0

        self.x += v * math.cos(mid_theta) * dt
        self.y += v * math.sin(mid_theta) * dt
        self.theta += delta_theta
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

        qx, qy, qz, qw = yaw_to_quaternion(self.theta)

        odom_msg = Odometry()
        odom_msg.header.stamp = stamp.to_msg()
        odom_msg.header.frame_id = self.odom_frame
        odom_msg.child_frame_id = self.base_frame

        odom_msg.pose.pose.position.x = self.x
        odom_msg.pose.pose.position.y = self.y
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.pose.pose.orientation.x = qx
        odom_msg.pose.pose.orientation.y = qy
        odom_msg.pose.pose.orientation.z = qz
        odom_msg.pose.pose.orientation.w = qw

        odom_msg.twist.twist.linear.x = v
        odom_msg.twist.twist.angular.z = w

        # Covarianzas orientativas: AJUSTAR según el comportamiento real observado
        odom_msg.pose.covariance[0] = 0.01
        odom_msg.pose.covariance[7] = 0.01
        odom_msg.pose.covariance[35] = 0.05
        odom_msg.twist.covariance[0] = 0.01
        odom_msg.twist.covariance[35] = 0.05

        self.odom_pub.publish(odom_msg)

        if self.publish_tf:
            t = TransformStamped()
            t.header.stamp = stamp.to_msg()
            t.header.frame_id = self.odom_frame
            t.child_frame_id = self.base_frame
            t.transform.translation.x = self.x
            t.transform.translation.y = self.y
            t.transform.translation.z = 0.0
            t.transform.rotation.x = qx
            t.transform.rotation.y = qy
            t.transform.rotation.z = qz
            t.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(t)

    def _publish_joint_states(self, meas_l, meas_r, dt, stamp):
        self.wheel_angle_l += meas_l * dt
        self.wheel_angle_r += meas_r * dt

        js = JointState()
        js.header.stamp = stamp.to_msg()
        js.name = ['wheel_left_joint', 'wheel_right_joint']
        js.position = [self.wheel_angle_l, self.wheel_angle_r]
        js.velocity = [meas_l, meas_r]
        self.joint_pub.publish(js)

    def destroy_node(self):
        self.stop_thread = True
        try:
            self.ser.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
