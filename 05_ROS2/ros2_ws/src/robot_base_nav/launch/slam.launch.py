import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('robot_base_nav')
    slam_toolbox_share = get_package_share_directory('slam_toolbox')

    params_file = LaunchConfiguration('slam_params_file')

    declare_params = DeclareLaunchArgument(
        'slam_params_file',
        default_value=os.path.join(pkg_share, 'config', 'mapper_params_online_async.yaml')
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_toolbox_share, 'launch', 'online_async_launch.py')
        ),
        launch_arguments={'slam_params_file': params_file, 'use_sim_time': 'false'}.items()
    )

    return LaunchDescription([
        declare_params,
        slam_launch,
    ])
