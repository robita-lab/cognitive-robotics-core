import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('robot_base_nav')
    xacro_file = os.path.join(pkg_share, 'description', 'robot.urdf.xacro')

    serial_port = LaunchConfiguration('serial_port')
    wheel_radius = LaunchConfiguration('wheel_radius')
    wheel_separation = LaunchConfiguration('wheel_separation')

    declare_serial_port = DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0')
    declare_wheel_radius = DeclareLaunchArgument('wheel_radius', default_value='0.08')
    declare_wheel_separation = DeclareLaunchArgument('wheel_separation', default_value='0.40')

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': Command(['xacro ', xacro_file]),
            'use_sim_time': False,
        }]
    )

    serial_bridge = Node(
        package='robot_base_nav',
        executable='serial_bridge_node',
        name='serial_bridge_node',
        output='screen',
        parameters=[{
            'serial_port': serial_port,
            'baud_rate': 115200,
            'wheel_radius': wheel_radius,
            'wheel_separation': wheel_separation,
        }]
    )

    # Driver del lidar LDRobot (paquete ldlidar_node, repo Myzhar/ldrobot-lidar-ros2).
    # Usamos la variante "with_mgr" porque incluye el lifecycle_manager de Nav2, que
    # hace automáticamente las transiciones configure -> activate del nodo lifecycle.
    # Sin ella el nodo arranca pero se queda inactivo y nunca publica /ldlidar_node/scan.
    ldlidar_share = get_package_share_directory('ldlidar_node')
    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ldlidar_share, 'launch', 'ldlidar_with_mgr.launch.py')
        )
    )

    return LaunchDescription([
        declare_serial_port,
        declare_wheel_radius,
        declare_wheel_separation,
        robot_state_publisher,
        serial_bridge,
        lidar_launch,
    ])
