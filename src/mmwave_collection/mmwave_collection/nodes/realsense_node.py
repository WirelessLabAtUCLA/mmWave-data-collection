#!/usr/bin/env python3
"""Intel RealSense D455 node for SLAM data collection.

Streams color, depth, and IMU data from a RealSense D455 for use with RTAB-Map
and integration with the mmWave data collection pipeline.

Published topics:
  /camera/color/image_raw          (sensor_msgs/Image)          - BGR8, for SLAM
  /camera/color/image/compressed   (sensor_msgs/CompressedImage) - JPEG, saved by sync_node
  /camera/color/camera_info        (sensor_msgs/CameraInfo)
  /camera/depth/image_rect_raw     (sensor_msgs/Image)          - 16UC1, aligned to color
  /camera/depth/camera_info        (sensor_msgs/CameraInfo)
  /camera/imu                      (sensor_msgs/Imu)            - accel + gyro combined

Subscribed topics (discrete mode):
  /trigger_collection              (std_msgs/Empty)
  /rotation_table/rotation_complete (std_msgs/Empty)

Usage:
  ros2 launch mmwave_collection collection.launch.py

  # Direct run with custom resolution:
  ros2 run mmwave_collection realsense_node --ros-args \\
    -p color_width:=1280 -p color_height:=720 -p color_fps:=30
"""
import threading

import cv2
import numpy as np
import pyrealsense2 as rs
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, CompressedImage, Image, Imu
from std_msgs.msg import Empty


