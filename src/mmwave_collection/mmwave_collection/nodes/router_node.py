#!/usr/bin/env python3
"""Router node - SSH to router and collect CSI data in batches"""
from mmwave_collection.utils.router_utils import prepare_collection_script
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
import paramiko
from pathlib import Path
import time
import subprocess
import tempfile
import os
import json


class RouterNode(Node):
    def __init__(self):
        super().__init__('router_node')
        
        # Declare parameters
        self.declare_parameter('router_name', 'rx_router')
        self.declare_parameter('host', '192.168.1.101')
        self.declare_parameter('port', 22)
        self.declare_parameter('username', 'root')
        self.declare_parameter('key_file', '~/.ssh/id_ed25519')
        self.declare_parameter('mac_address', '\\xf4\\x1e\\x57\\x64\\x92\\xae')
        self.declare_parameter('remote_file', '/tmp/csi_measurements.txt')
        self.declare_parameter('remote_script', '/scripts/collect_csi.sh')
        self.declare_parameter('measurements_per_batch', 5)
        self.declare_parameter('batch_interval', 1.0)  # Seconds between batch collections
        self.declare_parameter('connection_timeout', 10)
        self.declare_parameter('discrete_mode', False)  # New: discrete vs continuous
        
        # Get parameters
        self.router_name = self.get_parameter('router_name').value
        self.host = self.get_parameter('host').value
        self.port = self.get_parameter('port').value
        self.username = self.get_parameter('username').value
        key_file = self.get_parameter('key_file').value
        self.key_file = str(Path(key_file).expanduser())
        self.mac_address = self.get_parameter('mac_address').value
        self.remote_file = self.get_parameter('remote_file').value
        self.remote_script = self.get_parameter('remote_script').value
        self.measurements_per_batch = self.get_parameter('measurements_per_batch').value
        self.batch_interval = self.get_parameter('batch_interval').value
        self.connection_timeout = self.get_parameter('connection_timeout').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        
        # Publisher
        topic_name = f'/{self.router_name}/data'
        self.publisher = self.create_publisher(String, topic_name, 10)
        
        # Trigger subscribers for discrete mode and automated collection
        self.trigger_sub = self.create_subscription(
            Empty, '/trigger_collection', self.trigger_callback, 10)
        self.rotation_complete_sub = self.create_subscription(
            Empty, '/rotation_table/rotation_complete', self.rotation_complete_callback, 10)
        
        # SSH client
        self.ssh_client = None
        self.batch_count = 0
        
        # Connect and upload script
        if self.connect_ssh():
            if self.upload_collection_script():
                mode_str = "discrete" if self.discrete_mode else "continuous"
                
                # Start batch collection timer only in continuous mode
                if not self.discrete_mode:
                    self.timer = self.create_timer(self.batch_interval, self.collect_batch)
                    self.get_logger().info(
                        f'{self.router_name} started in {mode_str} mode: {self.measurements_per_batch} measurements '
                        f'every {self.batch_interval}s'
                    )
                else:
                    self.get_logger().info(
                        f'{self.router_name} started in {mode_str} mode: {self.measurements_per_batch} measurements '
                        f'per trigger'
                    )
            else:
                self.get_logger().error('Failed to upload collection script')
        else:
            self.get_logger().error('Failed to connect to router')
    
    def trigger_callback(self, msg):
        """Handle manual collection trigger (discrete mode)"""
        if self.discrete_mode:
            self.get_logger().info('Manual trigger, collecting router data')
            self.collect_batch()
    
    def rotation_complete_callback(self, msg):
        """Handle rotation complete signal (automated collection)"""
        if self.discrete_mode:
            self.get_logger().info('Rotation complete, collecting router data')
            self.collect_batch()
    
    def connect_ssh(self):
        """Connect to router via SSH"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            transport = paramiko.Transport((self.host, self.port))
            transport.connect()
            transport.auth_none(self.username)
            
            self.ssh_client._transport = transport
            self.get_logger().info(f"Connected to {self.host}")
            
            # Test connection
            stdin, stdout, stderr = self.ssh_client.exec_command('uname -a')
            output = stdout.read().decode()
            self.get_logger().info(f"Router info: {output.strip()}")
            
            return True
                
        except Exception as e:
            self.get_logger().error(f'Failed to connect: {e}')
            self.ssh_client = None
            return False
    
    def upload_collection_script(self):
        """Upload the CSI collection script to the router"""
        # Generate script content
        script_content = prepare_collection_script({
            'measurements_per_batch': self.measurements_per_batch,
            'batch_interval': self.batch_interval,
            'connection_timeout': self.connection_timeout,
            'mac_address': self.mac_address,
            'remote_file': self.remote_file,
            'remote_script': self.remote_script,
        })
        try:
            # Write script to temporary local file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as tmp:
                tmp.write(script_content)
                tmp_path = tmp.name
            
            # Use scp with legacy SSH options
            scp_cmd = [
                'scp', '-O',
                '-o', 'HostKeyAlgorithms=+ssh-rsa',
                '-o', 'PubkeyAcceptedKeyTypes=+ssh-rsa',
                '-o', 'StrictHostKeyChecking=no',
                tmp_path,
                f'{self.username}@{self.host}:{self.remote_script}'
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                # Make script executable
                self.ssh_client.exec_command(f'chmod +x {self.remote_script}')
                self.get_logger().info(f"Uploaded collection script to {self.remote_script}")
                return True
            else:
                self.get_logger().error(f"SCP failed: {result.stderr}")
                return False
        
        except Exception as e:
            self.get_logger().error(f"Failed to upload script: {e}")
            return False
    
    def collect_batch(self):
        """Run collection script, SCP data back, and publish"""
        if not self.ssh_client:
            self.get_logger().warn('Not connected, skipping batch')
            return
        
        try:
            # 1. Execute the collection script on the router
            self.get_logger().info(f'Starting batch #{self.batch_count + 1}...')
            stdin, stdout, stderr = self.ssh_client.exec_command(self.remote_script, timeout=30)
            
            # Wait for script to complete
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8')
                self.get_logger().error(f'Collection script failed: {error_output}')
                self.collect_batch()
            
            # 2. SCP the data file back
            local_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            local_file.close()
            local_path = local_file.name
            
            scp_cmd = [
                'scp', '-O',
                '-o', 'HostKeyAlgorithms=+ssh-rsa',
                '-o', 'PubkeyAcceptedKeyTypes=+ssh-rsa',
                '-o', 'StrictHostKeyChecking=no',
                f'{self.username}@{self.host}:{self.remote_file}',
                local_path
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.get_logger().error(f'SCP failed: {result.stderr}')
                os.unlink(local_path)
                return
            
            # 3. Read the data and publish
            with open(local_path, 'r') as f:
                measurements = f.read().strip().split('\n')
            
            # Clean up temp file
            os.unlink(local_path)
            
            # Filter: only keep lines that contain actual measurement data
            # All measurement lines have "Measurement:" in them
            measurements = [m for m in measurements if m and 'Measurement:' in m]
            
            if measurements:
                # Publish as JSON batch
                msg = String()
                msg.data = json.dumps({
                    'batch_id': self.batch_count,
                    'timestamp': time.time(),
                    'measurements': measurements,
                    'count': len(measurements)
                })
                self.publisher.publish(msg)
                
                self.batch_count += 1
                self.get_logger().info(
                    f'Published batch #{self.batch_count}: {len(measurements)} measurements'
                )
            else:
                self.get_logger().warn('No measurements in batch')
                
        except Exception as e:
            self.get_logger().error(f'Error in batch collection: {e}')
    
    def destroy_node(self):
        """Cleanup"""
        if self.ssh_client:
            try:
                self.ssh_client.close()
                if hasattr(self.ssh_client, '_transport') and self.ssh_client._transport:
                    self.ssh_client._transport.close()
            except:
                pass
        
        super().destroy_node()


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
