#!/usr/bin/env python3
"""Rotation table node - Control the rotation table"""
import serial
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, String, Int16
import numpy as np
import time

class RotationTableNode(Node):
    def __init__(self):
        super().__init__('rotation_table_node')
        
        # Declare parameters
        self.declare_parameter('rotation_table_device', '/dev/ttyACM0')
        self.declare_parameter('rotation_table_baudrate', 115200)
        self.declare_parameter('timeout', 0.1)
        self.declare_parameter('discrete_mode', False)
        self.declare_parameter('stabilization_time', 2.0)  # Seconds to wait after rotation

        device = self.get_parameter('rotation_table_device').value
        baudrate = self.get_parameter('rotation_table_baudrate').value
        timeout = self.get_parameter('timeout').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        self.stabilization_time = self.get_parameter('stabilization_time').value
        
        self.angle_range = np.arange(-60, 60+1, 1)
        self.current_angle = 0
        
        # Publishers
        self.angle_pub = self.create_publisher(Int16, '/rotation_table/angle', 10)
        self.rotation_complete_pub = self.create_publisher(Empty, '/rotation_table/rotation_complete', 10)
        
        # Angle command subscriber for automated collection
        self.angle_command_sub = self.create_subscription(
            Int16, '/rotation_table/angle_command', self.angle_command_callback, 10)

        # Open serial port
        try:
            self.serial = serial.Serial(device, baudrate, timeout=timeout)
            self.get_logger().info(f'Rotation table node started on {device}')
        except Exception as e:
            self.get_logger().error(f'Failed to open rotation table device: {e}')
            self.serial = None
            return
    
    def angle_command_callback(self, msg):
        """Handle angle command from automated collection coordinator"""
        target_angle = msg.data
        self.get_logger().info(f'Received angle command: {target_angle}°')
        self.rotate_to_angle(target_angle)
    
    def rotate_to_angle(self, angle):
        """Rotate table to a specific angle and publish rotation complete after stabilization"""
        if self.serial is None or not self.serial.is_open:
            self.get_logger().error('Serial port not available')
            return
        
        # Send angle command to Arduino
        self.serial.write(bytes(str(angle), 'utf-8'))
        self.get_logger().info(f'Rotating table to {angle}°')
        
        # Publish current angle
        msg = Int16()
        msg.data = angle
        self.angle_pub.publish(msg)
        
        # Wait for stabilization
        time.sleep(self.stabilization_time)
        
        # Publish rotation complete to trigger data collection
        self.get_logger().info(f'Rotation complete at {angle}°, triggering data collection')
        self.rotation_complete_pub.publish(Empty())

    def destroy_node(self):
        """Cleanup"""
        if self.serial and self.serial.is_open:
            self.serial.write(bytes(str(0),'utf-8'))
            self.serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RotationTableNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()