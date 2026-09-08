import rclpy
from rclpy.node import Node

from body_interfaces.msg import DOA


class DOASubscriber(Node):

    def __init__(self):
        super().__init__('doa_subscriber')
        self.subscription = self.create_subscription(
            DOA,                                               
            'topic',
            self.listener_callback,
            10)
        self.subscription

    def listener_callback(self, msg):
        self.get_logger().info('Angle of voice: "%d", %d' % (msg.angle, msg.vad))  


def main(args=None):
    rclpy.init(args=args)

    minimal_subscriber = DOASubscriber()

    rclpy.spin(minimal_subscriber)

    minimal_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()