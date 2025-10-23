#!/usr/bin/env python3
"""GPS node - Read GPS data and publish NavSatFix"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, NavSatStatus
import serial
import pynmea2


class GPSNode(Node):
    def __init__(self):
        super().__init__('gps_node')
        
        # Declare parameters
        self.declare_parameter('device', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 9600)
        self.declare_parameter('auto_detect', True)
        
        # Get parameters
        device = self.get_parameter('device').value
        baudrate = self.get_parameter('baudrate').value
        auto_detect = self.get_parameter('auto_detect').value
        
        # Auto-detect device if needed
        if auto_detect and device == 'auto':
            from mmwave_collection.utils import find_gps_device
            device = find_gps_device()
            if device is None:
                self.get_logger().error('No GPS device found!')
                return
            self.get_logger().info(f'Auto-detected GPS device: {device}')
        
        # Publisher
        self.publisher = self.create_publisher(NavSatFix, '/gps/fix', 10)
        
        # Open serial port
        try:
            self.serial = serial.Serial(device, baudrate, timeout=1)
            self.get_logger().info(f'GPS node started on {device}')
        except Exception as e:
            self.get_logger().error(f'Failed to open GPS device: {e}')
            self.serial = None
            return
        
        # Timer to read GPS
        self.timer = self.create_timer(0.1, self.read_gps)  # 10Hz
    
    def read_gps(self):
        """Read and publish GPS data"""
        if self.serial is None or not self.serial.is_open:
            return
        
        try:
            line = self.serial.readline().decode('ascii', errors='ignore').strip()
            
            if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                msg = pynmea2.parse(line)
                
                # Create NavSatFix message
                fix = NavSatFix()
                fix.header.stamp = self.get_clock().now().to_msg()
                fix.header.frame_id = 'gps'
                
                fix.latitude = msg.latitude
                fix.longitude = msg.longitude
                fix.altitude = msg.altitude
                
                fix.status.status = NavSatStatus.STATUS_FIX if msg.gps_qual > 0 else NavSatStatus.STATUS_NO_FIX
                fix.status.service = NavSatStatus.SERVICE_GPS
                
                self.publisher.publish(fix)
                
                if msg.gps_qual > 0:
                    self.get_logger().info(
                        f'GPS: {msg.latitude:.6f}, {msg.longitude:.6f}, alt={msg.altitude:.1f}m',
                        throttle_duration_sec=5.0  # Log every 5 seconds max
                    )
                
        except (pynmea2.ParseError, UnicodeDecodeError):
            pass  # Ignore invalid sentences
        except Exception as e:
            self.get_logger().error(f'GPS read error: {e}')
    
    def destroy_node(self):
        """Cleanup"""
        if self.serial and self.serial.is_open:
            self.serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GPSNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

