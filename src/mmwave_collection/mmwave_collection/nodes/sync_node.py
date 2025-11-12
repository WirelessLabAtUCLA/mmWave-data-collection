#!/usr/bin/env python3
"""Sync node - Synchronize all data and save to disk"""
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import String, Empty
from sensor_msgs.msg import NavSatFix, CompressedImage
from message_filters import Subscriber, ApproximateTimeSynchronizer
import json
from pathlib import Path
from datetime import datetime
import time
from collections import deque


class SyncNode(Node):
    def __init__(self):
        super().__init__('sync_node')
        
        # Declare parameters
        self.declare_parameter('data_path', './data')
        self.declare_parameter('time_tolerance', 2.0)  # Increased tolerance for manual sync
        self.declare_parameter('organize_by_date', True)
        self.declare_parameter('max_queue_size', 50)
        self.declare_parameter('discrete_mode', False)
        self.declare_parameter('gps_required', False)  # Make GPS optional
        
        # Get parameters
        data_path = self.get_parameter('data_path').value
        self.time_tolerance = self.get_parameter('time_tolerance').value
        organize_by_date = self.get_parameter('organize_by_date').value
        max_queue_size = self.get_parameter('max_queue_size').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        self.gps_required = self.get_parameter('gps_required').value
        
        # Setup data directory
        self.data_root = Path(data_path)
        self.session_dir = self._create_session_dir(organize_by_date)
        
        # Create subdirectories
        (self.session_dir / 'rx_router_data').mkdir(exist_ok=True)
        (self.session_dir / 'images').mkdir(exist_ok=True)
        
        # Metadata
        self.metadata = {
            'session_id': self.session_dir.name,
            'start_time': datetime.now().isoformat(),
            'data_points': []
        }
        
        # Message buffers for manual synchronization (String messages don't have headers)
        self.router_buffer = deque(maxlen=max_queue_size)
        self.gps_buffer = deque(maxlen=max_queue_size)
        self.camera_buffer = deque(maxlen=max_queue_size)
        
        # Publisher for save confirmation
        self.save_confirm_pub = self.create_publisher(Empty, '/sync_node/save_complete', 10)
        
        # Direct subscribers
        self.rx_router_sub = self.create_subscription(
            String, '/rx_router/data', self.router_callback, 10)
        self.gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self.gps_callback, 10)
        self.camera_sub = self.create_subscription(
            CompressedImage, '/camera/image/compressed', self.camera_callback, 10)
        
        # Timer for periodic synchronization attempts
        if self.discrete_mode:
            self.create_timer(0.1, self.try_sync_discrete)  # Try to sync every 100ms
        else:
            self.create_timer(0.1, self.try_sync)  # Try to sync every 100ms
        
        self.sample_count = 0
        self.pending_sync = False  # Track if new data arrived
        self.last_gps = None  # Store last GPS for optional mode
        
        mode_str = "discrete" if self.discrete_mode else "continuous"
        gps_str = "required" if self.gps_required else "optional"
        self.get_logger().info(f'Sync node started in {mode_str} mode (GPS {gps_str}), saving to {self.session_dir}')
    
    def _create_session_dir(self, organize_by_date: bool) -> Path:
        """Create session directory"""
        now = datetime.now()
        
        if organize_by_date:
            date_dir = self.data_root / now.strftime('%Y-%m-%d')
            date_dir.mkdir(parents=True, exist_ok=True)
            session_dir = date_dir / f"session_{now.strftime('%H%M%S')}"
        else:
            session_dir = self.data_root / f"session_{now.strftime('%Y%m%d_%H%M%S')}"
        
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    
    def router_callback(self, msg):
        """Store router data with timestamp"""
        ros_time = self.get_clock().now()
        self.router_buffer.append((ros_time, msg))

    def gps_callback(self, msg):
        """Store GPS data with timestamp"""
        # GPS messages have headers with timestamps
        ros_time = Time.from_msg(msg.header.stamp)
        self.gps_buffer.append((ros_time, msg))
        self.last_gps = msg  # Store for optional GPS mode
    
    def camera_callback(self, msg):
        """Store camera data with timestamp"""
        # Camera messages have headers with timestamps
        ros_time = Time.from_msg(msg.header.stamp)
        self.camera_buffer.append((ros_time, msg))

    def try_sync_discrete(self):
        """Synchronize messages in discrete mode"""
        if not self.router_buffer or not self.gps_buffer or not self.camera_buffer:
            return
        
        for i, (router_time, router_msg) in enumerate(self.router_buffer):
            # Find closest GPS message
            gps_match = None
            gps_idx = None
            min_gps_diff = float('inf')
            
            for j, (gps_time, gps_msg) in enumerate(self.gps_buffer):
                time_diff = abs((router_time - gps_time).nanoseconds / 1e9)
                if time_diff < min_gps_diff:
                    min_gps_diff = time_diff
                    gps_match = gps_msg
                    gps_idx = j
            
            # Find closest camera message
            camera_match = None
            camera_idx = None
            min_camera_diff = float('inf')
            
            for k, (camera_time, camera_msg) in enumerate(self.camera_buffer):
                time_diff = abs((router_time - camera_time).nanoseconds / 1e9)
                if time_diff < min_camera_diff:
                    min_camera_diff = time_diff
                    camera_match = camera_msg
                    camera_idx = k
            
            # Found a match! Process it
            self.process_synced_data(router_msg, gps_match, camera_match)
            
            # Remove processed messages from buffers
            # Remove from oldest to newest to maintain indices
            if camera_idx is not None:
                del self.camera_buffer[camera_idx]
            if gps_idx is not None:
                del self.gps_buffer[gps_idx]
            # Remove router message last (we're iterating over it)
            del self.router_buffer[i]
            
            # Only process one match per timer callback
            return

    def try_sync(self):
        """Periodically try to synchronize messages from all three sources"""
        # Need at least one message from each source
        if not self.router_buffer or not self.gps_buffer or not self.camera_buffer:
            return
        
        # Try to find a matching set within time tolerance
        for i, (router_time, router_msg) in enumerate(self.router_buffer):
            # Find closest GPS message
            gps_match = None
            gps_idx = None
            min_gps_diff = float('inf')
            
            for j, (gps_time, gps_msg) in enumerate(self.gps_buffer):
                time_diff = abs((router_time - gps_time).nanoseconds / 1e9)
                if time_diff < min_gps_diff and time_diff < self.time_tolerance:
                    min_gps_diff = time_diff
                    gps_match = gps_msg
                    gps_idx = j
            
            if gps_match is None:
                continue
            
            # Find closest camera message
            camera_match = None
            camera_idx = None
            min_camera_diff = float('inf')
            
            for k, (camera_time, camera_msg) in enumerate(self.camera_buffer):
                time_diff = abs((router_time - camera_time).nanoseconds / 1e9)
                if time_diff < min_camera_diff and time_diff < self.time_tolerance:
                    min_camera_diff = time_diff
                    camera_match = camera_msg
                    camera_idx = k
            
            if camera_match is None:
                continue
            
            # Found a match! Process it
            self.process_synced_data(router_msg, gps_match, camera_match)
            
            # Remove processed messages from buffers
            # Remove from oldest to newest to maintain indices
            if camera_idx is not None:
                del self.camera_buffer[camera_idx]
            if gps_idx is not None:
                del self.gps_buffer[gps_idx]
            # Remove router message last (we're iterating over it)
            del self.router_buffer[i]
            
            # Only process one match per timer callback
            return
    
    def process_synced_data(self, rx_router_msg, gps_msg, camera_msg):
        """Handle synchronized messages from all sources"""
        self.sample_count += 1
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
        
        self.get_logger().info(f'Synchronized sample #{self.sample_count}')
        
        # Parse router batch data (JSON format)
        try:
            batch_data = json.loads(rx_router_msg.data)
            batch_id = batch_data.get('batch_id', 0)
            measurements = batch_data.get('measurements', [])
            measurement_count = batch_data.get('count', 0)
        except json.JSONDecodeError:
            self.get_logger().error('Failed to parse router data as JSON')
            measurements = [rx_router_msg.data]
            batch_id = 0
            measurement_count = 1
        
        # Save RX router batch data
        rx_router_file = self.session_dir / 'rx_router_data' / f'{timestamp_str}_batch{batch_id}.json'
        with open(rx_router_file, 'w') as f:
            json.dump({
                'batch_id': batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': measurements,
                'count': measurement_count
            }, f, indent=2)
        
        # Save image
        image_file = self.session_dir / 'images' / f'{timestamp_str}.jpg'
        image_file.write_bytes(bytes(camera_msg.data))
        
        # Record metadata
        data_point = {
            'index': self.sample_count,
            'timestamp': timestamp.isoformat(),
            'gps': {
                'latitude': gps_msg.latitude if gps_msg else 0.0,
                'longitude': gps_msg.longitude if gps_msg else 0.0,
                'altitude': gps_msg.altitude if gps_msg else 0.0,
            },
            'router_batch': {
                'batch_id': batch_id,
                'measurement_count': measurement_count,
                'file': str(rx_router_file.relative_to(self.session_dir))
            },
            'image': str(image_file.relative_to(self.session_dir))
        }
        
        self.metadata['data_points'].append(data_point)
        
        # Save metadata incrementally
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        if gps_msg:
            self.get_logger().info(
                f'Saved sample #{self.sample_count} - '
                f'GPS: {gps_msg.latitude:.6f}, {gps_msg.longitude:.6f} - '
                f'Router batch: {measurement_count} measurements'
            )
        else:
            self.get_logger().info(
                f'Saved sample #{self.sample_count} - '
                f'GPS: N/A - '
                f'Router batch: {measurement_count} measurements'
            )
        
        # Publish save confirmation for automated collection coordination
        self.save_confirm_pub.publish(Empty())
    
    def destroy_node(self):
        """Cleanup - finalize metadata"""
        self.metadata['end_time'] = datetime.now().isoformat()
        self.metadata['total_samples'] = self.sample_count
        
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        self.get_logger().info(f'Session complete: {self.sample_count} samples saved')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SyncNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