class RealSenseNode(Node):
    def __init__(self):
        super().__init__('realsense_node')

        # --- Parameters ---
        self.declare_parameter('color_width', 848)
        self.declare_parameter('color_height', 480)
        self.declare_parameter('color_fps', 30)
        self.declare_parameter('depth_width', 848)
        self.declare_parameter('depth_height', 480)
        self.declare_parameter('depth_fps', 30)
        self.declare_parameter('enable_imu', True)
        self.declare_parameter('jpeg_quality', 85)
        self.declare_parameter('discrete_mode', False)

        color_width = self.get_parameter('color_width').value
        color_height = self.get_parameter('color_height').value
        color_fps = self.get_parameter('color_fps').value
        depth_width = self.get_parameter('depth_width').value
        depth_height = self.get_parameter('depth_height').value
        depth_fps = self.get_parameter('depth_fps').value
        self.enable_imu = self.get_parameter('enable_imu').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value
        self.discrete_mode = self.get_parameter('discrete_mode').value

        # --- Publishers ---
        self.color_pub = self.create_publisher(
            Image, '/camera/color/image_raw', 10)
        self.color_compressed_pub = self.create_publisher(
            CompressedImage, '/camera/color/image/compressed', 10)
        self.color_info_pub = self.create_publisher(
            CameraInfo, '/camera/color/camera_info', 10)
        self.depth_pub = self.create_publisher(
            Image, '/camera/depth/image_rect_raw', 10)
        self.depth_info_pub = self.create_publisher(
            CameraInfo, '/camera/depth/camera_info', 10)

        if self.enable_imu:
            self.imu_pub = self.create_publisher(Imu, '/camera/imu', 10)

        # --- Trigger subscriptions ---
        self.create_subscription(
            Empty, '/trigger_collection', self._trigger_callback, 10)
        self.create_subscription(
            Empty, '/rotation_table/rotation_complete', self._rotation_complete_callback, 10)

        # --- RealSense pipeline setup ---
        self.pipeline = rs.pipeline()
        config = rs.config()

        config.enable_stream(
            rs.stream.color, color_width, color_height, rs.format.bgr8, color_fps)
        config.enable_stream(
            rs.stream.depth, depth_width, depth_height, rs.format.z16, depth_fps)

        if self.enable_imu:
            # D455 accel: 100 or 200 Hz; gyro: 200 or 400 Hz
            config.enable_stream(rs.stream.accel, rs.format.motion_xyz32f, 200)
            config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 200)

        try:
            profile = self.pipeline.start(config)
        except RuntimeError as e:
            self.get_logger().fatal(f'Failed to start RealSense pipeline: {e}')
            raise

        # Depth aligned to color frame so they share intrinsics and resolution
        self.align = rs.align(rs.stream.color)

        # Cache intrinsics from the color stream (depth adopts them post-align)
        self._color_intr, self._depth_intr = self._get_intrinsics(profile)

        # IMU state: buffer latest accel so it can be paired with each gyro reading
        self._last_accel = None
        self._accel_lock = threading.Lock()

        # Frame counter for periodic logging
        self._frame_count = 0

        # --- Background capture thread ---
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name='realsense_capture')
        self._capture_thread.start()

        mode = 'discrete' if self.discrete_mode else 'continuous'
        self.get_logger().info(
            f'RealSense node started ({mode} mode) '
            f'| color {color_width}x{color_height}@{color_fps}fps '
            f'| depth {depth_width}x{depth_height}@{depth_fps}fps '
            f'| IMU {"enabled" if self.enable_imu else "disabled"}'
        )

    # ------------------------------------------------------------------
    # Intrinsics helpers
    # ------------------------------------------------------------------

    def _get_intrinsics(self, profile):
        """Return (color_intr, depth_intr) from the active pipeline profile.

        After alignment depth adopts the color intrinsics, so both entries
        end up identical — but we retrieve them separately in case the user
        runs without alignment in a future revision.
        """
        color_stream = profile.get_stream(rs.stream.color).as_video_stream_profile()
        depth_stream = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        return color_stream.get_intrinsics(), depth_stream.get_intrinsics()

    def _build_camera_info(self, intr, frame_id: str) -> CameraInfo:
        """Construct a CameraInfo message from a pyrealsense2 intrinsics object."""
        msg = CameraInfo()
        msg.header.frame_id = frame_id
        msg.width = intr.width
        msg.height = intr.height
        msg.distortion_model = 'plumb_bob'
        # coeffs order: k1, k2, p1, p2, k3
        msg.d = list(intr.coeffs)
        msg.k = [
            intr.fx,  0.0,     intr.ppx,
            0.0,      intr.fy, intr.ppy,
            0.0,      0.0,     1.0,
        ]
        msg.r = [1.0, 0.0, 0.0,
                 0.0, 1.0, 0.0,
                 0.0, 0.0, 1.0]
        msg.p = [
            intr.fx, 0.0,     intr.ppx, 0.0,
            0.0,     intr.fy, intr.ppy, 0.0,
            0.0,     0.0,     1.0,      0.0,
        ]
        return msg

    # ------------------------------------------------------------------
    # Trigger callbacks (discrete mode — sync_node handles the actual gate)
    # ------------------------------------------------------------------

    def _trigger_callback(self, _msg):
        if self.discrete_mode:
            self.get_logger().debug('Trigger received (streaming continuously)')

    def _rotation_complete_callback(self, _msg):
        if self.discrete_mode:
            self.get_logger().debug('Rotation complete received (streaming continuously)')

    # ------------------------------------------------------------------
    # Capture loop (background thread)
    # ------------------------------------------------------------------

    def _capture_loop(self):
        """Poll the RealSense pipeline and publish all frame types."""
        while self._running:
            try:
                # wait_for_frames returns the next composite frameset;
                # motion frames (if enabled) arrive inside the same frameset.
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            except RuntimeError as e:
                if self._running:
                    self.get_logger().warn(f'wait_for_frames timeout/error: {e}')
                continue

            stamp = self.get_clock().now().to_msg()

            # -- IMU --
            if self.enable_imu:
                self._handle_motion(frames, stamp)

            # -- Video (depth aligned to color) --
            try:
                aligned = self.align.process(frames)
            except RuntimeError as e:
                self.get_logger().warn(f'Frame alignment failed: {e}')
                continue

            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()

            if color_frame and depth_frame:
                self._publish_color(stamp, color_frame)
                self._publish_depth(stamp, depth_frame)
                self._frame_count += 1
                if self._frame_count % 150 == 0:  # log every ~5 s at 30 fps
                    self.get_logger().info(
                        f'Streaming: {self._frame_count} frames captured',
                        throttle_duration_sec=5.0)

    # ------------------------------------------------------------------
    # IMU handling
    # ------------------------------------------------------------------

    def _handle_motion(self, frames, stamp):
        """Extract accel and gyro frames and publish a combined Imu message.

        The D455 accel and gyro run at different (or equal) rates.  We buffer
        the latest accel reading and publish an Imu message each time a gyro
        frame is available, pairing it with the most recent accel sample.
        """
        accel_frame = frames.first_or_default(rs.stream.accel)
        gyro_frame = frames.first_or_default(rs.stream.gyro)

        if accel_frame:
            data = accel_frame.as_motion_frame().get_motion_data()
            with self._accel_lock:
                self._last_accel = (data.x, data.y, data.z)

        if gyro_frame:
            gyro_data = gyro_frame.as_motion_frame().get_motion_data()
            with self._accel_lock:
                accel_snapshot = self._last_accel

            if accel_snapshot is not None:
                self._publish_imu(stamp, accel_snapshot,
                                  (gyro_data.x, gyro_data.y, gyro_data.z))

    # ------------------------------------------------------------------
    # Publishers
    # ------------------------------------------------------------------

    def _publish_color(self, stamp, color_frame):
        color_array = np.asanyarray(color_frame.get_data())

        # Raw uncompressed — consumed by RTAB-Map
        raw_msg = Image()
        raw_msg.header.stamp = stamp
        raw_msg.header.frame_id = 'camera_color_optical_frame'
        raw_msg.height, raw_msg.width = color_array.shape[:2]
        raw_msg.encoding = 'bgr8'
        raw_msg.is_bigendian = False
        raw_msg.step = raw_msg.width * 3
        raw_msg.data = color_array.tobytes()
        self.color_pub.publish(raw_msg)

        # Compressed JPEG — saved to disk by sync_node
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality,
                         int(cv2.IMWRITE_JPEG_OPTIMIZE), 1]
        ok, jpeg_buf = cv2.imencode('.jpg', color_array, encode_params)
        if ok:
            comp_msg = CompressedImage()
            comp_msg.header = raw_msg.header
            comp_msg.format = 'jpeg'
            comp_msg.data = jpeg_buf.tobytes()
            self.color_compressed_pub.publish(comp_msg)

        # Camera info (fresh copy per frame to avoid stamp mutation race)
        info = self._build_camera_info(self._color_intr, 'camera_color_optical_frame')
        info.header.stamp = stamp
        self.color_info_pub.publish(info)

    def _publish_depth(self, stamp, depth_frame):
        """Publish aligned depth as 16UC1 (millimetres, matching RealSense default)."""
        depth_array = np.asanyarray(depth_frame.get_data())

        msg = Image()
        msg.header.stamp = stamp
        # Depth is aligned to color, so they share the same optical frame
        msg.header.frame_id = 'camera_color_optical_frame'
        msg.height, msg.width = depth_array.shape[:2]
        msg.encoding = '16UC1'
        msg.is_bigendian = False
        msg.step = msg.width * 2
        msg.data = depth_array.tobytes()
        self.depth_pub.publish(msg)

        info = self._build_camera_info(self._color_intr, 'camera_color_optical_frame')
        info.header.stamp = stamp
        self.depth_info_pub.publish(info)

    def _publish_imu(self, stamp, accel, gyro):
        """Publish combined accel + gyro as sensor_msgs/Imu.

        Orientation is not estimated here (covariance[0] = -1 signals unknown).
        RTAB-Map or an external EKF can integrate these measurements.
        """
        msg = Imu()
        msg.header.stamp = stamp
        msg.header.frame_id = 'camera_imu_optical_frame'

        msg.orientation_covariance[0] = -1.0  # orientation unknown

        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = accel
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gyro

        self.imu_pub.publish(msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy_node(self):
        self.get_logger().info('Shutting down RealSense node...')
        self._running = False
        self._capture_thread.join(timeout=3.0)
        try:
            self.pipeline.stop()
        except RuntimeError:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RealSenseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
