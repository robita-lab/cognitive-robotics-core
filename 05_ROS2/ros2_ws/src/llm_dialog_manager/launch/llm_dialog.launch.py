"""Production-ish launch: dialog manager alone.

Assumes stt_publisher and com_act_server are already running elsewhere
(e.g. via launch/base.py at the repo root).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    server_url = DeclareLaunchArgument(
        "server_url", default_value="http://localhost:8080",
        description="FastAPI server tier base URL",
    )
    local_url = DeclareLaunchArgument(
        "local_url", default_value="http://localhost:8080",
        description="FastAPI local tier base URL",
    )
    conversation_id = DeclareLaunchArgument(
        "conversation_id", default_value="udito-session-default",
    )

    dialog = Node(
        package="llm_dialog_manager",
        executable="llm_dialog_manager",
        name="llm_dialog_manager",
        output="screen",
        parameters=[{
            "server_url": LaunchConfiguration("server_url"),
            "local_url": LaunchConfiguration("local_url"),
            "conversation_id": LaunchConfiguration("conversation_id"),
        }],
    )

    return LaunchDescription([server_url, local_url, conversation_id, dialog])
