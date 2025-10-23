#!/usr/bin/env python3
"""Router node - SSH to router and collect data"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Header
import paramiko
from pathlib import Path
import time


class RouterNode(Node):
    def __init__(self):
        super().__init__('router_node')
        
        # Declare parameters
        self.declare_parameter('router_name', 'rx_router')  # Which router config to use
        self.declare_parameter('host', '192.168.1.1')
        self.declare_parameter('port', 22)
        self.declare_parameter('username', 'root')
        self.declare_parameter('key_file', '~/.ssh/id_rsa')
        self.declare_parameter('command', 'cat /proc/net/mmwave_stats')
        self.declare_parameter('remote_file', '/tmp/mmwave_data.csv')
        self.declare_parameter('interval', 60.0)
        self.declare_parameter('timeout', 30.0)
        self.declare_parameter('enable_legacy_ssh', True)  # Enable ssh-rsa algorithm
        
        # Get parameters
        self.router_name = self.get_parameter('router_name').value
        self.host = self.get_parameter('host').value
        self.port = self.get_parameter('port').value
        self.username = self.get_parameter('username').value
        key_file = self.get_parameter('key_file').value
        self.key_file = str(Path(key_file).expanduser())
        self.command = self.get_parameter('command').value
        self.remote_file = self.get_parameter('remote_file').value
        interval = self.get_parameter('interval').value
        self.timeout = self.get_parameter('timeout').value
        self.enable_legacy_ssh = self.get_parameter('enable_legacy_ssh').value
        
        # Publisher - use router name in topic
        topic_name = f'/{self.router_name}/data'
        self.publisher = self.create_publisher(String, topic_name, 10)
        
        # SSH client
        self.ssh_client = None
        self.connect_ssh()
        
        # Timer for periodic collection
        self.timer = self.create_timer(interval, self.collect_data)
        
        self.get_logger().info(f'{self.router_name} node started, collecting every {interval}s from {self.host}')
    
    def connect_ssh(self):
        """Connect to router via SSH with legacy algorithm support"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Configure connection parameters
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'key_filename': self.key_file,
                'timeout': self.timeout,
            }
            
            # Enable legacy SSH algorithms if needed (for -o HostKeyAlgorithms=+ssh-rsa)
            if self.enable_legacy_ssh:
                connect_kwargs['disabled_algorithms'] = {'pubkeys': []}
                # This allows ssh-rsa which is disabled by default in newer OpenSSH
                
            self.ssh_client.connect(**connect_kwargs)
            
            self.get_logger().info(f'Connected to {self.router_name} at {self.host}')
        except Exception as e:
            self.get_logger().error(f'Failed to connect to {self.router_name}: {e}')
            self.ssh_client = None
    
    def collect_data(self):
        """Collect data from router"""
        if self.ssh_client is None:
            self.get_logger().warn(f'{self.router_name}: Not connected, attempting reconnect...')
            self.connect_ssh()
            return
        
        try:
            # Execute command
            stdin, stdout, stderr = self.ssh_client.exec_command(self.command)
            data = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if error:
                self.get_logger().warn(f'{self.router_name} command stderr: {error}')
            
            # Publish data
            msg = String()
            msg.data = data
            self.publisher.publish(msg)
            
            self.get_logger().info(f'{self.router_name}: Collected {len(data)} bytes')
            
        except Exception as e:
            self.get_logger().error(f'{self.router_name}: Error collecting data: {e}')
            self.ssh_client = None  # Will reconnect next time
    
    def destroy_node(self):
        """Cleanup"""
        if self.ssh_client:
            self.ssh_client.close()
        super().destroy_node()

    def setup_rx_script(self):
        """Setup RX script on router"""

    def setup_tx_script(self):
        """Setup TX script on router"""
        
        


def main(args=None):
    rclpy.init(args=args)
    node = RouterNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

