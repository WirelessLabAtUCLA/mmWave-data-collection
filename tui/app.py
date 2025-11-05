#!/usr/bin/env python3
"""Enhanced TUI for monitoring data collection"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log, Input, Button
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual import work
from textual.reactive import reactive
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
from sensor_msgs.msg import NavSatFix, CompressedImage
from rcl_interfaces.msg import Log as RosLog
from threading import Thread
import time


class StatusWidget(Static):
    """Display system status"""
    router_status = reactive("⚪ Checking...")
    gps_status = reactive("⚪ Checking...")
    camera_status = reactive("⚪ Checking...")
    samples = reactive(0)
    router_ready = reactive(False)
    camera_ready = reactive(False)
    gps_ready = reactive(False)
    
    def render(self) -> str:
        # Overall system ready status
        required_ready = self.router_ready and self.camera_ready
        optional_status = " (optional)" if not self.gps_ready else ""
        
        status_color = "green" if required_ready else "yellow"
        ready_text = "READY" if required_ready else "NOT READY"
        
        return f"""[bold]System Status[/bold]
        
[bold {status_color}]{ready_text}[/bold {status_color}]

Router:  {self.router_status}
GPS:     {self.gps_status}{optional_status}
Camera:  {self.camera_status}

Samples collected: {self.samples}
"""


class GPSWidget(Static):
    """Display GPS info"""
    lat = reactive(0.0)
    lon = reactive(0.0)
    alt = reactive(0.0)
    has_fix = reactive(False)
    
    def render(self) -> str:
        if not self.has_fix:
            return """[bold]GPS Location[/bold]

[dim]Waiting for GPS fix...[/dim]
"""
        return f"""[bold]GPS Location[/bold]

