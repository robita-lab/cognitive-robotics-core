#
# ros2 launch 
#
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='multimodal_expression',
            executable='com_act_server',
            name='com_act_server'
        ),
        Node(
            package='speech_to_text',
            executable='stt_publisher',
            name='stt_publisher'
        ),
    ])