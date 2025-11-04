#!/usr/bin/env python3
"""Simple TUI for monitoring data collection"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log
from textual.containers import Container, Vertical, Horizontal
from textual import work
from textual.reactive import reactive
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
from sensor_msgs.msg import NavSatFix, CompressedImage
from threading import Thread
import time


class StatusWidget(Static):
    """Display system status"""
    router_status = reactive("⚪ Disconnected")
    gps_status = reactive("⚪ No Fix")
    camera_status = reactive("⚪ Inactive")
    samples = reactive(0)
    
    def render(self) -> str:
        return f"""[bold]System Status[/bold]
        
Router:  {self.router_status}
GPS:     {self.gps_status}
Camera:  {self.camera_status}

Samples: {self.samples}
"""


class GPSWidget(Static):
    """Display GPS info"""
    lat = reactive(0.0)
    lon = reactive(0.0)
    alt = reactive(0.0)
    
    def render(self) -> str:
        return f"""[bold]GPS Location[/bold]

Latitude:  {self.lat:>10.6f}°
Longitude: {self.lon:>10.6f}°
Altitude:  {self.alt:>10.1f} m
"""


class ROSBridge(Node):
    """Bridge between ROS and TUI"""
    def __init__(self, app):
        super().__init__('tui_bridge')
        self.app = app
        
        # Subscribers
        self.create_subscription(String, '/rx_router/data', self.router_callback, 10)
        self.create_subscription(NavSatFix, '/gps/fix', self.gps_callback, 10)
        self.create_subscription(CompressedImage, '/camera/image/compressed', self.camera_callback, 10)
        
        # Publisher for triggering collection
        self.trigger_pub = self.create_publisher(Empty, '/trigger_collection', 10)
        
        self.last_router = 0
        self.last_gps = 0
        self.last_camera = 0
        self.sample_count = 0
    
    def trigger_collection(self):
        """Trigger a discrete data collection"""
        msg = Empty()
        self.trigger_pub.publish(msg)
        self.get_logger().info('Collection triggered')
    
    def router_callback(self, msg):
        self.last_router = time.time()
        self.sample_count += 1
        self.app.call_from_thread(self.app.update_router)
        self.app.call_from_thread(self.app.log_message, f"Router data received ({len(msg.data)} bytes)")
    
    def gps_callback(self, msg):
        self.last_gps = time.time()
        self.app.call_from_thread(self.app.update_gps, msg.latitude, msg.longitude, msg.altitude)
        
    def camera_callback(self, msg):
        self.last_camera = time.time()
        self.app.call_from_thread(self.app.update_camera)


class CollectionTUI(App):
    """Data Collection TUI"""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-rows: 1fr 2fr;
    }
    
    #status {
        column-span: 1;
        border: solid green;
        padding: 1;
    }
    
    #gps {
        column-span: 1;
        border: solid blue;
        padding: 1;
    }
    
    #log {
        column-span: 2;
        border: solid yellow;
    }
    
    Footer {
        background: $primary;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "collect", "Collect Sample"),
        ("c", "clear_log", "Clear Log"),
    ]
    
    def __init__(self):
        super().__init__()
        self.ros_node = None
        self.ros_thread = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusWidget(id="status")
        yield GPSWidget(id="gps")
        yield Log(id="log", highlight=True)
        yield Footer()
    
    def on_mount(self):
        """Start ROS when TUI mounts"""
        self.log_message("Starting data collection system...")
        
        # Initialize ROS in separate thread
        rclpy.init()
        self.ros_node = ROSBridge(self)
        
        def spin_ros():
            rclpy.spin(self.ros_node)
        
        self.ros_thread = Thread(target=spin_ros, daemon=True)
        self.ros_thread.start()
        
        # Start status update timer
        self.set_interval(1.0, self.update_status)
        
        self.log_message("TUI started. Waiting for data...")
    
    def update_status(self):
        """Update status periodically"""
        now = time.time()
        status = self.query_one("#status", StatusWidget)
        
        # Check if we're receiving data
        if self.ros_node:
            router_ok = (now - self.ros_node.last_router) < 5 if self.ros_node.last_router > 0 else False
            gps_ok = (now - self.ros_node.last_gps) < 2 if self.ros_node.last_gps > 0 else False
            camera_ok = (now - self.ros_node.last_camera) < 5 if self.ros_node.last_camera > 0 else False
            
            status.router_status = "🟢 Connected" if router_ok else "🔴 Disconnected"
            status.gps_status = "🟢 GPS Fix" if gps_ok else "🔴 No Fix"
            status.camera_status = "🟢 Active" if camera_ok else "🔴 Inactive"
            status.samples = self.ros_node.sample_count
    
    def update_router(self):
        """Called when router data received"""
        pass  # Status updated by timer
    
    def update_gps(self, lat, lon, alt):
        """Update GPS display"""
        gps = self.query_one("#gps", GPSWidget)
        gps.lat = lat
        gps.lon = lon
        gps.alt = alt
    
    def update_camera(self):
        """Called when camera data received"""
        pass  # Status updated by timer
    
    def log_message(self, message: str):
        """Add message to log"""
        log = self.query_one("#log", Log)
        log.write_line(message)
    
    def action_clear_log(self):
        """Clear the log"""
        log = self.query_one("#log", Log)
        log.clear()
    
    def action_collect(self):
        """Trigger a discrete data collection"""
        if self.ros_node:
            self.ros_node.trigger_collection()
            self.log_message("[bold green]Collecting sample...[/bold green]")
    
    def on_unmount(self):
        """Cleanup ROS"""
        if self.ros_node:
            self.ros_node.destroy_node()
        rclpy.shutdown()


def main():
    app = CollectionTUI()
    app.run()


if __name__ == '__main__':
    main()

