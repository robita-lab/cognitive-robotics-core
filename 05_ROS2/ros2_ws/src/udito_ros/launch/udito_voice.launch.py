"""Arquitectura 3T - UDITO · Lanza las capas sobre ROS 2 + consola del operador.

ros2 launch udito_ros udito_voice.launch.py [stt_mode:=vad] [whisper:=tiny|base|small] [mic:=false] [console:=false]
        [body_example:=false] [cognitive:=true] [rag:=true] [face:=true]
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
    arg = LaunchConfiguration

    return LaunchDescription([
        DeclareLaunchArgument("console", default_value="true", description="Consola del operador (cara, botones, log)"),
        DeclareLaunchArgument("mic", default_value="true", description="Nodo STT con micrófono"),
        DeclareLaunchArgument("stt_mode", default_value="ptt", description="ptt = mantén para hablar · vad = escucha continua"),
        DeclareLaunchArgument("whisper", default_value="base", description="tiny · base · small"),
        DeclareLaunchArgument("body_example", default_value="true", description="Nodo de ejemplo del cuerpo"),
        DeclareLaunchArgument("cognitive", default_value="false", description="Capa deliberativa (desactivada en esta etapa)"),
        DeclareLaunchArgument("rag", default_value="false", description="RAG completo dentro de Cognitive"),
        DeclareLaunchArgument("face", default_value="false", description="Cara en ventana aparte (pantalla física)"),

        # Capa ejecutiva (C.C.)
        Node(package="udito_ros", executable="orchestrator_node", name="udito_cc", output="screen",
             parameters=[{"use_cognitive": ParameterValue(arg("cognitive"), value_type=bool)}]),
        # Capa reactiva: actuadores y sensores
        Node(package="udito_ros", executable="tts_node", name="udito_tts", output="screen"),
        Node(package="udito_ros", executable="stt_node", name="udito_stt", output="screen",
             condition=IfCondition(arg("mic")),
             parameters=[{"mode": ParameterValue(arg("stt_mode"), value_type=str),
                          "model": ParameterValue(arg("whisper"), value_type=str)}]),
        # Ejemplo para el orquestador del cuerpo
        Node(package="udito_ros", executable="body_example_node", name="udito_body_example", output="screen",
             condition=IfCondition(arg("body_example"))),
        # Capa deliberativa (opcional)
        Node(package="udito_ros", executable="cognitive_node", name="udito_cognitive", output="screen",
             condition=IfCondition(arg("cognitive")),
             parameters=[{"use_rag": ParameterValue(arg("rag"), value_type=bool)}]),
        # Operador
        Node(package="udito_ros", executable="console_node", name="udito_console", output="screen",
             condition=IfCondition(arg("console"))),
        ExecuteProcess(cmd=[os.path.join(root, "scripts", "udito", "face-sim.sh"), "--wakeword"],
                       condition=IfCondition(arg("face")), output="screen"),
    ])
