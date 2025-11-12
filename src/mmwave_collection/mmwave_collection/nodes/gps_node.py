#!/usr/bin/env python3
"""GPS node - Read GPS data and publish NavSatFix"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Empty
import serial
import pynmea2


class GPSNode(Node):
    def __init__(self):
        super().__init__('gps_node')
        
        # Declare parameters
        self.declare_parameter('device', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 9600)
        self.declare_parameter('auto_detect', True)
        self.declare_parameter('discrete_mode', False)  # New: discrete vs continuous
        
        # Get parameters
        device = self.get_parameter('device').value
        baudrate = self.get_parameter('baudrate').value
        auto_detect = self.get_parameter('auto_detect').value
        self.discrete_mode = self.get_parameter('discrete_mode').value
        
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
        
        # Trigger subscribers for discrete mode and automated collection
        self.trigger_sub = self.create_subscription(
            Empty, '/trigger_collection', self.trigger_callback, 10)
        self.rotation_complete_sub = self.create_subscription(
            Empty, '/rotation_table/rotation_complete', self.rotation_complete_callback, 10)
        
        # Open serial port
        try:
            self.serial = serial.Serial(device, baudrate, timeout=1)
            mode_str = "discrete" if self.discrete_mode else "continuous"
            self.get_logger().info(f'GPS node started in {mode_str} mode on {device}')
        except Exception as e:
            self.get_logger().error(f'Failed to open GPS device: {e}')
            self.serial = None
            return
        
        # Store latest GPS data for discrete mode
        self.latest_gps = None
        
        # Timer to continuously read GPS (needed to keep data fresh)
        # In discrete mode, we read continuously but only publish on trigger
        self.timer = self.create_timer(0.1, self.read_gps)  # 10Hz
    
    def trigger_callback(self, msg):
        """Handle manual collection trigger (discrete mode)"""
        if self.discrete_mode and self.latest_gps is not None:
            # Publish the latest GPS reading
            self.publisher.publish(self.latest_gps)
            self.get_logger().info('Manual trigger, publishing GPS sample')
    
    def rotation_complete_callback(self, msg):
        """Handle rotation complete signal (automated collection)"""
        if self.discrete_mode and self.latest_gps is not None:
            # Publish the latest GPS reading
            self.publisher.publish(self.latest_gps)
            self.get_logger().info('Rotation complete, publishing GPS sample')
    
    def read_gps(self):
        """Read and optionally publish GPS data"""
        if self.serial is None or not self.serial.is_open:
            return
        
        try:
            line = self.serial.readline().decode('ascii', errors='ignore').strip()
            
            if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                msg = pynmea2.parse(line)
                
                # Skip if no valid GPS data yet
                if msg.latitude is None or msg.longitude is None:
                    return
                
                # Create NavSatFix message
                fix = NavSatFix()
                fix.header.stamp = self.get_clock().now().to_msg()
                fix.header.frame_id = 'gps'
                
                fix.latitude = float(msg.latitude)
                fix.longitude = float(msg.longitude)
                fix.altitude = float(msg.altitude) if msg.altitude is not None else 0.0
                
                fix.status.status = NavSatStatus.STATUS_FIX if msg.gps_qual > 0 else NavSatStatus.STATUS_NO_FIX
                fix.status.service = NavSatStatus.SERVICE_GPS
                
                # Store latest for discrete mode
                self.latest_gps = fix
                
                # Only publish automatically in continuous mode
                if not self.discrete_mode:
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

