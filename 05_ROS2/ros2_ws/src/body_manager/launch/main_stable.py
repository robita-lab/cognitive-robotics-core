#
# ros2 launch turtlesim_mimic_launch.py
#
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='body_manager',
            executable='introduce_myself_behavior',
            name='introduce_myself'
        ),
        Node(
            package='body_manager',
            executable='idle_behavior',
            name='idle'
        ),
#        Node(
#            package='body_manager',
#            executable='gaze_behavior',
#            name='gaze'
#        ),
        Node(
            package='body_manager',
            executable='sequencer',
            name='sequencer'
        ),
    ])
