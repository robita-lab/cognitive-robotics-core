import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('robot_base_nav')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    params_file = LaunchConfiguration('params_file')
    map_yaml = LaunchConfiguration('map')

    declare_params = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(pkg_share, 'config', 'nav2_params.yaml')
    )
    declare_map = DeclareLaunchArgument(
        'map',
        default_value=''  # vacío = navegación con SLAM en vivo; o ruta a un .yaml de mapa guardado
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'params_file': params_file,
            'map': map_yaml,
            'use_sim_time': 'false',
        }.items()
    )

    return LaunchDescription([
        declare_params,
        declare_map,
        nav2_launch,
    ])
