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
        self.declare_parameter('video_mode', False)  # Video recording mode (no per-frame sync)
        
        # Get parameters
        data_path = self.get_parameter('data_path').value
        self.time_tolerance = self.get_parameter('time_tolerance').value
        organize_by_date = self.get_parameter('organize_by_date').value
        max_queue_size = self.get_parameter('max_queue_size').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        self.gps_required = self.get_parameter('gps_required').value
        self.video_mode = self.get_parameter('video_mode').value
        
        # Setup data directory
        self.data_root = Path(data_path)
        self.session_dir = self._create_session_dir(organize_by_date)
        
        # Create subdirectories
        (self.session_dir / 'rx_router_data').mkdir(exist_ok=True)
        (self.session_dir / 'ftm_data').mkdir(exist_ok=True)
        (self.session_dir / 'images').mkdir(exist_ok=True)
        
        # Metadata
        self.metadata = {
            'session_id': self.session_dir.name,
            'start_time': datetime.now().isoformat(),
            'data_points': [],
            'video_file': None  # Will be set if video recording is used
        }
        
        # Message buffers for manual synchronization (String messages don't have headers)
        self.router_buffer = deque(maxlen=max_queue_size)
        self.gps_buffer = deque(maxlen=max_queue_size)
        self.camera_buffer = deque(maxlen=max_queue_size)
        
        # For 'both' mode: group CSI and FTM messages together
        self.pending_csi_msg = None
        self.pending_ftm_msg = None
        self.pending_csi_time = None
        self.pending_ftm_time = None
        self.group_timeout = 2.0  # seconds to wait for both CSI and FTM
        
        # Publisher for save confirmation
        self.save_confirm_pub = self.create_publisher(Empty, '/sync_node/save_complete', 10)
        
        # Direct subscribers
        self.rx_router_sub = self.create_subscription(
            String, '/rx_router/data', self.router_callback, 10)
        self.gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self.gps_callback, 10)
        self.camera_sub = self.create_subscription(
            CompressedImage, '/camera/image/compressed', self.camera_callback, 10)
        
        # Video path subscriber (for video recording mode)
        self.video_path_sub = self.create_subscription(
            String, '/camera/video_path', self.video_path_callback, 10)
        
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
        video_str = "video mode (no per-frame sync)" if self.video_mode else "image mode"
        self.get_logger().info(f'Sync node started in {mode_str} mode (GPS {gps_str}, {video_str}), saving to {self.session_dir}')
    
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
        
        # Parse message to check data type
        try:
            batch_data = json.loads(msg.data)
            data_type = batch_data.get('data_type', 'csi')
        except json.JSONDecodeError:
            data_type = 'csi'  # Default to CSI if can't parse
        
        # In discrete mode with 'both', group CSI and FTM together
        if self.discrete_mode and data_type in ['csi', 'ftm']:
            if data_type == 'csi':
                self.pending_csi_msg = msg
                self.pending_csi_time = ros_time
            else:  # ftm
                self.pending_ftm_msg = msg
                self.pending_ftm_time = ros_time
        else:
            # For non-discrete or single mode, add to buffer normally
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
    
    def video_path_callback(self, msg):
        """Handle video file path from camera node"""
        video_path = msg.data
        self.get_logger().info(f'Received video file path: {video_path}')
        
        # Update metadata with video file path
        self.metadata['video_file'] = video_path
        
        # Save metadata
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        self.get_logger().info(f'Updated metadata with video file: {video_path}')

    def try_sync_discrete(self):
        """Synchronize messages in discrete mode"""
        # Check if we have grouped CSI+FTM ready to process
        if self.pending_csi_msg is not None:
            # Check if we also have FTM, or if timeout has passed
            current_time = self.get_clock().now()
            time_since_csi = (current_time - self.pending_csi_time).nanoseconds / 1e9 if self.pending_csi_time else 0
            
            # Process if: we have both, or timeout passed (then process CSI only)
            has_both = self.pending_ftm_msg is not None
            timeout_passed = time_since_csi > self.group_timeout
            
            if has_both or timeout_passed:
                # In video mode, skip camera sync requirement
                if not self.video_mode:
                    # We have at least CSI, check for camera
                    if not self.camera_buffer:
                        return
                
                # Use CSI time as the reference time
                router_time = self.pending_csi_time
                
                # Find closest camera (only if not in video mode)
                camera_match = None
                if not self.video_mode:
                    min_camera_diff = float('inf')
                    
                    for k, (camera_time, camera_msg) in enumerate(self.camera_buffer):
                        time_diff = abs((router_time - camera_time).nanoseconds / 1e9)
                        if time_diff < min_camera_diff:
                            min_camera_diff = time_diff
                            camera_match = camera_msg
                    
                    if camera_match is None:
                        return
                
                # Find GPS if available
                gps_match = None
                if self.gps_buffer:
                    min_gps_diff = float('inf')
                    for j, (gps_time, gps_msg) in enumerate(self.gps_buffer):
                        time_diff = abs((router_time - gps_time).nanoseconds / 1e9)
                        if time_diff < min_gps_diff:
                            min_gps_diff = time_diff
                            gps_match = gps_msg
                
                if gps_match is None and self.last_gps:
                    gps_match = self.last_gps
                
                # Process grouped data
                if timeout_passed and not has_both:
                    self.get_logger().warn('FTM data not received within timeout, processing CSI only')
                
                self.process_grouped_data(self.pending_csi_msg, self.pending_ftm_msg, gps_match, camera_match)
                
                # Clear pending messages
                self.pending_csi_msg = None
                self.pending_ftm_msg = None
                self.pending_csi_time = None
                self.pending_ftm_time = None
                return
        
        # Original buffer-based sync for non-grouped messages
        if not self.router_buffer:
            return
        
        # In discrete mode, check what data we have
        # Skip camera check if in video mode
        if not self.video_mode and not self.camera_buffer:
            return
        
        # GPS handling: only require if gps_required is True
        if self.gps_required and not self.gps_buffer and not self.last_gps:
            return
        
        for i, (router_time, router_msg) in enumerate(self.router_buffer):
            # Find closest GPS message (don't remove it - allow reuse for multiple router messages)
            gps_match = None
            min_gps_diff = float('inf')
            
            if self.gps_buffer:
                for j, (gps_time, gps_msg) in enumerate(self.gps_buffer):
                    time_diff = abs((router_time - gps_time).nanoseconds / 1e9)
                    if time_diff < min_gps_diff:
                        min_gps_diff = time_diff
                        gps_match = gps_msg
            
            # Use last GPS if available and no buffer entries, or None if GPS not required
            if gps_match is None:
                if self.last_gps:
                    gps_match = self.last_gps
                    self.get_logger().debug('Using last GPS for sync (no recent GPS data)')
                elif not self.gps_required:
                    gps_match = None  # Explicitly set to None when GPS is disabled
                    self.get_logger().debug('Syncing without GPS (GPS not required)')
                else:
                    continue  # Skip if GPS required but not available
            
            # Find closest camera message (don't remove it - allow reuse for multiple router messages)
            camera_match = None
            min_camera_diff = float('inf')
            
            if not self.video_mode:
                for k, (camera_time, camera_msg) in enumerate(self.camera_buffer):
                    time_diff = abs((router_time - camera_time).nanoseconds / 1e9)
                    if time_diff < min_camera_diff:
                        min_camera_diff = time_diff
                        camera_match = camera_msg
                
                if camera_match is None:
                    # No camera data available, skip this router message for now
                    continue
            
            # Found a match! Process it
            if gps_match:
                self.get_logger().debug(f'Syncing router message with GPS diff: {min_gps_diff:.3f}s, camera diff: {min_camera_diff:.3f}s')
            else:
                self.get_logger().debug(f'Syncing router message with camera diff: {min_camera_diff:.3f}s (no GPS)')
            
            self.process_synced_data(router_msg, gps_match, camera_match)
            
            # Remove only the router message that was processed
            del self.router_buffer[i]
            
            # Only process one match per timer callback
            return

    def try_sync(self):
        """Periodi[cally try to synchronize messages from all three sources"""
        # In video mode, only need router and optionally GPS
        if self.video_mode:
            if not self.router_buffer:
                return
            # GPS optional in video mode
            if self.gps_required and not self.gps_buffer:
                return
        else:
            # In image mode, need at least router and camera
            if not self.router_buffer or not self.camera_buffer:
                return
            # GPS optional in image mode too
            if self.gps_required and not self.gps_buffer:
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
            
            if gps_match is None and self.gps_required:
                continue
            
            # Find closest camera message (skip if in video mode)
            camera_match = None
            camera_idx = None
            min_camera_diff = float('inf')
            
            if not self.video_mode:
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
    
    def process_grouped_data(self, csi_msg, ftm_msg, gps_msg, camera_msg):
        """Handle grouped CSI+FTM messages from 'both' mode - saves as single data point"""
        self.sample_count += 1
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
        
        self.get_logger().info(f'Synchronized grouped sample #{self.sample_count}')
        
        # Parse CSI data
        csi_batch_id = 0
        csi_measurements = []
        csi_count = 0
        if csi_msg:
            try:
                csi_data = json.loads(csi_msg.data)
                csi_batch_id = csi_data.get('batch_id', 0)
                csi_measurements = csi_data.get('measurements', [])
                csi_count = csi_data.get('count', 0)
            except json.JSONDecodeError:
                self.get_logger().error('Failed to parse CSI data')
        
        # Parse FTM data (may be None if unreliable)
        ftm_batch_id = 0
        ftm_measurements = []
        ftm_count = 0
        if ftm_msg:
            try:
                ftm_data = json.loads(ftm_msg.data)
                ftm_batch_id = ftm_data.get('batch_id', 0)
                ftm_measurements = ftm_data.get('measurements', [])
                ftm_count = ftm_data.get('count', 0)
            except json.JSONDecodeError:
                self.get_logger().error('Failed to parse FTM data')
        
        # Save CSI data
        csi_file = self.session_dir / 'rx_router_data' / f'{timestamp_str}_batch{csi_batch_id}.json'
        with open(csi_file, 'w') as f:
            json.dump({
                'data_type': 'csi',
                'batch_id': csi_batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': csi_measurements,
                'count': csi_count
            }, f, indent=2)
        
        # Save FTM data
        ftm_file = self.session_dir / 'ftm_data' / f'{timestamp_str}_batch{ftm_batch_id}.json'
        with open(ftm_file, 'w') as f:
            json.dump({
                'data_type': 'ftm',
                'batch_id': ftm_batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': ftm_measurements,
                'count': ftm_count
            }, f, indent=2)
        
        # Save image (only if camera_msg is provided)
        if camera_msg:
            image_file = self.session_dir / 'images' / f'{timestamp_str}.jpg'
            image_file.write_bytes(bytes(camera_msg.data))
        else:
            image_file = None
        
        # Record metadata with both CSI and FTM in single data point
        data_point = {
            'index': self.sample_count,
            'timestamp': timestamp.isoformat(),
            'gps': {
                'latitude': gps_msg.latitude if gps_msg else 0.0,
                'longitude': gps_msg.longitude if gps_msg else 0.0,
                'altitude': gps_msg.altitude if gps_msg else 0.0,
            },
            'csi_batch': {
                'batch_id': csi_batch_id,
                'measurement_count': csi_count,
                'file': str(csi_file.relative_to(self.session_dir))
            },
            'ftm_batch': {
                'batch_id': ftm_batch_id,
                'measurement_count': ftm_count,
                'file': str(ftm_file.relative_to(self.session_dir))
            }
        }
        
        # Add image field only if we have one
        if image_file:
            data_point['image'] = str(image_file.relative_to(self.session_dir))
        
        self.metadata['data_points'].append(data_point)
        
        # Save metadata incrementally
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        if gps_msg:
            self.get_logger().info(
                f'Saved grouped sample #{self.sample_count} - '
                f'GPS: {gps_msg.latitude:.6f}, {gps_msg.longitude:.6f} - '
                f'CSI: {csi_count} measurements, FTM: {ftm_count} measurements'
            )
        else:
            self.get_logger().info(
                f'Saved grouped sample #{self.sample_count} - '
                f'GPS: N/A - '
                f'CSI: {csi_count} measurements, FTM: {ftm_count} measurements'
            )
        
        # Publish save confirmation for automated collection coordination
        self.save_confirm_pub.publish(Empty())
    
    def process_synced_data(self, rx_router_msg, gps_msg, camera_msg):
        """Handle synchronized messages from all sources"""
        self.sample_count += 1
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
        
        self.get_logger().info(f'Synchronized sample #{self.sample_count}')
        
        # Parse router batch data (JSON format)
        try:
            batch_data = json.loads(rx_router_msg.data)
            data_type = batch_data.get('data_type', 'csi')  # Default to 'csi' for backward compatibility
            batch_id = batch_data.get('batch_id', 0)
            measurements = batch_data.get('measurements', [])
            measurement_count = batch_data.get('count', 0)
        except json.JSONDecodeError:
            self.get_logger().error('Failed to parse router data as JSON')
            measurements = [rx_router_msg.data]
            batch_id = 0
            measurement_count = 1
            data_type = 'csi'
        
        # Determine save directory and file name based on data type
        if data_type == 'ftm':
            data_dir = self.session_dir / 'ftm_data'
            data_file = data_dir / f'{timestamp_str}_batch{batch_id}.json'
            data_label = 'FTM'
        else:  # csi or default
            data_dir = self.session_dir / 'rx_router_data'
            data_file = data_dir / f'{timestamp_str}_batch{batch_id}.json'
            data_label = 'CSI'
        
        # Save router batch data
        with open(data_file, 'w') as f:
            json.dump({
                'data_type': data_type,
                'batch_id': batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': measurements,
                'count': measurement_count
            }, f, indent=2)
        
        # Save image (only if camera_msg is provided)
        if camera_msg:
            image_file = self.session_dir / 'images' / f'{timestamp_str}.jpg'
            image_file.write_bytes(bytes(camera_msg.data))
        else:
            image_file = None
        
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
                'data_type': data_type,
                'batch_id': batch_id,
                'measurement_count': measurement_count,
                'file': str(data_file.relative_to(self.session_dir))
            }
        }
        
        # Add image field only if we have one
        if image_file:
            data_point['image'] = str(image_file.relative_to(self.session_dir))
        
        self.metadata['data_points'].append(data_point)
        
        # Save metadata incrementally
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        if gps_msg:
            self.get_logger().info(
                f'Saved sample #{self.sample_count} - '
                f'GPS: {gps_msg.latitude:.6f}, {gps_msg.longitude:.6f} - '
                f'{data_label} batch: {measurement_count} measurements'
            )
        else:
            self.get_logger().info(
                f'Saved sample #{self.sample_count} - '
                f'GPS: N/A - '
                f'{data_label} batch: {measurement_count} measurements'
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

