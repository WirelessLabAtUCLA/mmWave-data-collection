"""Launch all data collection nodes"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os


def generate_launch_description():
    # Get config file path
    config_file = LaunchConfiguration('config', default='config/default_config.yaml')
    
    # Declare launch argument for discrete mode
    discrete_mode_arg = DeclareLaunchArgument(
        'discrete_mode',
        default_value='false',
        description='Enable discrete data collection mode (trigger-based)'
    )
    
    discrete_mode = LaunchConfiguration('discrete_mode')
    
    return LaunchDescription([
        discrete_mode_arg,
        
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
                'remote_file': '/tmp/csi_measurements.txt',
                'remote_script': '/scripts/collect_csi.sh',
                'measurements_per_batch': 5,
                'batch_interval': 1.0,
                'connection_timeout': 10,
                'discrete_mode': discrete_mode,
            }]
        ),
        
        # GPS node
        Node(
            package='mmwave_collection',
            executable='gps_node',
            name='gps_node',
            output='screen',
            parameters=[{
                'device': 'auto',
                'baudrate': 9600,
                'auto_detect': True,
                'discrete_mode': discrete_mode,
            }]
        ),
        
        # Camera node
        Node(
            package='mmwave_collection',
            executable='camera_node',
            name='camera_node',
            output='screen',
            parameters=[{
                'device_id': 0,
                'width': 1920,
                'height': 1080,
                'jpeg_quality': 85,
                'discrete_mode': discrete_mode,
            }]
        ),
        
        # Sync node
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
                'gps_required': False,  # GPS is optional
            }]
        ),
    ])

