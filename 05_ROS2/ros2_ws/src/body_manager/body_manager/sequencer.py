import sys
import rclpy
import time
from rclpy.node import Node
from body_interfaces.srv import HeadMove
from body_interfaces.msg import DOA
from body_interfaces.msg import SequencerMsg   
from body_interfaces.msg import BehaviorMsg 

class Sequencer(Node):
    def __init__(self):
        super().__init__('sequencer_node')
        self.pub = self.create_publisher(SequencerMsg, 'sequencer_topic', 10)
#        self.doa_sub = self.create_subscription(
#            DOA,                                               
#            'doa_topic',
#            self.doa_callback,
#            10)
#        self.doa_sub  # prevent unused variable warning

        self.behavior_sub = self.create_subscription(
            BehaviorMsg,
            'behavior_topic',
            self.behavior_sub_callback,
            10)

        self.states = ["IDLE", "GAZE", "INTRODUCE_MYSELF"]
        self.seq_msg = SequencerMsg()
        self.seq_msg.state = "IDLE"
        self.seq_msg.param = 1
        self.change_to_state("IDLE")

    def doa_callback(self, msg):    
        if self.current_state =="IDLE":
            self.current_state = "INTRODUCE_MYSELF"
        self.seq_msg.state = self.current_state
        self.pub.publish(self.seq_msg)
        self.get_logger().info('publishing.new_state: "%s", param:%d' %(self.seq_msg.state, self.seq_msg.param))  

    def behavior_sub_callback(self, msg):    
        self.get_logger().info('received topic: "%s", param:%s' %(msg.id, msg.state))  
        self.get_logger().info('current active state: %s' %self.current_state)
        if (self.current_state =="INTRODUCE_MYSELF" and
        msg.id == "INTRODUCE_MYSELF" and
        msg.state == "END"):
            self.change_to_state("IDLE")

    def change_to_state(self, new_state):
        self.current_state = new_state
        self.seq_msg.state = self.current_state
        self.seq_msg.param = 1
        self.pub.publish(self.seq_msg)
        self.get_logger().info('publishing.new_state: "%s", param:%d' %(self.seq_msg.state, self.seq_msg.param))  


def main(args=None):
    rclpy.init()
    seq_node = Sequencer()
    for i in range(50):
#        rclpy.spin_once(seq_node)
        time.sleep(0.1)
    seq_node.change_to_state("INTRODUCE_MYSELF")
    rclpy.spin(seq_node)
    seq_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