Latitude:  {self.lat:>10.6f}°
Longitude: {self.lon:>10.6f}°
Altitude:  {self.alt:>10.1f} m
"""


class CommandPanel(Static):
    """Panel for command input"""
    
    def compose(self) -> ComposeResult:
        yield Static("[bold]Quick Actions[/bold]", classes="panel-title")
        yield Button("🔄 Reconnect All", id="reconnect", variant="primary")
        yield Button("📷 Collect Sample", id="collect", variant="success")
        yield Button("🗑️  Clear Logs", id="clear", variant="default")


class ROSBridge(Node):
    """Bridge between ROS and TUI"""
    def __init__(self, app):
        super().__init__('tui_bridge')
        self.app = app
        
        # Subscribers
        self.router_sub = self.create_subscription(
            String, '/rx_router/data', self.router_callback, 10)
        self.gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self.gps_callback, 10)
        self.camera_sub = self.create_subscription(
            CompressedImage, '/camera/image/compressed', self.camera_callback, 10)
        self.rosout_sub = self.create_subscription(
            RosLog, '/rosout', self.rosout_callback, 50)
        
        # Publisher for triggering collection
        self.trigger_pub = self.create_publisher(Empty, '/trigger_collection', 10)
        
        self.last_router = 0
        self.last_gps = 0
        self.last_camera = 0
        self.sample_count = 0
        
        # Track first messages to determine node availability
        self.router_ever_seen = False
        self.camera_ever_seen = False
        self.gps_ever_seen = False
        
    def check_nodes_exist(self):
        """Check if required ROS nodes are running"""
        node_names = self.get_node_names()
        
        router_exists = any('router_node' in name for name in node_names)
        camera_exists = any('camera_node' in name for name in node_names)
        gps_exists = any('gps_node' in name for name in node_names)
        
        return router_exists, camera_exists, gps_exists
    
    def trigger_collection(self):
        """Trigger a discrete data collection"""
        msg = Empty()
        self.trigger_pub.publish(msg)
        self.get_logger().info('Collection triggered via TUI')
    
    def router_callback(self, msg):
        if not self.router_ever_seen:
            self.router_ever_seen = True
            self.app.call_from_thread(self.app.mark_router_ready)
        
        self.last_router = time.time()
        self.sample_count += 1
        self.app.call_from_thread(self.app.update_router)
    
    def gps_callback(self, msg):
        if not self.gps_ever_seen:
            self.gps_ever_seen = True
            self.app.call_from_thread(self.app.mark_gps_ready)
        
        self.last_gps = time.time()
        self.app.call_from_thread(self.app.update_gps, msg.latitude, msg.longitude, msg.altitude)
        
    def camera_callback(self, msg):
        if not self.camera_ever_seen:
            self.camera_ever_seen = True
            self.app.call_from_thread(self.app.mark_camera_ready)
        
        self.last_camera = time.time()
        self.app.call_from_thread(self.app.update_camera)
    
    def rosout_callback(self, msg):
        """Handle rosout messages"""
        # Filter out messages from this node to avoid recursion
        if msg.name == 'tui_bridge':
            return
        
        # Map log levels to colors
        level_map = {
            10: ('DEBUG', 'blue'),      # DEBUG
            20: ('INFO', 'green'),       # INFO
            30: ('WARN', 'yellow'),      # WARN
            40: ('ERROR', 'red'),        # ERROR
            50: ('FATAL', 'magenta'),    # FATAL
        }
        
        level_str, color = level_map.get(msg.level, ('INFO', 'white'))
        timestamp = time.strftime('%H:%M:%S', time.localtime(msg.stamp.sec))
        
        log_line = f"[{timestamp}] [{color}]{level_str:5}[/{color}] [{msg.name}] {msg.msg}"
        self.app.call_from_thread(self.app.log_rosout, log_line)


class CollectionTUI(App):
    """Data Collection TUI"""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-rows: 1fr 1fr 1fr;
    }
    
    #status {
        column-span: 1;
        row-span: 1;
        border: solid green;
        padding: 1;
        height: 100%;
    }
    
    #gps {
        column-span: 1;
        row-span: 1;
        border: solid blue;
        padding: 1;
        height: 100%;
    }
    
    #commands {
        column-span: 1;
        row-span: 1;
        border: solid cyan;
        padding: 1;
        height: 100%;
    }
    
    #event_log {
        column-span: 3;
        row-span: 1;
        border: solid yellow;
        height: 100%;
    }
    
    #rosout_log {
        column-span: 3;
        row-span: 1;
        border: solid magenta;
        height: 100%;
    }
    
    .panel-title {
        margin-bottom: 1;
    }
    
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    
    Footer {
        background: $primary;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "collect", "Collect"),
        ("r", "reconnect", "Reconnect"),
        ("c", "clear_logs", "Clear"),
    ]
    
    def __init__(self):
        super().__init__()
        self.ros_node = None
        self.ros_thread = None
        self.connection_check_count = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # Left column: Status
        with Container(id="status"):
            yield StatusWidget()
        
        # Middle column: GPS
        with Container(id="gps"):
            yield GPSWidget()
        
        # Right column: Commands
        with Container(id="commands"):
            yield CommandPanel()
        
        # Bottom row: Event log
        with Container(id="event_log"):
            yield Static("[bold]Events[/bold]", classes="panel-title")
            yield Log(id="events", highlight=True)
        
        # Bottom row: ROS output
        with Container(id="rosout_log"):
            yield Static("[bold]ROS Output[/bold]", classes="panel-title")
            yield Log(id="rosout", highlight=True)
        
        yield Footer()
    
    def on_mount(self):
        """Start ROS when TUI mounts"""
        self.log_event("🚀 Starting data collection TUI...")
        
        # Initialize ROS in separate thread
        try:
            rclpy.init()
            self.ros_node = ROSBridge(self)
            
            def spin_ros():
                rclpy.spin(self.ros_node)
            
            self.ros_thread = Thread(target=spin_ros, daemon=True)
            self.ros_thread.start()
            
            self.log_event("✓ ROS bridge initialized")
        except Exception as e:
            self.log_event(f"❌ Failed to initialize ROS: {e}")
            return
        
        # Start status update timer
        self.set_interval(1.0, self.update_status)
        self.set_interval(2.0, self.check_connections)
        
        self.log_event("⏳ Checking for data sources...")
    
    def check_connections(self):
        """Periodically check if nodes exist"""
        self.connection_check_count += 1
        
        if not self.ros_node:
            return
        
        # Check if nodes exist in ROS graph
        router_exists, camera_exists, gps_exists = self.ros_node.check_nodes_exist()
        
        status = self.query_one(StatusWidget)
        
        # Mark nodes as ready if they exist (important for discrete mode)
        if router_exists and not status.router_ready:
            status.router_ready = True
            self.log_event("✓ Router node detected!")
        
        if camera_exists and not status.camera_ready:
            status.camera_ready = True
            self.log_event("✓ Camera node detected!")
        
        if gps_exists and not status.gps_ready:
            status.gps_ready = True
            self.log_event("✓ GPS node detected!")
        
        # After 6 seconds, if we still haven't seen nodes, warn the user
        if self.connection_check_count == 3:
            if not status.router_ready:
                self.log_event("⚠️  Router node not found. Is the launch file running?")
            if not status.camera_ready:
                self.log_event("⚠️  Camera node not found. Check if camera node is running.")
            if not status.gps_ready:
                self.log_event("ℹ️  GPS node not found (optional).")
    
    def update_status(self):
        """Update status periodically"""
        now = time.time()
        status = self.query_one(StatusWidget)
        
        # Check if we're receiving data
        if self.ros_node:
            router_receiving = (now - self.ros_node.last_router) < 3 if self.ros_node.last_router > 0 else False
            gps_receiving = (now - self.ros_node.last_gps) < 2 if self.ros_node.last_gps > 0 else False
            camera_receiving = (now - self.ros_node.last_camera) < 3 if self.ros_node.last_camera > 0 else False
            
            # Update status strings
            # For router: show ready if node exists, or active if receiving data
            if status.router_ready:
                if router_receiving:
                    status.router_status = "🟢 Active"
                else:
                    status.router_status = "🟢 Ready"
            else:
                status.router_status = "🔴 Not detected"
            
            # For GPS: show fix status if receiving
            if status.gps_ready:
                if gps_receiving:
                    status.gps_status = "🟢 GPS Fix"
                else:
                    status.gps_status = "🟢 Ready"
            else:
                status.gps_status = "🔴 Not detected"
            
            # For camera: show ready if node exists, or active if receiving
            if status.camera_ready:
                if camera_receiving:
                    status.camera_status = "🟢 Active"
                else:
                    status.camera_status = "🟢 Ready"
            else:
                status.camera_status = "🔴 Not detected"
            
            status.samples = self.ros_node.sample_count
    
    def mark_router_ready(self):
        """Mark router as ready"""
        status = self.query_one(StatusWidget)
        status.router_ready = True
        self.log_event("✓ Router connected!")
    
    def mark_gps_ready(self):
        """Mark GPS as ready"""
        status = self.query_one(StatusWidget)
        status.gps_ready = True
        self.log_event("✓ GPS connected!")
    
    def mark_camera_ready(self):
        """Mark camera as ready"""
        status = self.query_one(StatusWidget)
        status.camera_ready = True
        self.log_event("✓ Camera connected!")
    
    def update_router(self):
        """Called when router data received"""
        pass  # Status updated by timer
    
    def update_gps(self, lat, lon, alt):
        """Update GPS display"""
        gps = self.query_one(GPSWidget)
        gps.lat = lat
        gps.lon = lon
        gps.alt = alt
        gps.has_fix = True
    
    def update_camera(self):
        """Called when camera data received"""
        pass  # Status updated by timer
    
    def log_event(self, message: str):
        """Add message to event log"""
        log = self.query_one("#events", Log)
        log.write_line(message)
    
    def log_rosout(self, message: str):
        """Add message to rosout log"""
        log = self.query_one("#rosout", Log)
        log.write_line(message)
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses"""
        if event.button.id == "collect":
            self.action_collect()
        elif event.button.id == "clear":
            self.action_clear_logs()
        elif event.button.id == "reconnect":
            self.action_reconnect()
    
    def action_clear_logs(self):
        """Clear both logs"""
        event_log = self.query_one("#events", Log)
        rosout_log = self.query_one("#rosout", Log)
        event_log.clear()
        rosout_log.clear()
        self.log_event("🗑️  Logs cleared")
    
    def action_collect(self):
        """Trigger a discrete data collection"""
        if self.ros_node:
            status = self.query_one(StatusWidget)
            if not (status.router_ready and status.camera_ready):
                self.log_event("⚠️  Cannot collect: Required systems not ready")
                return
            
            self.ros_node.trigger_collection()
            self.log_event("✓ Collecting sample...")
    
    def action_reconnect(self):
        """Re-verify all systems"""
        self.log_event("🔄 Rechecking connections...")
        if self.ros_node:
            # Check node existence immediately
            router_exists, camera_exists, gps_exists = self.ros_node.check_nodes_exist()
            
            status = self.query_one(StatusWidget)
            
            # Update status
            status.router_ready = router_exists
            status.camera_ready = camera_exists
            status.gps_ready = gps_exists
            
            if router_exists:
                self.log_event("✓ Router node found")
            else:
                self.log_event("❌ Router node not found")
            
            if camera_exists:
                self.log_event("✓ Camera node found")
            else:
                self.log_event("❌ Camera node not found")
            
            if gps_exists:
                self.log_event("✓ GPS node found")
            else:
                self.log_event("ℹ️  GPS node not found (optional)")
        
        self.connection_check_count = 0
    
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
