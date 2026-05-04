#!/usr/bin/env python3
"""Sync node - Synchronize all data and save to disk.

Subscribes to:
  /rx_router/data                  (std_msgs/String)            - mmWave CSI/FTM batches
  /camera/color/image/compressed   (sensor_msgs/CompressedImage) - from realsense_node
  /rtabmap/odom                    (nav_msgs/Odometry)           - SLAM-corrected pose
  /odom                            (nav_msgs/Odometry)           - visual odometry fallback

Saves per-sample:
  images/<timestamp>.jpg
  rx_router_data/<timestamp>_batch<id>.json
  ftm_data/<timestamp>_batch<id>.json
  metadata.json  (updated incrementally)
"""
import json
from collections import deque
from datetime import datetime
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Empty, String


class SyncNode(Node):
    def __init__(self):
        super().__init__('sync_node')

        # --- Parameters ---
        self.declare_parameter('data_path', './data')
        self.declare_parameter('time_tolerance', 2.0)
        self.declare_parameter('organize_by_date', True)
        self.declare_parameter('max_queue_size', 50)
        self.declare_parameter('discrete_mode', False)
        self.declare_parameter('pose_required', False)  # SLAM pose optional

        data_path = self.get_parameter('data_path').value
        self.time_tolerance = self.get_parameter('time_tolerance').value
        organize_by_date = self.get_parameter('organize_by_date').value
        max_queue_size = self.get_parameter('max_queue_size').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        self.pose_required = self.get_parameter('pose_required').value

        # --- Session directory ---
        self.data_root = Path(data_path)
        self.session_dir = self._create_session_dir(organize_by_date)

        (self.session_dir / 'rx_router_data').mkdir(exist_ok=True)
        (self.session_dir / 'ftm_data').mkdir(exist_ok=True)
        (self.session_dir / 'images').mkdir(exist_ok=True)

        self.metadata = {
            'session_id': self.session_dir.name,
            'start_time': datetime.now().isoformat(),
            'data_points': [],
        }

        # --- Message buffers ---
        self.router_buffer = deque(maxlen=max_queue_size)
        self.pose_buffer = deque(maxlen=max_queue_size)
        self.camera_buffer = deque(maxlen=max_queue_size)

        # Grouped CSI+FTM state (for 'both' collection mode)
        self.pending_csi_msg = None
        self.pending_ftm_msg = None
        self.pending_csi_time = None
        self.pending_ftm_time = None
        self.group_timeout = 2.0

        # Carry-forward: reuse last known pose when buffer is empty
        self.last_pose = None

        self.sample_count = 0

        # --- Publishers ---
        self.save_confirm_pub = self.create_publisher(Empty, '/sync_node/save_complete', 10)

        # --- Subscribers ---
        self.create_subscription(String, '/rx_router/data', self._router_callback, 10)
        self.create_subscription(
            CompressedImage, '/camera/color/image/compressed', self._camera_callback, 10)
        # Accept pose from either the SLAM-corrected topic or the raw visual odometry
        # topic — whichever RTAB-Map is publishing goes into the same buffer.
        self.create_subscription(Odometry, '/rtabmap/odom', self._pose_callback, 10)
        self.create_subscription(Odometry, '/odom', self._pose_callback, 10)

        # --- Sync timer ---
        sync_fn = self._try_sync_discrete if self.discrete_mode else self._try_sync
        self.create_timer(0.1, sync_fn)

        mode = 'discrete' if self.discrete_mode else 'continuous'
        pose = 'required' if self.pose_required else 'optional'
        self.get_logger().info(
            f'Sync node started in {mode} mode (SLAM pose {pose}), '
            f'saving to {self.session_dir}')
        self.get_logger().info(
            'Listening for pose on /rtabmap/odom and /odom (whichever RTAB-Map publishes)')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_session_dir(self, organize_by_date: bool) -> Path:
        now = datetime.now()
        if organize_by_date:
            date_dir = self.data_root / now.strftime('%Y-%m-%d')
            date_dir.mkdir(parents=True, exist_ok=True)
            session_dir = date_dir / f"session_{now.strftime('%H%M%S')}"
        else:
            session_dir = self.data_root / f"session_{now.strftime('%Y%m%d_%H%M%S')}"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    @staticmethod
    def _pose_to_dict(odom_msg) -> dict:
        """Extract x/y/z position and quaternion orientation from an Odometry message."""
        p = odom_msg.pose.pose.position
        q = odom_msg.pose.pose.orientation
        return {
            'x': p.x,
            'y': p.y,
            'z': p.z,
            'qx': q.x,
            'qy': q.y,
            'qz': q.z,
            'qw': q.w,
        }

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _router_callback(self, msg):
        ros_time = self.get_clock().now()
        try:
            batch_data = json.loads(msg.data)
            data_type = batch_data.get('data_type', 'csi')
        except json.JSONDecodeError:
            data_type = 'csi'

        if self.discrete_mode and data_type in ('csi', 'ftm'):
            if data_type == 'csi':
                self.pending_csi_msg = msg
                self.pending_csi_time = ros_time
            else:
                self.pending_ftm_msg = msg
                self.pending_ftm_time = ros_time
        else:
            self.router_buffer.append((ros_time, msg))

    def _pose_callback(self, msg):
        ros_time = Time.from_msg(msg.header.stamp)
        self.pose_buffer.append((ros_time, msg))
        if self.last_pose is None:
            self.get_logger().info(
                f'Receiving pose from frame_id="{msg.header.frame_id}" — '
                f'odometry active at ({msg.pose.pose.position.x:.2f}, '
                f'{msg.pose.pose.position.y:.2f})')
        self.last_pose = msg

    def _camera_callback(self, msg):
        ros_time = Time.from_msg(msg.header.stamp)
        self.camera_buffer.append((ros_time, msg))

    # ------------------------------------------------------------------
    # Synchronisation (continuous mode)
    # ------------------------------------------------------------------

    def _try_sync(self):
        if not self.router_buffer or not self.camera_buffer:
            return
        if self.pose_required and not self.pose_buffer and self.last_pose is None:
            return

        for i, (router_time, router_msg) in enumerate(self.router_buffer):
            # Closest pose within tolerance
            pose_match = self._closest(self.pose_buffer, router_time, self.time_tolerance)
            if pose_match is None:
                pose_match = self.last_pose
            if pose_match is None and self.pose_required:
                continue

            # Closest camera within tolerance
            camera_match, camera_idx = self._closest_indexed(
                self.camera_buffer, router_time, self.time_tolerance)
            if camera_match is None:
                continue

            self._process_synced(router_msg, pose_match, camera_match)

            if camera_idx is not None:
                del self.camera_buffer[camera_idx]
            del self.router_buffer[i]
            return

    # ------------------------------------------------------------------
    # Synchronisation (discrete mode)
    # ------------------------------------------------------------------

    def _try_sync_discrete(self):
        if self.pending_csi_msg is not None:
            current_time = self.get_clock().now()
            elapsed = (
                (current_time - self.pending_csi_time).nanoseconds / 1e9
                if self.pending_csi_time else 0
            )
            has_both = self.pending_ftm_msg is not None
            timed_out = elapsed > self.group_timeout

            if has_both or timed_out:
                if not self.camera_buffer:
                    return

                ref_time = self.pending_csi_time

                camera_match = self._closest(self.camera_buffer, ref_time)
                if camera_match is None:
                    return

                pose_match = self._closest(self.pose_buffer, ref_time)
                if pose_match is None:
                    pose_match = self.last_pose

                if timed_out and not has_both:
                    self.get_logger().warn(
                        'FTM data not received within timeout, processing CSI only')

                self._process_grouped(
                    self.pending_csi_msg, self.pending_ftm_msg, pose_match, camera_match)

                self.pending_csi_msg = None
                self.pending_ftm_msg = None
                self.pending_csi_time = None
                self.pending_ftm_time = None
                return

        if not self.router_buffer:
            return
        if not self.camera_buffer:
            return
        if self.pose_required and not self.pose_buffer and self.last_pose is None:
            return

        for i, (router_time, router_msg) in enumerate(self.router_buffer):
            pose_match = self._closest(self.pose_buffer, router_time)
            if pose_match is None:
                pose_match = self.last_pose
            if pose_match is None and self.pose_required:
                continue

            camera_match = self._closest(self.camera_buffer, router_time)
            if camera_match is None:
                continue

            self._process_synced(router_msg, pose_match, camera_match)
            del self.router_buffer[i]
            return

    # ------------------------------------------------------------------
    # Buffer search utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _closest(buffer, ref_time, tolerance=None):
        """Return the message in buffer closest to ref_time, within optional tolerance."""
        best_msg = None
        best_diff = float('inf')
        for t, msg in buffer:
            diff = abs((ref_time - t).nanoseconds / 1e9)
            if diff < best_diff:
                if tolerance is None or diff < tolerance:
                    best_diff = diff
                    best_msg = msg
        return best_msg

    @staticmethod
    def _closest_indexed(buffer, ref_time, tolerance=None):
        """Return (message, index) of the closest match, or (None, None)."""
        best_msg = None
        best_idx = None
        best_diff = float('inf')
        for idx, (t, msg) in enumerate(buffer):
            diff = abs((ref_time - t).nanoseconds / 1e9)
            if diff < best_diff:
                if tolerance is None or diff < tolerance:
                    best_diff = diff
                    best_msg = msg
                    best_idx = idx
        return best_msg, best_idx

    # ------------------------------------------------------------------
    # Data processing
    # ------------------------------------------------------------------

    def _process_synced(self, router_msg, pose_msg, camera_msg):
        """Save a single router + pose + image sample."""
        self.sample_count += 1
        timestamp = datetime.now()
        ts_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]

        self.get_logger().info(f'Synchronized sample #{self.sample_count}')

        try:
            batch_data = json.loads(router_msg.data)
            data_type = batch_data.get('data_type', 'csi')
            batch_id = batch_data.get('batch_id', 0)
            measurements = batch_data.get('measurements', [])
            count = batch_data.get('count', 0)
        except json.JSONDecodeError:
            self.get_logger().error('Failed to parse router data as JSON')
            measurements, batch_id, count, data_type = [], 0, 1, 'csi'

        data_dir = (self.session_dir / 'ftm_data'
                    if data_type == 'ftm' else self.session_dir / 'rx_router_data')
        data_file = data_dir / f'{ts_str}_batch{batch_id}.json'
        with open(data_file, 'w') as f:
            json.dump({
                'data_type': data_type,
                'batch_id': batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': measurements,
                'count': count,
            }, f, indent=2)

        image_file = self.session_dir / 'images' / f'{ts_str}.jpg'
        if camera_msg:
            image_file.write_bytes(bytes(camera_msg.data))

        data_point = {
            'index': self.sample_count,
            'timestamp': timestamp.isoformat(),
            'slam_pose': self._pose_to_dict(pose_msg) if pose_msg else None,
            'router_batch': {
                'data_type': data_type,
                'batch_id': batch_id,
                'measurement_count': count,
                'file': str(data_file.relative_to(self.session_dir)),
            },
            'image': str(image_file.relative_to(self.session_dir)),
        }
        self.metadata['data_points'].append(data_point)
        self._write_metadata()

        pose_str = (
            f'pose=({pose_msg.pose.pose.position.x:.2f}, '
            f'{pose_msg.pose.pose.position.y:.2f})'
            if pose_msg else 'pose=N/A'
        )
        self.get_logger().info(
            f'Saved sample #{self.sample_count} - {pose_str} - '
            f'{data_type.upper()} batch: {count} measurements')

        self.save_confirm_pub.publish(Empty())

    def _process_grouped(self, csi_msg, ftm_msg, pose_msg, camera_msg):
        """Save a grouped CSI+FTM sample (used in 'both' collection mode)."""
        self.sample_count += 1
        timestamp = datetime.now()
        ts_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]

        self.get_logger().info(f'Synchronized grouped sample #{self.sample_count}')

        def _parse(msg, default_type):
            if msg is None:
                return 0, [], 0
            try:
                d = json.loads(msg.data)
                return d.get('batch_id', 0), d.get('measurements', []), d.get('count', 0)
            except json.JSONDecodeError:
                self.get_logger().error(f'Failed to parse {default_type} data')
                return 0, [], 0

        csi_batch_id, csi_meas, csi_count = _parse(csi_msg, 'CSI')
        ftm_batch_id, ftm_meas, ftm_count = _parse(ftm_msg, 'FTM')

        csi_file = self.session_dir / 'rx_router_data' / f'{ts_str}_batch{csi_batch_id}.json'
        with open(csi_file, 'w') as f:
            json.dump({
                'data_type': 'csi', 'batch_id': csi_batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': csi_meas, 'count': csi_count,
            }, f, indent=2)

        ftm_file = self.session_dir / 'ftm_data' / f'{ts_str}_batch{ftm_batch_id}.json'
        with open(ftm_file, 'w') as f:
            json.dump({
                'data_type': 'ftm', 'batch_id': ftm_batch_id,
                'timestamp': timestamp.isoformat(),
                'measurements': ftm_meas, 'count': ftm_count,
            }, f, indent=2)

        image_file = self.session_dir / 'images' / f'{ts_str}.jpg'
        if camera_msg:
            image_file.write_bytes(bytes(camera_msg.data))

        data_point = {
            'index': self.sample_count,
            'timestamp': timestamp.isoformat(),
            'slam_pose': self._pose_to_dict(pose_msg) if pose_msg else None,
            'csi_batch': {
                'batch_id': csi_batch_id,
                'measurement_count': csi_count,
                'file': str(csi_file.relative_to(self.session_dir)),
            },
            'ftm_batch': {
                'batch_id': ftm_batch_id,
                'measurement_count': ftm_count,
                'file': str(ftm_file.relative_to(self.session_dir)),
            },
            'image': str(image_file.relative_to(self.session_dir)),
        }
        self.metadata['data_points'].append(data_point)
        self._write_metadata()

        pose_str = (
            f'pose=({pose_msg.pose.pose.position.x:.2f}, '
            f'{pose_msg.pose.pose.position.y:.2f})'
            if pose_msg else 'pose=N/A'
        )
        self.get_logger().info(
            f'Saved grouped sample #{self.sample_count} - {pose_str} - '
            f'CSI: {csi_count} meas, FTM: {ftm_count} meas')

        self.save_confirm_pub.publish(Empty())

    def _write_metadata(self):
        metadata_file = self.session_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy_node(self):
        self.metadata['end_time'] = datetime.now().isoformat()
        self.metadata['total_samples'] = self.sample_count
        self._write_metadata()
        self.get_logger().info(
            f'Session complete: {self.sample_count} samples saved to {self.session_dir}')
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
