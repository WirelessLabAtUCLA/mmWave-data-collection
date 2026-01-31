#!/usr/bin/env python3
"""Router node - SSH to router and collect CSI/FTM data in batches"""
from mmwave_collection.utils.router_utils import prepare_collection_script, prepare_ftm_collection_script
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
        self.declare_parameter('collection_mode', 'csi')  # 'csi', 'ftm', or 'both'
        
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
        self.collection_mode = self.get_parameter('collection_mode').value
        
        # Validate collection mode
        if self.collection_mode not in ['csi', 'ftm', 'both']:
            self.get_logger().error(f"Invalid collection_mode: {self.collection_mode}. Must be 'csi', 'ftm', or 'both'")
            self.collection_mode = 'csi'
        
        # Setup FTM parameters if needed
        if self.collection_mode in ['ftm', 'both']:
            self.remote_ftm_file = '/tmp/ftm_measurements.txt'
            self.remote_ftm_script = '/scripts/collect_ftm.sh'
        
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
        self.ftm_batch_count = 0
        
        # Connect and upload script
        if self.connect_ssh():
            scripts_uploaded = True
            
            # Upload CSI script if needed
            if self.collection_mode in ['csi', 'both']:
                if not self.upload_collection_script('csi'):
                    self.get_logger().error('Failed to upload CSI collection script')
                    scripts_uploaded = False
            
            # Upload FTM script if needed
            if self.collection_mode in ['ftm', 'both']:
                if not self.upload_collection_script('ftm'):
                    self.get_logger().error('Failed to upload FTM collection script')
                    scripts_uploaded = False
            
            if scripts_uploaded:
                mode_str = "discrete" if self.discrete_mode else "continuous"
                collection_str = "CSI+FTM" if self.collection_mode == 'both' else self.collection_mode.upper()
                
                # Start batch collection timer only in continuous mode
                if not self.discrete_mode:
                    self.timer = self.create_timer(self.batch_interval, self.collect_batch)
                    self.get_logger().info(
                        f'{self.router_name} started in {mode_str} mode ({collection_str}): {self.measurements_per_batch} measurements '
                        f'every {self.batch_interval}s'
                    )
                else:
                    self.get_logger().info(
                        f'{self.router_name} started in {mode_str} mode ({collection_str}): {self.measurements_per_batch} measurements '
                        f'per trigger'
                    )
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
    
    def upload_collection_script(self, script_type='csi'):
        """Upload the collection script to the router
        
        Args:
            script_type: 'csi' for CSI collection or 'ftm' for FTM collection
        """
        # Determine script parameters based on type
        if script_type == 'ftm':
            script_content = prepare_ftm_collection_script({
                'measurements_per_batch': self.measurements_per_batch,
                'connection_timeout': self.connection_timeout,
                'mac_address': self.mac_address,
                'remote_file': self.remote_ftm_file,
            })
            remote_script = self.remote_ftm_script
            script_name = "FTM collection script"
        else:  # csi
            script_content = prepare_collection_script({
                'measurements_per_batch': self.measurements_per_batch,
                'batch_interval': self.batch_interval,
                'connection_timeout': self.connection_timeout,
                'mac_address': self.mac_address,
                'remote_file': self.remote_file,
                'remote_script': self.remote_script,
            })
            remote_script = self.remote_script
            script_name = "CSI collection script"
        
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
                f'{self.username}@{self.host}:{remote_script}'
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                # Make script executable
                self.ssh_client.exec_command(f'chmod +x {remote_script}')
                self.get_logger().info(f"Uploaded {script_name} to {remote_script}")
                return True
            else:
                self.get_logger().error(f"SCP failed for {script_name}: {result.stderr}")
                return False
        
        except Exception as e:
            self.get_logger().error(f"Failed to upload {script_name}: {e}")
            return False
    
    def collect_batch(self):
        """Run collection script(s), SCP data back, and publish"""
        if not self.ssh_client:
            self.get_logger().warn('Not connected, skipping batch')
            return
        
        # Collect CSI if enabled
        if self.collection_mode in ['csi', 'both']:
            self._collect_data('csi')
        
        # Collect FTM if enabled
        if self.collection_mode in ['ftm', 'both']:
            self._collect_data('ftm')
    
    def _collect_data(self, data_type='csi'):
        """Collect data of specified type (csi or ftm)
        
        Args:
            data_type: 'csi' for CSI/AoA data or 'ftm' for ToF data
        """
        if not self.ssh_client:
            return
        
        # Determine parameters based on data type
        if data_type == 'ftm':
            script = self.remote_ftm_script
            remote_file = self.remote_ftm_file
            batch_id = self.ftm_batch_count
            data_label = "FTM"
        else:  # csi
            script = self.remote_script
            remote_file = self.remote_file
            batch_id = self.batch_count
            data_label = "CSI"
        
        try:
            # 1. Execute the collection script on the router
            self.get_logger().info(f'Starting {data_label} batch #{batch_id + 1}...')
            stdin, stdout, stderr = self.ssh_client.exec_command(script, timeout=60)
            
            # Wait for script to complete
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8')
                self.get_logger().error(f'{data_label} collection script failed: {error_output}')
                return
            
            # 2. SCP the data file back
            local_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            local_file.close()
            local_path = local_file.name
            
            scp_cmd = [
                'scp', '-O',
                '-o', 'HostKeyAlgorithms=+ssh-rsa',
                '-o', 'PubkeyAcceptedKeyTypes=+ssh-rsa',
                '-o', 'StrictHostKeyChecking=no',
                f'{self.username}@{self.host}:{remote_file}',
                local_path
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.get_logger().error(f'{data_label} SCP failed: {result.stderr}')
                os.unlink(local_path)
                return
            
            # 3. Read the data and publish
            with open(local_path, 'r') as f:
                measurements = f.read().strip().split('\n')
            
            # Clean up temp file
            os.unlink(local_path)
            
            # Filter: only keep lines that contain actual measurement data
            measurements = [m for m in measurements if m and 'Measurement:' in m]
            
            if measurements:
                # Publish as JSON batch
                msg = String()
                msg.data = json.dumps({
                    'data_type': data_type,
                    'batch_id': batch_id,
                    'timestamp': time.time(),
                    'measurements': measurements,
                    'count': len(measurements)
                })
                self.publisher.publish(msg)
                
                # Increment appropriate counter
                if data_type == 'ftm':
                    self.ftm_batch_count += 1
                else:
                    self.batch_count += 1
                
                self.get_logger().info(
                    f'Published {data_label} batch #{batch_id + 1}: {len(measurements)} measurements'
                )
            else:
                self.get_logger().warn(f'No {data_label} measurements in batch')
                
        except Exception as e:
            self.get_logger().error(f'Error in {data_label} batch collection: {e}')
    
    def destroy_node(self):
        """Cleanup"""
        if self.ssh_client:
            try:
                self.ssh_client.close()
                if hasattr(self.ssh_client, '_transport') and self.ssh_client._transport:
                    self.ssh_client._transport.close()
            except Exception:
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
