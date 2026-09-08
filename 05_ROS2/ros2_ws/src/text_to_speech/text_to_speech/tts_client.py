import sys

from body_interfaces.srv import Text2Speech
import rclpy
from rclpy.node import Node

class MinimalClientAsync(Node):
    def __init__(self):
        super().__init__('minimal_client_async')
        self.cli = self.create_client(Text2Speech, 'text_to_speech_server')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.req = Text2Speech.Request()

    def send_request(self, text, speaker):
        self.req.text = text
        self.req.speaker = speaker
        future = self.cli.call_async(self.req)
        future.add_done_callback(self.service_response_callback)
    
    def service_response_callback(self, future):
        try:
            response = future.result()
            self.get_logger().info('Respuesta del servicio:%s' %response.rta)
        except Exception as e:
            self.get_logger().error(f'Error al llamar al servicio: {e}')

    def test(self):
        self.send_request("Hola mundo", "UDITO")
        self.send_request("Esto es una frase de prueba", "UDITO")
        self.send_request("Y esto, es una frase mucho más larga, que debería tener una espera de unos cuantos segundos", "UDITO")
        self.send_request("Adiós mundo cruel", "UDITO")

def main():
    rclpy.init()

    minimal_client = MinimalClientAsync()
    minimal_client.test()
    rclpy.spin(minimal_client)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
import sys

from body_interfaces.srv import Text2Speech
import rclpy
from rclpy.node import Node

class MinimalClientAsync(Node):
    def __init__(self):
        super().__init__('minimal_client_async')
        self.cli = self.create_client(Text2Speech, 'text_to_speech_server')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.req = Text2Speech.Request()

    def send_request(self, text, speaker):
        self.req.text = text
        self.req.speaker = speaker
        future = self.cli.call_async(self.req)
        future.add_done_callback(self.service_response_callback)
    
    def service_response_callback(self, future):
        try:
            response = future.result()
            self.get_logger().info('Respuesta del servicio:%s' %response.rta)
        except Exception as e:
            self.get_logger().error(f'Error al llamar al servicio: {e}')

    def test(self):
        self.send_request("Hola mundo", "UDITO")
        self.send_request("Esto es una frase de prueba", "UDITO")
        self.send_request("Y esto, es una frase mucho más larga, que debería tener una espera de unos cuantos segundos", "UDITO")
        self.send_request("Adiós mundo cruel", "UDITO")

def main():
    rclpy.init()

    minimal_client = MinimalClientAsync()
    minimal_client.test()
    rclpy.spin(minimal_client)
    rclpy.shutdown()


if __name__ == '__main__':
    main()