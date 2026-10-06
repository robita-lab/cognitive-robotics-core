"""Arquitectura 3T - UDITO · Lanza las tres capas sobre ROS 2.

ros2 launch udito_ros udito_voice.launch.py [rag:=true] [face:=false] [mic:=false] [wake_word:=udito]
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    root = os.environ.get("ROBITA_ROOT", "/opt/robita-lab")
    rag = LaunchConfiguration("rag")
    face = LaunchConfiguration("face")
    mic = LaunchConfiguration("mic")
    wake = LaunchConfiguration("wake_word")

    return LaunchDescription([
        DeclareLaunchArgument("rag", default_value="false", description="RAG completo (lento de cargar)"),
        DeclareLaunchArgument("face", default_value="true", description="Simulador de rostro en pantalla"),
        DeclareLaunchArgument("mic", default_value="true", description="Nodo STT con micrófono"),
        DeclareLaunchArgument("wake_word", default_value="none", description="Palabra clave, p. ej. udito (none = sin)"),

        # Capa deliberativa
        Node(package="udito_ros", executable="cognitive_node", name="udito_cognitive", output="screen",
             parameters=[{"use_rag": ParameterValue(rag, value_type=bool)}]),
        # Capa ejecutiva (C.C.)
        Node(package="udito_ros", executable="orchestrator_node", name="udito_cc", output="screen"),
        # Capa reactiva: actuadores y sensores
        Node(package="udito_ros", executable="tts_node", name="udito_tts", output="screen"),
        Node(package="udito_ros", executable="stt_node", name="udito_stt", output="screen",
             condition=IfCondition(mic),
             parameters=[{"wake_word": ParameterValue(wake, value_type=str)}]),
        ExecuteProcess(cmd=[os.path.join(root, "scripts", "udito", "face-sim.sh"), "--wakeword"],
                       condition=IfCondition(face), output="screen"),
    ])
