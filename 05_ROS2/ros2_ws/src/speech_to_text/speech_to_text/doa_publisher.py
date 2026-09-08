# DOA publishes Direction Of Audio source, and Voice Activity Detection (VAD) is a key part of the process.
# This code is a ROS2 node that publishes DOA and VAD data.

import usb.core
import usb.util
import time
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from body_interfaces.msg import DOA


sys.path.append("/home/udito/OneDrive/UDITO/udito/src/audio/respeaker/usb_4_mic_array")
from tuning import Tuning

class DOAPublisher(Node):

    def __init__(self):
        super().__init__('doa_publisher')
        self.dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
        self.publisher_ = self.create_publisher(DOA, 'doa_topic', 10)
        timer_period = 0.1  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0
        if self.dev:
            self.mic = Tuning(self.dev)
            self.mic.set_vad_threshold(3)
            self.get_logger().info('Mic found')

    def timer_callback(self):
        msg = DOA()
        if self.dev:
            if(self.mic.is_voice()):
                msg.angle = self.mic.direction
                msg.vad = 1
                print(self.mic.direction)
            else:
                msg.vad = 0
            self.publisher_.publish(msg)
#            self.get_logger().info('publishing.angle: "%d", vad:%d' %(msg.angle, msg.vad))  

def main(args=None):
    rclpy.init(args=args)

    minimal_publisher = DOAPublisher()

    rclpy.spin(minimal_publisher)

    minimal_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()