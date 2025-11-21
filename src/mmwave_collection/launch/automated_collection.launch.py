"""Launch automated data collection with rotation table"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os


def generate_launch_description():
    # Declare launch arguments
    angle_start_arg = DeclareLaunchArgument(
        'angle_start',
        default_value='-60',
        description='Starting angle in degrees'
    )
    
    angle_end_arg = DeclareLaunchArgument(
        'angle_end',
        default_value='60',
        description='Ending angle in degrees'
    )
    
    angle_step_arg = DeclareLaunchArgument(
        'angle_step',
        default_value='1',
        description='Angle step size in degrees'
    )
    
    stabilization_time_arg = DeclareLaunchArgument(
        'stabilization_time',
        default_value='10.0',
        description='Time to wait after rotation for stabilization (seconds)'
    )
    
    # Get configurations
    angle_start = LaunchConfiguration('angle_start')
    angle_end = LaunchConfiguration('angle_end')
    angle_step = LaunchConfiguration('angle_step')
    stabilization_time = LaunchConfiguration('stabilization_time')
    
    return LaunchDescription([
        angle_start_arg,
        angle_end_arg,
        angle_step_arg,
        stabilization_time_arg,
        
        # Rotation table node
        Node(
            package='mmwave_collection',
            executable='rotation_table_node',
            name='rotation_table_node',
            output='screen',
            parameters=[{
                'rotation_table_device': '/dev/ttyACM0',
                'rotation_table_baudrate': 115200,
                'timeout': 0.1,
                'discrete_mode': True,  # Use discrete mode for automated collection
                'stabilization_time': stabilization_time,  # Pass stabilization time
            }]
        ),
        
        # RX Router node in discrete mode
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
                'measurements_per_batch': 100,
                'batch_interval': 1.0,
                'connection_timeout': 10,
                'discrete_mode': True,  # Discrete mode - wait for triggers
            }]
        ),
        
        # Camera node in discrete mode
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
                'fps': 30,
                'discrete_mode': True,
            }]
        ),
        
        # GPS node in discrete mode
        Node(
            package='mmwave_collection',
            executable='gps_node',
            name='gps_node',
            output='screen',
            parameters=[{
                'device': '/dev/ttyACM1',
                'baudrate': 9600,
                'auto_detect': False,
                'discrete_mode': True,
            }]
        ),
        
        # Sync node in discrete mode
        Node(
            package='mmwave_collection',
            executable='sync_node',
            name='sync_node',
            output='screen',
            parameters=[{
                'data_path': './data',
                'time_tolerance': 2.0,
                'organize_by_date': True,
                'discrete_mode': True,
                'gps_required': False,
            }]
        ),
        
        # Automated collection coordinator
        Node(
            package='mmwave_collection',
            executable='automated_collection_node',
            name='automated_collection_node',
            output='screen',
            parameters=[{
                'angle_start': angle_start,
                'angle_end': angle_end,
                'angle_step': angle_step,
                'auto_start': True,
            }]
        ),
    ])

