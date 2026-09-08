# DOA publishes Direction Of Audio source, and Voice Activity Detection (VAD) is a key part of the process.
# This code is a ROS2 node that publishes DOA and VAD data.

import usb.core
import usb.util
import time
import sys

import json
import io
import threading
import numpy as np
import queue
import pyaudio
import wave
import webrtcvad
import whisper
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from body_interfaces.msg import DOA
from body_interfaces.msg import Speech2Text

sys.path.append("/home/udito/OneDrive/UDITO/udito/src")
from audio.StT import StT

class StTPublisher(Node):

    def __init__(self):
        super().__init__('stt_publisher')
        self.doa_pub = self.create_publisher(DOA, 'doa_topic', 10)
        self.stt_pub = self.create_publisher(Speech2Text, 'stt_topic', 10)
        timer_period = 0.01  # seconds
        self.timer = self.create_timer(timer_period, self.tick)
        self.stt = StT()
        self.doa_msg = DOA()
        self.stt_msg = Speech2Text()
        if self.stt.respeaker:
            self.stt.respeaker.set_vad_threshold( 10 )
            self.get_logger().info('Mic found')

    def tick(self):
        #while True:
            result = self.stt.tick()
            if self.stt.user_speaking:
                self.doa_msg.angle = self.stt.respeaker.direction
                self.doa_msg.vad = 1
                self.doa_pub.publish(self.doa_msg)
                self.get_logger().info('publishing.angle: "%d", vad:%d' %(self.doa_msg.angle, self.doa_msg.vad))  

            if result:
                self.stt_msg.text = result['results'][0]['alternatives'][0]['transcript'].strip()
                self.stt_msg.confidence = result['results'][0]['alternatives'][0]['confidence']
                self.stt_pub.publish(self.stt_msg)
                self.get_logger().info('publishing text:%s,  conf:%f' %(self.stt_msg.text, self.stt_msg.confidence))

    def close(self):
        self.stt.close()

def main(args=None):
    rclpy.init(args=args)

    stt_pub = StTPublisher()
    rclpy.spin(stt_pub)

    stt_pub.close()
    stt_pub.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()