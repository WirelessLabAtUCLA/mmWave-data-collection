#!/usr/bin/env python3
"""Sync node - Synchronize all data and save to disk"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import NavSatFix, CompressedImage
from message_filters import Subscriber, ApproximateTimeSynchronizer
import json
from pathlib import Path
from datetime import datetime


class SyncNode(Node):
    def __init__(self):
        super().__init__('sync_node')
        
        # Declare parameters
        self.declare_parameter('data_path', './data')
        self.declare_parameter('time_tolerance', 0.5)
        self.declare_parameter('organize_by_date', True)
        
        # Get parameters
        data_path = self.get_parameter('data_path').value
        time_tolerance = self.get_parameter('time_tolerance').value
        organize_by_date = self.get_parameter('organize_by_date').value
        
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
        
        # Subscribers with message_filters for synchronization
        self.rx_router_sub = Subscriber(self, String, '/rx_router/data')
        self.gps_sub = Subscriber(self, NavSatFix, '/gps/fix')
        self.camera_sub = Subscriber(self, CompressedImage, '/camera/image/compressed')
        
        # Synchronizer - synchronize all 4 data sources
        self.sync = ApproximateTimeSynchronizer(
            [self.rx_router_sub, self.gps_sub, self.camera_sub],
            queue_size=10,
            slop=time_tolerance
        )
        self.sync.registerCallback(self.sync_callback)
        
        self.sample_count = 0
        self.get_logger().info(f'Sync node started, saving to {self.session_dir}')
    
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
    
    def sync_callback(self, rx_router_msg, tx_router_msg, gps_msg, camera_msg):
        """Handle synchronized messages from all sources"""
        self.sample_count += 1
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%H%M%S')
        
        self.get_logger().info(f'Synchronized sample #{self.sample_count}')
        
        # Save RX router data
        rx_router_file = self.session_dir / 'rx_router_data' / f'{timestamp_str}_rx_router.txt'
        rx_router_file.write_text(rx_router_msg.data)
        
        # Save image
        image_file = self.session_dir / 'images' / f'{timestamp_str}.jpg'
        image_file.write_bytes(bytes(camera_msg.data))
        
        # Record metadata
        data_point = {
            'index': self.sample_count,
            'timestamp': timestamp.isoformat(),
            'gps': {
                'latitude': gps_msg.latitude,
                'longitude': gps_msg.longitude,
                'altitude': gps_msg.altitude,
            },
            'files': {
                'rx_router_data': str(rx_router_file.relative_to(self.session_dir)),
                'image': str(image_file.relative_to(self.session_dir))
            }
        }
        
        self.metadata['data_points'].append(data_point)
        
        # Save metadata
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        self.get_logger().info(
            f'Saved sample #{self.sample_count} - '
            f'GPS: {gps_msg.latitude:.6f}, {gps_msg.longitude:.6f}'
        )
    
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

