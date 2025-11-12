#!/usr/bin/env python3
"""Automated collection coordinator node - Orchestrates rotation table and router for systematic data collection"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, Int16
from enum import Enum


class CollectionState(Enum):
    """State machine for automated collection"""
    IDLE = 0
    ROTATING_AND_COLLECTING = 1
    COMPLETED = 2


class AutomatedCollectionNode(Node):
    def __init__(self):
        super().__init__('automated_collection_node')
        
        # Declare parameters
        self.declare_parameter('angle_start', -30)
        self.declare_parameter('angle_end', 30)
        self.declare_parameter('angle_step', 5)
        self.declare_parameter('auto_start', True)  # Start automatically on init
        
        # Get parameters
        self.angle_start = self.get_parameter('angle_start').value
        self.angle_end = self.get_parameter('angle_end').value
        self.angle_step = self.get_parameter('angle_step').value
        auto_start = self.get_parameter('auto_start').value
        
        # Generate angle sequence
        self.angle_sequence = list(range(self.angle_start, self.angle_end + 1, self.angle_step))
        self.current_angle_index = 0
        self.target_angle = None
        
        # Collection state
        self.state = CollectionState.IDLE
        
        # Statistics
        self.angles_completed = 0
        
        # Publishers
        self.angle_command_pub = self.create_publisher(Int16, '/rotation_table/angle_command', 10)
        
        # Subscribers
        self.save_confirm_sub = self.create_subscription(
            Empty, '/sync_node/save_complete', self.save_confirm_callback, 10)
        
        self.get_logger().info(
            f'Automated collection node initialized:\n'
            f'  Angles: {self.angle_start}° to {self.angle_end}° (step: {self.angle_step}°)\n'
            f'  Total angles: {len(self.angle_sequence)}'
        )
        
        if auto_start:
            self.get_logger().info('Auto-starting collection in 5 seconds...')
            # Create a one-shot timer
            self.auto_start_timer = self.create_timer(5.0, self._auto_start_once)
    
    def _auto_start_once(self):
        """One-shot timer callback to start collection"""
        self.auto_start_timer.cancel()
        self.start_collection()
    
    def start_collection(self):
        """Start the automated collection process"""
        if self.state != CollectionState.IDLE:
            self.get_logger().warn('Collection already in progress')
            return
        
        self.get_logger().info('Starting automated collection...')
        self.current_angle_index = 0
        self.angles_completed = 0
        self.command_next_angle()
    
    def command_next_angle(self):
        """Command rotation table to move to next angle"""
        if self.current_angle_index >= len(self.angle_sequence):
            self.state = CollectionState.COMPLETED
            self.get_logger().info(
                f'Collection COMPLETED!\n'
                f'  Total angles: {self.angles_completed}/{len(self.angle_sequence)}'
            )
            return
        
        self.target_angle = self.angle_sequence[self.current_angle_index]
        msg = Int16()
        msg.data = self.target_angle
        self.angle_command_pub.publish(msg)
        self.get_logger().info(f'Commanding rotation to {self.target_angle}° ({self.current_angle_index+1}/{len(self.angle_sequence)})')
        self.state = CollectionState.ROTATING_AND_COLLECTING
    
    def save_confirm_callback(self, msg):
        """Receive confirmation that sync_node saved data"""
        if self.state == CollectionState.ROTATING_AND_COLLECTING:
            self.angles_completed += 1
            self.get_logger().info(f'Data saved for angle {self.target_angle}°')
            # Move to next angle
            self.current_angle_index += 1
            self.command_next_angle()
    
    def destroy_node(self):
        """Cleanup"""
        self.get_logger().info('Shutting down automated collection node')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AutomatedCollectionNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

