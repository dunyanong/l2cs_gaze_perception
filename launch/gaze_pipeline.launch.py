import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    share_dir = get_package_share_directory('l2cs_gaze_perception')
    default_model = os.path.join(share_dir, 'models', 'L2CSNet_gaze360.pkl')
    default_params = os.path.join(share_dir, 'config', 'gaze_params.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('camera_id', default_value='0'),
        DeclareLaunchArgument('model_path', default_value=default_model),
        DeclareLaunchArgument('model_arch', default_value='ResNet50'),
        DeclareLaunchArgument('device', default_value='0'),  # also accepts 'cpu'
        DeclareLaunchArgument('params_file', default_value=default_params),

        Node(
            package='l2cs_gaze_perception',
            executable='gaze_node',
            name='gaze_node',
            output='screen',
            parameters=[
                {
                    'camera_id': LaunchConfiguration('camera_id'),
                    'model_path': LaunchConfiguration('model_path'),
                    'model_arch': LaunchConfiguration('model_arch'),
                    'device': LaunchConfiguration('device'),
                },
                LaunchConfiguration('params_file'),
            ],
        ),
    ])
