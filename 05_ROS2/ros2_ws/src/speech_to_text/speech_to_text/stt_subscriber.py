import rclpy
from rclpy.node import Node

from body_interfaces.msg import DOA
from body_interfaces.msg import Speech2Text


class StTSubscriber(Node):

    def __init__(self):
        super().__init__('stt_subscriber')
        self.subscription = self.create_subscription(
            DOA,                                               
            'doa_topic',
            self.listener_callback,
            10)
        self.subscription
        self.stt_sub = self.create_subscription(
            Speech2Text,
            'stt_topic',
            self.stt_callback, 
            10)
    def stt_callback(self,msg):
        self.get_logger().info('text: %s, conf: %f' %(msg.text, msg.confidence))

    def listener_callback(self, msg):
        self.get_logger().info('Angle of voice: "%d", %d' % (msg.angle, msg.vad))  


def main(args=None):
    rclpy.init(args=args)

    minimal_subscriber = StTSubscriber()

    rclpy.spin(minimal_subscriber)

    minimal_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()