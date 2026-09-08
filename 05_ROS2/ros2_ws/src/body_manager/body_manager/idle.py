import sys
import rclpy
import time
from random import randint
from rclpy.node import Node
from body_interfaces.srv import ComActMsg
from body_interfaces.srv import HeadMove
from body_interfaces.msg import DOA
from body_interfaces.srv import Behavior
from body_interfaces.msg import SequencerMsg

class Idle(Node):
    def __init__(self):
        super().__init__('idle')
        self.cli_com_act = self.create_client(ComActMsg, 'com_act_server')

        while not self.cli_com_act.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('multimodal_expression_server not available, waiting again...')

        self.com_act_req = ComActMsg.Request()

        self.sequencer_subscription = self.create_subscription(
            SequencerMsg,
            'sequencer_topic',
            self.sequencer_callback,
            10) 
        self.speaking = False
        self.active = False

    def sequencer_callback(self, msg):
        self.get_logger().info('Sequencer publishes\nstate: %s \nparam:%d' %(msg.state,msg.param))
        if msg.state == "IDLE":
            self.active = True
            self.do_idle()
        else:
            if self.active:
                self.active = False
                self.get_logger().info('Stopping idle')

# TODO: Revisar porque no funciona
    def do_idle(self):
        while rclpy.ok():
            p = randint(-30,30)
            t1 = randint(-5,5)
            t2 = randint(-5,5)
            tau = randint(10,60)
            d = randint(100, 2000)
            self.send_com_act("me aburro","R_TILT", t1)
            self.send_com_act("guapi","L_TILT", t2)
            self.send_com_act("a","PAN", p)
            self.send_com_act("op","BLINK", tau)
            time.sleep(d/1000)
            rclpy.spin_once(self)
            if not self.active:
                self.send_com_act("Ejem","NEUTRAL", 10)
                self.req.end = True
                self.cli_seq.call_async(self.req)
                break

    def send_com_act(self, text, gesture, data):
        while self.speaking:
            rclpy.spin_once(self)
            time.sleep(0.1)
        self.com_act_req.text = text
        self.com_act_req.gesture = gesture
        self.com_act_req.data = data
        self.speaking = True
        future = self.cli_com_act.call_async(self.com_act_req)
        future.add_done_callback(self.com_act_service_callback) 

    def com_act_service_callback( self, future ):
        try:
            response = future.result()
            self.get_logger().info(
                        'Result of ComAct service: for %s  = %s' %                                
                        (self.com_act_req.text, response.rta)) 
            if response.rta == "ACK":
                self.speaking = False
        except Exception as e:
            self.get_logger().info(
                        'Service call failed %r' % (e,))    
               
def map_range(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

def main(args=None):
    rclpy.init()
    idle_node = Idle()
    rclpy.spin(idle_node)
    idle_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()



