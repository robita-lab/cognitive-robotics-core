from body_interfaces.srv import Text2Speech

import rclpy
from rclpy.node import Node
import sys
sys.path.append("/home/udito/OneDrive/UDITO/udito/src/audio")
from TtS import TtS

class TtsService(Node):

    def __init__(self):
        super().__init__('text_to_speech_server')
        self.srv = self.create_service(Text2Speech, 'text_to_speech_server', self.speech_callback)
        self.myTtS = TtS()
        self.myTtS.speak("Hola¿cómo estás?")

    def speech_callback(self, request, response):
        self.get_logger().info('Server received\ntext: %s speaker: %s' % (request.text, request.speaker))
        self.myTtS.speak(request.text)
        response.rta = "ACK"
        return response

def main():
    rclpy.init()

    minimal_service = TtsService()

    rclpy.spin(minimal_service)

    rclpy.shutdown()


if __name__ == '__main__':
    main()
from body_interfaces.srv import Text2Speech

import rclpy
from rclpy.node import Node
import sys
sys.path.append("/home/udito/OneDrive/UDITO/udito/src/audio")
from TtS import TtS

class TtsService(Node):

    def __init__(self):
        super().__init__('text_to_speech_server')
        self.srv = self.create_service(Text2Speech, 'text_to_speech_server', self.speech_callback)
        self.myTtS = TtS()
        self.myTtS.speak("Hola¿cómo estás?")

    def speech_callback(self, request, response):
        self.get_logger().info('Server received\ntext: %s speaker: %s' % (request.text, request.speaker))
        self.myTtS.speak(request.text)
        response.rta = "ACK"
        return response

def main():
    rclpy.init()

    minimal_service = TtsService()

    rclpy.spin(minimal_service)

    rclpy.shutdown()


if __name__ == '__main__':
    main()