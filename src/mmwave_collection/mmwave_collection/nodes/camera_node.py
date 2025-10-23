#!/usr/bin/env python3
"""Camera node - Capture images from webcam"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        
        # Declare parameters
        self.declare_parameter('device_id', 0)
        self.declare_parameter('width', 1920)
        self.declare_parameter('height', 1080)
        self.declare_parameter('jpeg_quality', 85)
        
        # Get parameters
        device_id = self.get_parameter('device_id').value
        width = self.get_parameter('width').value
        height = self.get_parameter('height').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value
        
        # Publisher
        self.publisher = self.create_publisher(CompressedImage, '/camera/image/compressed', 10)
        
        # Open camera
        self.cap = cv2.VideoCapture(device_id)
        
        if not self.cap.isOpened():
            self.get_logger().error(f'Failed to open camera {device_id}')
            # Try alternative device IDs
            for alt_id in [0, 1, 2]:
                if alt_id != device_id:
                    self.cap = cv2.VideoCapture(alt_id)
                    if self.cap.isOpened():
                        self.get_logger().info(f'Using camera {alt_id} instead')
                        break
        
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.get_logger().info(f'Camera node started (device {device_id})')
            
            # Timer for capture (will be triggered by sync node in practice)
            self.timer = self.create_timer(1.0, self.capture_image)  # 1Hz for now
        else:
            self.get_logger().error('Could not open any camera')
            self.cap = None
    
    def capture_image(self):
        """Capture and publish image"""
        if self.cap is None or not self.cap.isOpened():
            return
        
        ret, frame = self.cap.read()
        
        if ret:
            # Compress image to JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            _, jpeg_data = cv2.imencode('.jpg', frame, encode_param)
            
            # Create message
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

