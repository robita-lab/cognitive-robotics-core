"""ros2 launch robita_cognitive cognitive.launch.py [rag_backend:=normativa|legacy|none] [repo_root:=/ruta/al/repo]"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    cfg = os.path.join(get_package_share_directory("robita_cognitive"), "config", "cognitive.yaml")
    use_rag = LaunchConfiguration("use_rag")
    rag_backend = LaunchConfiguration("rag_backend")
    repo_root = LaunchConfiguration("repo_root")
    return LaunchDescription([
        DeclareLaunchArgument("use_rag", default_value="true"),
        DeclareLaunchArgument("rag_backend", default_value="normativa"),
        DeclareLaunchArgument("repo_root", default_value=os.getenv("ROBITA_REPO_ROOT", "")),
        Node(
            package="robita_cognitive",
            executable="cognitive_node",
            name="robita_cognitive",
            output="screen",
            parameters=[
                cfg,
                {
                    "use_rag": ParameterValue(use_rag, value_type=bool),
                    "rag_backend": ParameterValue(rag_backend, value_type=str),
                    "repo_root": ParameterValue(repo_root, value_type=str),
                },
            ],
        ),
    ])
