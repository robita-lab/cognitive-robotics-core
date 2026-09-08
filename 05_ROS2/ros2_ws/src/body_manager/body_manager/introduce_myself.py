import time
import sys
import rclpy
from rclpy.node import Node
from body_interfaces.srv import ComActMsg
from body_interfaces.msg import DOA
from body_interfaces.msg import SequencerMsg
from body_interfaces.msg import BehaviorMsg

class IntroduceMyself(Node):
    text = ["Hola! Soy el robot de la universidad de diseño innovación y tecnología",
        "Mi nombre es UDITO",
        "¿Te gustaría estudiar algo relacionado con el diseño?",
        "Pronto podré ayudarte en ello!"]
    gesture = ["HAPPY", "NEUTRAL","BLINK","BLINK"]
    data = [5, 5, 5, 10]
    ID="INTRODUCE_MYSELF"

    def __init__(self):
        super().__init__('introduce_myself')
        self.pub = self.create_publisher(BehaviorMsg, 'behavior_topic', 10)
        self.cli_com_act = self.create_client(ComActMsg, 'com_act_server')

        while not self.cli_com_act.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('multimodal_expression_server not available, waiting again...')

        self.com_act_req = ComActMsg.Request()
        self.behavior_msg = BehaviorMsg()

        self.sequencer_subscription = self.create_subscription(
            SequencerMsg,
            'sequencer_topic',
            self.sequencer_callback,
            10) 
        self.speaking = False
        self.num_com_acts_finished = 0

    def sequencer_callback(self, msg):
        self.get_logger().info('Sequencer publishes\nstate: %s \nparam:%d' %(msg.state,msg.param))
        if msg.state == self.ID:
            self.introduce_myself()

    def introduce_myself( self ):
        for i in range(len(self.text)):
            self.send_com_act(self.text[i], self.gesture[i], self.data[i])

    def send_behavior_end(self):
        self.behavior_msg.id=self.ID
        self.behavior_msg.state="END"
        self.pub.publish(self.behavior_msg)
        self.get_logger().info(
            'Sending Behvior msg ID: %s, state:%s' %(self.behavior_msg.id, self.behavior_msg.state)
        )

    def send_com_act(self, text, gesture, data):
        self.com_act_req.text = text
        self.com_act_req.gesture = gesture
        self.com_act_req.data = data
        self.speaking = True
        self.get_logger().info(
            'Sending to com_act_server: for %s' %self.com_act_req.text) 
        future = self.cli_com_act.call_async(self.com_act_req)
        future.add_done_callback(self.com_act_service_callback) 

    def com_act_service_callback( self, future ):
        try:
            response = future.result()
            self.get_logger().info(
                        'Result of ComAct service: %s' %response.rta) 
            self.num_com_acts_finished += 1
            if self.num_com_acts_finished == len(self.text):
                self.send_behavior_end()
        except Exception as e:
            self.get_logger().info(
                        'Service call failed %r' % (e,))    

def main(args=None):
    rclpy.init(args=args)

    intro_myself = IntroduceMyself()
    intro_myself.introduce_myself()

    rclpy.spin(intro_myself)

    rclpy.shutdown()

if __name__ == '__main__':
    main()
