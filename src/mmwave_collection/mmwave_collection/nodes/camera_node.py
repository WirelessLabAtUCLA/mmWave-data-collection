#!/usr/bin/env python3
"""Camera node - Capture images from webcam"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Empty
import cv2


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        
        # Declare parameters
        self.declare_parameter('device_id', 0)
        self.declare_parameter('width', 1920)
        self.declare_parameter('height', 1080)
        self.declare_parameter('jpeg_quality', 85)
        self.declare_parameter('discrete_mode', False)  # New: discrete vs continuous
        self.declare_parameter('fps', 30)  # Target FPS for camera
        
        # Get parameters
        device_id = self.get_parameter('device_id').value
        width = self.get_parameter('width').value
        height = self.get_parameter('height').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        fps = self.get_parameter('fps').value
        
        # Publisher
        self.publisher = self.create_publisher(CompressedImage, '/camera/image/compressed', 10)
        
        # Trigger subscribers for discrete mode and automated collection
        self.trigger_sub = self.create_subscription(
            Empty, '/trigger_collection', self.trigger_callback, 10)
        self.rotation_complete_sub = self.create_subscription(
            Empty, '/rotation_table/rotation_complete', self.rotation_complete_callback, 10)
        
        # Open camera with optimized backend (prefer V4L2 on Linux)
        self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            self.get_logger().warn(f'V4L2 backend failed, trying default backend')
            self.cap = cv2.VideoCapture(device_id)
            
        if not self.cap.isOpened():
            self.get_logger().error(f'Failed to open camera {device_id}')
            # Try alternative device IDs
            for alt_id in [0, 1, 2]:
                if alt_id != device_id:
                    self.cap = cv2.VideoCapture(alt_id, cv2.CAP_V4L2)
                    if self.cap.isOpened():
                        self.get_logger().info(f'Using camera {alt_id} instead')
                        break
        
        if self.cap.isOpened():
            # Set camera properties for optimal performance
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
            # Critical: Set buffer size to 1 to avoid stale frames
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Disable autofocus for faster capture (optional, comment out if needed)
            # self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            
            # Use MJPEG format if available (faster than raw)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            # Warm up camera - discard first few frames
            for _ in range(5):
                self.cap.read()
            
            mode_str = "discrete" if self.discrete_mode else "continuous"
            self.get_logger().info(f'Camera node started in {mode_str} mode (device {device_id})')
            self.get_logger().info(f'Camera configured: {width}x{height} @ {fps}fps, buffer=1')
            
            # Timer for capture in continuous mode only
            if not self.discrete_mode:
                self.timer = self.create_timer(1.0, self.capture_image)  # 1Hz for continuous
        else:
            self.get_logger().error('Could not open any camera')
            self.cap = None
    
    def trigger_callback(self, msg):
        """Handle manual collection trigger (discrete mode)"""
        if self.discrete_mode:
            self.capture_image()
    
    def rotation_complete_callback(self, msg):
        """Handle rotation complete signal (automated collection)"""
        if self.discrete_mode:
            self.get_logger().info('Rotation complete, capturing image')
            self.capture_image()
    
    def capture_image(self):
        """Capture and publish image"""
        if self.cap is None or not self.cap.isOpened():
            return
        
        # Clear buffer by reading and discarding frames (grab is faster than read)
        # This ensures we get the latest frame, not a stale buffered one
        for _ in range(2):
            self.cap.grab()
        
        # Now retrieve and decode the latest frame
        ret, frame = self.cap.retrieve()
        
        if not ret:
            # Fallback to regular read if retrieve fails
            ret, frame = self.cap.read()
        
        if ret:
            # Compress image to JPEG with optimized parameters
            encode_param = [
                int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality,
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,  # Enable optimization
                int(cv2.IMWRITE_JPEG_PROGRESSIVE), 0  # Disable progressive for speed
            ]
            success, jpeg_data = cv2.imencode('.jpg', frame, encode_param)
            
            if not success:
                self.get_logger().warn('Failed to encode frame to JPEG')
                return
            
            # Create message with precise timestamp
            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'camera'
            msg.format = 'jpeg'
            msg.data = jpeg_data.tobytes()
            
            self.publisher.publish(msg)
            self.get_logger().info(
                f'Captured image ({len(msg.data)} bytes)',
                throttle_duration_sec=5.0
            )
        else:
            self.get_logger().warn('Failed to capture frame')
    
    def destroy_node(self):
        """Cleanup"""
        if self.cap:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

