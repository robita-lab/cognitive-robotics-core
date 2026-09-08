from body_interfaces.srv import ComActMsg

import rclpy
from rclpy.node import Node 
import sys
sys.path.append("/home/udito/OneDrive/UDITO/udito/src/audio")
from ComAct import ComAct

class ComActClient(Node):
    def __init__(self):
        super().__init__('com_act_client')
        self.cli = self.create_client(ComActMsg, 'com_act_server')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.req = ComActMsg.Request()

    def send_request(self, text, gesture, gesture_parameter):
        self.req.text = text
        self.req.gesture = gesture
        self.req.data = gesture_parameter
        return self.cli.call_async(self.req)

    
def main():
    rclpy.init()
    com_act_client = ComActClient()
    future = com_act_client.send_request("Hola, soy un cliente", "HAPPY", 10)
    rclpy.spin_until_future_complete(com_act_client, future)
    response = future.result()
    com_act_client.get_logger().info(
        'Result of com_act_client: %s' % response.rta)
    com_act_client.destroy_node()
    rclpy.shutdown()    

if __name__ == '__main__':
    main()
