"""Launch all data collection nodes"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os


def generate_launch_description():
    # Get config file path
    config_file = LaunchConfiguration('config', default='config/default_config.yaml')
    
    return LaunchDescription([
        # RX Router node
        Node(
            package='mmwave_collection',
            executable='router_node',
            name='rx_router_node',
            output='screen',
            parameters=[{
                'router_name': 'rx_router',
                'host': '192.168.1.1',
                'port': 22,
                'username': 'root',
                'key_file': '~/.ssh/id_rsa',
                'command': 'cat /proc/net/mmwave_stats',
                'remote_file': '/tmp/mmwave_data.csv',
                'interval': 60.0,
                'timeout': 30.0,
                'enable_legacy_ssh': True,
            }]
        ),
        
        # TX Router node
        Node(
            package='mmwave_collection',
            executable='router_node',
            name='tx_router_node',
            output='screen',
            parameters=[{
                'router_name': 'tx_router',
                'host': '192.168.100.1',
                'port': 22,
                'username': 'root',
                'key_file': '~/.ssh/id_rsa',
                'command': 'hostapd -B /etc/hostapd.conf',
                'remote_file': '',
                'interval': 60.0,
                'timeout': 30.0,
                'enable_legacy_ssh': True,
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
            }]
        ),
    ])

