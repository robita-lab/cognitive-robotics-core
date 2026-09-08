import sys
import rclpy
from rclpy.node import Node
from body_interfaces.srv import HeadMove
from body_interfaces.msg import DOA
from body_interfaces.srv import Behavior

class Gaze(Node):
    def __init__(self):
        super().__init__('gaze')
        self.srv = self.create_service(Behavior, 'gaze_behavior', self.gaze_callback)    
        self.cli = self.create_client(HeadMove, 'head_server')
        while not self.cli.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('head_server not available, waiting again...')
        self.req = HeadMove.Request()
        self.subscription = self.create_subscription(
            DOA,                                               
            'topic',
            self.doa_callback,
            10)
        self.subscription  # prevent unused variable warning
        self.active = 0

    def gaze_callback(self, request, response):
        self.get_logger().info('Incoming request\nactive: %d' %request.active)  
        self.active = request.active
        if request.active == 1:
            self.get_logger().info('Gaze active')
        else:
            self.get_logger().info('Gaze inactive')
        response.rta = "ACK"    
        return response

    def doa_callback(self, msg):
        if self.active == 0:
            return
        self.get_logger().info('Angle of voice: "%d", %d' % (msg.angle, msg.vad))  
        if msg.vad == 1:
#            self.cli.send_request("PAN", map_range(msg.angle, 180, 360, 60, -60))
            if (msg.angle > 180) & (msg.angle < 240):
#                self.send_request("PAN", map_range(msg.angle, 180, 360, 60, -60))
                self.move_head("PAN", -40) # RIGHT
            elif(msg.angle > 300) & (msg.angle < 360):  
                self.move_head("PAN", 40)
            elif(msg.angle >= 240) & (msg.angle <= 300):  
                self.move_head("PAN", 0)
            elif msg.angle < 90 :  
                self.move_head("PAN", 40) # LEFT
            elif(msg.angle >= 90) & (msg.angle <= 180):  
                self.move_head("PAN", -40) # LEFT
    
    def move_head(self, cmd, data):
        self.req.command = cmd
        self.req.data = data
        future = self.cli.call_async(self.req)
        future.add_done_callback(self.service_response_callback)


    def service_response_callback(self, future):
        try:
            response = future.result()
            self.get_logger().info(
                        'Result of service: for %s  = %s' %                                # CHANGE
                        (self.req.data, response.rta))  # CHANGE
        except Exception as e:
            self.get_logger().info(
                        'Service call failed %r' % (e,))     
               
def map_range(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

def main(args=None):
    rclpy.init()
    gaze_node = Gaze()
    rclpy.spin(gaze_node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()