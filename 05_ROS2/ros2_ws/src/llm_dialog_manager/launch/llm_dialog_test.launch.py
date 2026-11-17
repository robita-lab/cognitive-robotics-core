"""Robot-free ROS integration launch.

Starts:
  - mock_com_act_server  (stub ComAct, logs everything)
  - llm_dialog_manager   (real node, talks to a FastAPI server)

No microphone, no head hardware required. Drive it by publishing
Speech2Text messages manually, e.g.:

    ros2 topic pub --once /stt_topic body_interfaces/msg/Speech2Text \\
        '{text: "hola", confidence: 0.9}'
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    server_url = DeclareLaunchArgument(
        "server_url", default_value="http://localhost:8080",
        description="FastAPI server tier base URL (running on host or LAN workstation)",
    )
    local_url = DeclareLaunchArgument(
        "local_url", default_value="http://localhost:8080",
        description="FastAPI local tier base URL (running on the robot; same as server_url for tests)",
    )

    mock = Node(
        package="llm_dialog_manager",
        executable="mock_com_act_server",
        name="mock_com_act_server",
        output="screen",
    )

    dialog = Node(
        package="llm_dialog_manager",
        executable="llm_dialog_manager",
        name="llm_dialog_manager",
        output="screen",
        parameters=[{
            "server_url": LaunchConfiguration("server_url"),
            "local_url": LaunchConfiguration("local_url"),
            "conversation_id": "test-session",
        }],
    )

    return LaunchDescription([server_url, local_url, mock, dialog])
