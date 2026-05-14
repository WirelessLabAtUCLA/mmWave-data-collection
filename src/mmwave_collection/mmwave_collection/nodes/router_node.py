#!/usr/bin/env python3
"""Router node - SSH to router and collect CSI/FTM data in batches"""
from mmwave_collection.utils.router_utils import prepare_collection_script, prepare_ftm_collection_script
from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String, Empty
import paramiko
from pathlib import Path
import time
import subprocess
import tempfile
import os
import json
from typing import Any, Dict, List

_DEFAULT_MAC = '\\xf4\\x1e\\x57\\x64\\x92\\xae'


class RouterNode(Node):
    def __init__(self):
        super().__init__('router_node')
        
        # Declare parameters
        self.declare_parameter('router_name', 'rx_router')
        self.declare_parameter('host', '192.168.1.101')
        self.declare_parameter('port', 22)
        self.declare_parameter('username', 'root')
        self.declare_parameter('key_file', '~/.ssh/id_ed25519')
        self.declare_parameter('mac_address', _DEFAULT_MAC)
        # Non-empty list overrides mac_address; each MAC gets measurements_per_batch samples per batch.
        # Tuple (name, Parameter.Type, descriptor): bare [] in declare_parameter infers as BYTE_ARRAY.
        self.declare_parameters(
            '',
            [
                ('mac_addresses', Parameter.Type.STRING_ARRAY, ParameterDescriptor()),
            ],
        )
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
        mac_addresses_param = self.get_parameter('mac_addresses').value
        mac_single = self.get_parameter('mac_address').value
        if mac_addresses_param:
            self.mac_addresses = [str(m).strip() for m in mac_addresses_param if str(m).strip()]
        elif mac_single and str(mac_single).strip():
            self.mac_addresses = [str(mac_single).strip()]
        else:
            self.get_logger().warn(
                'mac_addresses empty and mac_address unset; using default MAC'
            )
            self.mac_addresses = [_DEFAULT_MAC]
        self.remote_file = self.get_parameter('remote_file').value
        self.remote_script = self.get_parameter('remote_script').value
        self.measurements_per_batch = self.get_parameter('measurements_per_batch').value
        self.get_logger().info(
            f'Collecting from {len(self.mac_addresses)} TX MAC(s) '
            f'({self.measurements_per_batch} samples per MAC per batch)'
        )
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
        
        # Connect (CSI/FTM scripts are uploaded per MAC, per batch, in Python)
        if self.connect_ssh():
            mode_str = "discrete" if self.discrete_mode else "continuous"
            collection_str = "CSI+FTM" if self.collection_mode == 'both' else self.collection_mode.upper()
            if not self.discrete_mode:
                self.timer = self.create_timer(self.batch_interval, self.collect_batch)
                self.get_logger().info(
                    f'{self.router_name} started in {mode_str} mode ({collection_str}): '
                    f'{len(self.mac_addresses)} MAC(s) × {self.measurements_per_batch} measurements '
                    f'every {self.batch_interval}s'
                )
            else:
                self.get_logger().info(
                    f'{self.router_name} started in {mode_str} mode ({collection_str}): '
                    f'{len(self.mac_addresses)} MAC(s) × {self.measurements_per_batch} measurements per trigger'
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
    
    def upload_collection_script(self, script_type: str, mac_address: str) -> bool:
        """Upload a single-MAC collection script to the router (one TX per script).

        Args:
            script_type: 'csi' or 'ftm'
            mac_address: Target MAC for this script (same echo -e form as mac_address param)
        """
        if script_type == 'ftm':
            script_content = prepare_ftm_collection_script({
                'measurements_per_batch': self.measurements_per_batch,
                'connection_timeout': self.connection_timeout,
                'mac_address': mac_address,
                'remote_file': self.remote_ftm_file,
            })
            remote_script = self.remote_ftm_script
            script_name = 'FTM collection script'
        else:
            script_content = prepare_collection_script({
                'measurements_per_batch': self.measurements_per_batch,
                'batch_interval': self.batch_interval,
                'connection_timeout': self.connection_timeout,
                'mac_address': mac_address,
                'remote_file': self.remote_file,
                'remote_script': self.remote_script,
            })
            remote_script = self.remote_script
            script_name = 'CSI collection script'
        
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
                self.get_logger().debug(f'Uploaded {script_name} for MAC to {remote_script}')
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
    
    @staticmethod
    def _filter_router_measurement_lines(raw: str) -> List[str]:
        """Keep CSI/FTM dmesg lines; return [] when the router wrote Unreachable (no link)."""
        body = raw.strip()
        if not body:
            return []
        if 'Measurement:' not in body and 'Unreachable' in body:
            return []
        return [m for m in raw.split('\n') if m.strip() and 'Measurement:' in m]

    def _collect_data(self, data_type='csi'):
        """For each MAC: upload single-MAC script, run it once, SCP results; then publish one batch."""
        if not self.ssh_client:
            return

        if data_type == 'ftm':
            script = self.remote_ftm_script
            remote_file = self.remote_ftm_file
            batch_id = self.ftm_batch_count
            data_label = 'FTM'
        else:
            script = self.remote_script
            remote_file = self.remote_file
            batch_id = self.batch_count
            data_label = 'CSI'

        # Enough time for wlan bring-up + N measurements, repeated per MAC
        per_run = max(90, 20 + self.measurements_per_batch * 3)
        exec_timeout = max(120, per_run * len(self.mac_addresses))

        measurements_by_mac: List[Dict[str, Any]] = []
        flat_valid: List[str] = []

        self.get_logger().info(
            f'Starting {data_label} batch #{batch_id + 1} ({len(self.mac_addresses)} MAC run(s))...'
        )

        try:
            for mac in self.mac_addresses:
                if not self.upload_collection_script(data_type, mac):
                    self.get_logger().error(
                        f'{data_label}: failed to upload script for MAC {mac!r}'
                    )
                    measurements_by_mac.append({'mac_address': mac, 'data': []})
                    continue

                stdin, stdout, stderr = self.ssh_client.exec_command(
                    script, timeout=exec_timeout
                )
                exit_status = stdout.channel.recv_exit_status()

                if exit_status != 0:
                    err = stderr.read().decode('utf-8', errors='replace')
                    self.get_logger().error(
                        f'{data_label} script failed for MAC {mac!r} (exit {exit_status}): {err}'
                    )
                    measurements_by_mac.append({'mac_address': mac, 'data': []})
                    continue

                local_file = tempfile.NamedTemporaryFile(
                    mode='w', delete=False, suffix='.txt'
                )
                local_file.close()
                local_path = local_file.name

                try:
                    scp_cmd = [
                        'scp', '-O',
                        '-o', 'HostKeyAlgorithms=+ssh-rsa',
                        '-o', 'PubkeyAcceptedKeyTypes=+ssh-rsa',
                        '-o', 'StrictHostKeyChecking=no',
                        f'{self.username}@{self.host}:{remote_file}',
                        local_path,
                    ]
                    result = subprocess.run(
                        scp_cmd, capture_output=True, text=True, timeout=30
                    )
                    if result.returncode != 0:
                        self.get_logger().error(
                            f'{data_label} SCP failed for MAC {mac!r}: {result.stderr}'
                        )
                        measurements_by_mac.append({'mac_address': mac, 'data': []})
                        continue

                    with open(local_path, 'r') as f:
                        raw = f.read()

                    data = self._filter_router_measurement_lines(raw)
                    measurements_by_mac.append({'mac_address': mac, 'data': data})
                    flat_valid.extend(data)
                    if not data:
                        self.get_logger().warn(
                            f'{data_label}: no measurement lines for MAC {mac!r} '
                            f'(link may be Unreachable or peer missing)'
                        )
                finally:
                    try:
                        os.unlink(local_path)
                    except OSError:
                        pass

            expected_count = len(self.mac_addresses) * self.measurements_per_batch
            empty_macs = sum(1 for r in measurements_by_mac if not r['data'])

            msg = String()
            msg.data = json.dumps({
                'data_type': data_type,
                'batch_id': batch_id,
                'timestamp': time.time(),
                'mac_addresses': self.mac_addresses,
                'measurements_by_mac': measurements_by_mac,
                'measurements': flat_valid,
                'count': len(flat_valid),
                'expected_count': expected_count,
                'unreachable_count': empty_macs,
                'valid_count': len(flat_valid),
            })
            self.publisher.publish(msg)

            if data_type == 'ftm':
                self.ftm_batch_count += 1
            else:
                self.batch_count += 1

            self.get_logger().info(
                f'Published {data_label} batch #{batch_id + 1}: '
                f'{len(flat_valid)} measurements, {empty_macs} MAC(s) with no data'
            )
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
