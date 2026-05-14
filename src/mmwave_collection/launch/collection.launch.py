"""Launch all data collection nodes (mmWave + RealSense D455)."""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    discrete_mode_arg = DeclareLaunchArgument(
        'discrete_mode',
        default_value='false',
        description='Enable discrete data collection mode (trigger-based)')

    collection_mode_arg = DeclareLaunchArgument(
        'collection_mode',
        default_value='csi',
        description='Collection mode: csi (AoA only), ftm (ToF only), or both (AoA+ToF)')

    discrete_mode = LaunchConfiguration('discrete_mode')
    collection_mode = LaunchConfiguration('collection_mode')

    return LaunchDescription([
        discrete_mode_arg,
        collection_mode_arg,

        # RX Router node
        Node(
            package='mmwave_collection',
            executable='router_node',
            name='rx_router_node',
            output='screen',
            parameters=[{
                'router_name': 'rx_router',
                'host': '192.168.1.101',
                'port': 22,
                'username': 'root',
                'key_file': '~/.ssh/id_ed25519',
                'mac_address': '\\xf4\\x1e\\x57\\x64\\x92\\xae',
                'mac_addresses': ['\\xf4\\x1e\\x57\\x64\\x92\\xae', '\\xf4\\x1e\\x57\\xa4\\x86\\x5f'],
                'remote_file': '/tmp/csi_measurements.txt',
                'remote_script': '/scripts/collect_csi.sh',
                'measurements_per_batch': 250,
                'batch_interval': 1.0,
                'connection_timeout': 10,
                'discrete_mode': discrete_mode,
                'collection_mode': collection_mode,
            }]
        ),

        # RealSense D455 node — color + depth + IMU for RTAB-Map
        Node(
            package='mmwave_collection',
            executable='realsense_node',
            name='realsense_node',
            output='screen',
            parameters=[{
                'color_width': 848,
                'color_height': 480,
                'color_fps': 30,
                'depth_width': 848,
                'depth_height': 480,
                'depth_fps': 30,
                'enable_imu': True,
                'jpeg_quality': 85,
                'discrete_mode': discrete_mode,
            }]
        ),

        # Sync node — aligns mmWave batches with images and SLAM pose
        Node(
            package='mmwave_collection',
            executable='sync_node',
            name='sync_node',
            output='screen',
            parameters=[{
                'data_path': './data',
                'time_tolerance': 0.5,
                'organize_by_date': True,
                'discrete_mode': discrete_mode,
                'pose_required': False,  # SLAM pose is optional; node works without RTAB-Map
            }]
        ),
    ])
