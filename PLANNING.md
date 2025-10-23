# mmWave Data Collection System - Planning Document

**Project:** Automated 60GHz Router Data Collection with GPS and Camera  
**Architecture:** ROS2 + Terminal User Interface (TUI)  
**Date:** October 22, 2025  
**Version:** 1.1 (Cross-Platform Update)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Specifications](#component-specifications)
4. [Data Flow](#data-flow)
5. [Technical Stack](#technical-stack)
6. [Platform Compatibility](#platform-compatibility)
7. [Project Structure](#project-structure)
8. [Implementation Phases](#implementation-phases)
9. [Configuration Strategy](#configuration-strategy)
10. [Data Management](#data-management)
11. [Testing Strategy](#testing-strategy)
12. [Security Considerations](#security-considerations)
13. [Performance Requirements](#performance-requirements)
14. [Risk Assessment](#risk-assessment)
15. [Timeline & Milestones](#timeline--milestones)
16. [Future Enhancements](#future-enhancements)

---

## 1. Executive Summary

### Project Goal
Create an automated data collection system that synchronously gathers:
- mmWave router data (via SSH/SCP from 60GHz router)
- GPS location data
- Webcam images

### Key Features
- **ROS2-based architecture** for robust sensor synchronization
- **Interactive TUI** for monitoring and control
- **Time-synchronized data streams** using ROS2 message filters
- **rosbag recording** for data replay and analysis
- **Modular design** for easy expansion to additional sensors

### Primary Use Case
Mobile data collection for mmWave network characterization, likely mounted on a vehicle or mobile platform.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Textual TUI Application                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  Status  │   GPS    │  Camera  │   Logs   │ Controls │  │
│  │  Panel   │  Panel   │  Preview │  Panel   │  Panel   │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ rclpy interface
                         │ (subscribe to topics, call services)
┌────────────────────────┴────────────────────────────────────┐
│                      ROS2 Network                            │
│                                                              │
│  Topics:                          Services:                 │
│  - /router/data                   - /collection/start       │
│  - /router/status                 - /collection/stop        │
│  - /gps/fix                       - /collection/status      │
│  - /camera/image_raw              - /router/trigger_command │
│  - /camera/image_compressed                                 │
│  - /system/diagnostics                                      │
└──────┬──────────┬──────────┬──────────┬─────────────────────┘
       │          │          │          │
┌──────▼─────┐ ┌─▼────┐ ┌───▼──────┐ ┌─▼─────────────────┐
│   Router   │ │ GPS  │ │  Camera  │ │   Data Sync &     │
│    Node    │ │ Node │ │   Node   │ │   Storage Node    │
└──────┬─────┘ └──┬───┘ └────┬─────┘ └─────────┬─────────┘
       │          │           │                 │
       │          │           │                 ▼
       │          │           │         ┌───────────────┐
       │          │           │         │  rosbag2      │
       │          │           │         │  recorder     │
       │          │           │         └───────────────┘
       │          │           │                 │
┌──────▼──────────▼───────────▼─────────────────▼─────────┐
│              Synchronized Data Storage                   │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  router_data/  │  │  gps_logs/   │  │  images/   │  │
│  └────────────────┘  └──────────────┘  └────────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │           metadata.json (session info)           │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Node Communication Diagram

```
Router Node ──┐
              ├──> [Message Filter] ──> Data Sync Node ──> Storage
GPS Node ────┤         (sync)                              + rosbag
              │
Camera Node ─┘

                    ┌──> TUI Status Updates
All Nodes ──────────┤
                    └──> Diagnostics Node ──> /diagnostics
```

---

## 3. Component Specifications

### 3.1 ROS2 Nodes

#### A. Router Node (`router_node.py`)

**Purpose:** SSH into router, execute commands, transfer data via SCP

**Responsibilities:**
- Maintain persistent SSH connection with reconnection logic
- Execute configurable commands on router
- Transfer data files via SCP
- Publish router data and status
- Handle network timeouts and failures

**Published Topics:**
- `/router/data` (custom_msgs/RouterData) - Raw router data
- `/router/status` (diagnostic_msgs/DiagnosticStatus) - Connection status

**Services Provided:**
- `/router/trigger_command` - Manually trigger data collection

**Parameters:**
- `router_host` (string) - Router IP address
- `router_port` (int, default: 22) - SSH port
- `username` (string) - SSH username
- `key_file` (string) - Path to SSH private key
- `command` (string) - Command to execute on router
- `remote_data_path` (string) - Path to data file on router
- `collection_interval` (float, default: 60.0) - Collection frequency in seconds
- `timeout` (float, default: 30.0) - Operation timeout

**Error Handling:**
- Retry on connection failure (exponential backoff)
- Publish error status to diagnostics
- Continue operation if single collection fails

#### B. GPS Node (`gps_node.py`)

**Purpose:** Interface with GPS hardware and publish location data

**Responsibilities:**
- Connect to GPS device (serial/USB)
- Parse NMEA sentences or use gpsd
- Validate GPS fix quality
- Publish NavSatFix messages with ROS timestamps

**Published Topics:**
- `/gps/fix` (sensor_msgs/NavSatFix) - GPS coordinates
- `/gps/status` (diagnostic_msgs/DiagnosticStatus) - GPS health

**Parameters:**
- `device` (string, default: "/dev/ttyUSB0") - GPS device path
- `baudrate` (int, default: 9600) - Serial baudrate
- `frame_id` (string, default: "gps") - TF frame ID
- `use_gpsd` (bool, default: true) - Use gpsd vs direct serial

**Alternative:** Use existing `nmea_navsat_driver` package

#### C. Camera Node (`camera_node.py`)

**Purpose:** Capture images from webcam

**Responsibilities:**
- Initialize webcam device
- Capture images at specified intervals or on trigger
- Publish compressed images to reduce bandwidth
- Add timestamps to image headers

**Published Topics:**
- `/camera/image_raw` (sensor_msgs/Image) - Raw images
- `/camera/image_compressed` (sensor_msgs/CompressedImage) - JPEG compressed
- `/camera/camera_info` (sensor_msgs/CameraInfo) - Camera calibration

**Parameters:**
- `device_id` (int, default: 0) - Camera device ID
- `width` (int, default: 1920) - Image width
- `height` (int, default: 1080) - Image height
- `fps` (int, default: 30) - Capture frame rate
- `jpeg_quality` (int, default: 85) - Compression quality

**Alternative:** Use existing `usb_cam` package

#### D. Data Sync Node (`data_sync_node.py`)

**Purpose:** Synchronize all data streams and manage storage

**Responsibilities:**
- Subscribe to all sensor topics
- Use message_filters for time synchronization
- Save synchronized data to disk
- Generate metadata for each collection point
- Manage storage space

**Subscribed Topics:**
- `/router/data`
- `/gps/fix`
- `/camera/image_compressed`

**Services Provided:**
- `/collection/start` - Start data collection
- `/collection/stop` - Stop collection
- `/collection/status` - Get collection statistics

**Parameters:**
- `sync_slop` (float, default: 0.5) - Time tolerance for sync (seconds)
- `queue_size` (int, default: 10) - Message queue size
- `storage_path` (string) - Base path for data storage
- `rosbag_enabled` (bool, default: true) - Enable rosbag recording

### 3.2 TUI Application

#### Main TUI (`tui/app.py`)

**Purpose:** Interactive terminal interface for monitoring and control

**Features:**
- Real-time status display (all sensors)
- Live GPS coordinates and visualization
- Collection statistics (samples, size, duration)
- Scrolling log viewer with severity filtering
- Keyboard controls for start/stop/pause
- Configuration editor
- Data directory browser

**Keyboard Shortcuts:**
- `S` - Start collection
- `P` - Pause/Resume
- `Q` - Quit (with confirmation)
- `C` - Open configuration
- `V` - View data directory
- `L` - Filter logs by level
- `R` - Reset statistics
- `H` - Help screen

**Widgets:**

1. **Status Panel** - Node health (connected/disconnected, errors)
2. **GPS Panel** - Live coordinates, speed, heading, satellite count
3. **Camera Panel** - Last image preview (ASCII art), resolution, fps
4. **Stats Panel** - Sample count, session duration, data size
5. **Logs Panel** - Scrollable log with color-coded severity
6. **Controls Panel** - Current mode, available actions

**ROS Bridge (`tui/ros_bridge.py`):**
- Separate ROS node for TUI
- Subscribes to status topics
- Calls services for control
- Thread-safe communication with TUI widgets

---

## 4. Data Flow

### 4.1 Collection Cycle

```
Time T:
  1. Router Node triggers (timer callback)
     - SSH to router
     - Execute command
     - SCP data file
     - Publish to /router/data with timestamp T

  2. GPS Node (continuous)
     - Publishes at 1Hz (or hardware rate)
     - Latest fix available at time ~T

  3. Camera Node (triggered or continuous)
     - Captures image
     - Publishes to /camera/image_compressed at time ~T

  4. Data Sync Node
     - ApproximateTimeSynchronizer receives all 3 messages
     - Messages within ±0.5s are considered synchronized
     - Callback triggered with synchronized data
     - Save all data with consistent timestamp
     - Update metadata.json

  5. TUI updates
     - Receives status messages
     - Updates display in real-time
```

### 4.2 Synchronization Strategy

**Method:** `message_filters.ApproximateTimeSynchronizer`

**Why:**
- Router data collection takes variable time (network latency)
- GPS and camera are fast operations
- Exact synchronization impossible with network operations
- Approximate sync with tolerance is practical

**Parameters:**
- `slop`: 0.5 seconds (configurable)
- All messages within 0.5s window are synchronized
- If messages arrive outside window, oldest are dropped

**Alternative Strategies:**
- **Best Effort:** Use latest GPS/camera when router data arrives (simpler, less accurate)
- **Trigger-based:** Router node triggers GPS/camera reading (more complex setup)

---

## 5. Technical Stack

### 5.1 Core Dependencies

| Component | Library/Package | Version | Purpose |
|-----------|----------------|---------|---------|
| ROS | ROS2 Humble/Iron | ≥ Humble | Core framework |
| Python | Python | ≥ 3.10 | Programming language |
| TUI | Textual | ≥ 0.40.0 | Terminal UI framework |
| SSH/SCP | Paramiko | ≥ 3.0 | SSH client |
| GPS | gpsd-py3 | ≥ 0.3.0 | GPS daemon interface |
| GPS (alt) | pyserial + pynmea2 | latest | Direct serial GPS |
| Camera | OpenCV | ≥ 4.8 | Video capture |
| Image | cv_bridge | ROS2 | OpenCV ↔ ROS conversion |

### 5.2 ROS2 Packages

**Standard Packages:**
- `rclpy` - Python client library
- `sensor_msgs` - Standard sensor messages
- `diagnostic_msgs` - Diagnostics messages
- `std_srvs` - Standard services
- `message_filters` - Time synchronization
- `cv_bridge` - Image conversion
- `rosbag2` - Data recording

**Optional Third-Party:**
- `nmea_navsat_driver` - GPS driver (if not custom)
- `usb_cam` - Camera driver (if not custom)
- `tf2` - Coordinate transforms (future expansion)

### 5.3 Development Tools

- `colcon` - ROS2 build system
- `pytest` - Unit testing
- `pytest-mock` - Mocking for tests
- `flake8` - Linting
- `black` - Code formatting
- `mypy` - Type checking

---

## 6. Platform Compatibility

### 6.1 Supported Platforms

✅ **Ubuntu 22.04 LTS / 24.04 LTS** (Primary, Recommended)  
✅ **macOS 12+ (Monterey and later)** - Intel & Apple Silicon

| Component | Ubuntu | macOS | Notes |
|-----------|--------|-------|-------|
| ROS2 Core | ✅ Native | ✅ Homebrew | Full support both platforms |
| Python 3.10+ | ✅ | ✅ | Identical functionality |
| SSH/SCP | ✅ | ✅ | Paramiko is fully cross-platform |
| TUI | ✅ | ✅ | Textual works identically |
| OpenCV | ✅ | ✅ | Auto-selects correct backend |
| GPS | ✅ | ⚠️ | Different device paths |
| rosbag2 | ✅ | ✅ | Full support |

### 6.2 Platform-Specific Considerations

#### GPS Devices

**Ubuntu:** `/dev/ttyUSB0`, `/dev/ttyACM0`  
**macOS:** `/dev/cu.usbserial-*`, `/dev/tty.usbserial-*`

**Solution:** Auto-detection in `platform_utils.py`

#### Camera Devices

**Ubuntu:** V4L2 (`/dev/video0`)  
**macOS:** AVFoundation (no device files)

**Solution:** OpenCV abstracts this automatically

#### Installation

**Ubuntu:**
```bash
sudo apt install ros-humble-desktop
```

**macOS:**
```bash
brew install ros-humble-desktop
```

### 6.3 Cross-Platform Features

- ✅ **Auto-detect GPS device** across platforms
- ✅ **Auto-detect camera** across platforms
- ✅ **Platform utilities** for device discovery
- ✅ **Unified configuration** with platform overrides
- ✅ **Path handling** via `pathlib.Path`

**See `PLATFORM_COMPATIBILITY.md` for detailed analysis and installation instructions.**

---

## 7. Project Structure

```
mmWave-data-collection/
├── README.md                          # Project overview
├── PLANNING.md                        # This document
├── PLATFORM_COMPATIBILITY.md          # Cross-platform guide
├── LICENSE
├── .gitignore
│
├── config/                            # Configuration files
│   ├── default_config.yaml            # Default parameters
│   ├── router_config.yaml             # Router-specific settings
│   └── dev_config.yaml                # Development/testing config
│
├── src/
│   └── mmwave_collection/             # ROS2 package
│       ├── __init__.py
│       ├── package.xml                # ROS2 package manifest
│       ├── setup.py                   # Python package setup
│       ├── setup.cfg
│       │
│       ├── mmwave_collection/         # Python package
│       │   ├── __init__.py
│       │   │
│       │   ├── nodes/                 # ROS2 nodes
│       │   │   ├── __init__.py
│       │   │   ├── router_node.py
│       │   │   ├── gps_node.py
│       │   │   ├── camera_node.py
│       │   │   └── data_sync_node.py
│       │   │
│       │   ├── core/                  # Core functionality
│       │   │   ├── __init__.py
│       │   │   ├── ssh_client.py      # SSH/SCP wrapper
│       │   │   ├── gps_interface.py   # GPS hardware interface
│       │   │   ├── camera_interface.py
│       │   │   └── storage_manager.py # File operations
│       │   │
│       │   └── utils/                 # Utilities
│       │       ├── __init__.py
│       │       ├── logger.py          # Logging configuration
│       │       ├── config_loader.py   # YAML config parser
│       │       ├── platform_utils.py  # Cross-platform helpers
│       │       └── validators.py      # Data validation
│       │
│       ├── resource/                  # ROS2 resource files
│       │   └── mmwave_collection
│       │
│       ├── launch/                    # Launch files
│       │   ├── collection.launch.py   # Main launch file
│       │   ├── nodes_only.launch.py   # Without TUI
│       │   └── simulation.launch.py   # Mock data for testing
│       │
│       ├── msg/                       # Custom message definitions
│       │   └── RouterData.msg
│       │
│       └── srv/                       # Custom service definitions
│           ├── TriggerCollection.srv
│           └── GetCollectionStatus.srv
│
├── tui/                               # TUI application (separate from ROS)
│   ├── __init__.py
│   ├── app.py                         # Main TUI application
│   ├── ros_bridge.py                  # ROS ↔ TUI communication
│   │
│   ├── widgets/                       # Custom widgets
│   │   ├── __init__.py
│   │   ├── status_panel.py
│   │   ├── gps_panel.py
│   │   ├── camera_panel.py
│   │   ├── stats_panel.py
│   │   ├── logs_panel.py
│   │   └── controls_panel.py
│   │
│   ├── styles/                        # TUI styling
│   │   └── main.css                   # Textual CSS
│   │
│   └── utils/
│       ├── __init__.py
│       └── formatting.py              # Display formatters
│
├── data/                              # Data storage (gitignored)
│   └── .gitkeep
│
├── logs/                              # Application logs (gitignored)
│   └── .gitkeep
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── conftest.py                    # Pytest configuration
│   │
│   ├── unit/                          # Unit tests
│   │   ├── test_router_node.py
│   │   ├── test_gps_node.py
│   │   ├── test_camera_node.py
│   │   ├── test_data_sync_node.py
│   │   └── test_storage_manager.py
│   │
│   ├── integration/                   # Integration tests
│   │   ├── test_full_pipeline.py
│   │   └── test_tui_integration.py
│   │
│   └── fixtures/                      # Test data
│       ├── mock_router_data.csv
│       ├── mock_gps_data.txt
│       └── test_image.jpg
│
├── scripts/                           # Utility scripts
│   ├── install_dependencies.sh        # System dependencies
│   ├── setup_workspace.sh             # Initial setup
│   ├── run_tui.sh                     # Launch TUI + nodes
│   └── analyze_rosbag.py              # Data analysis tools
│
├── docs/                              # Documentation
│   ├── INSTALLATION.md
│   ├── USAGE.md
│   ├── CONFIGURATION.md
│   ├── API.md
│   └── TROUBLESHOOTING.md
│
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Development dependencies
└── package.xml                        # Root package.xml (if needed)
```

---

## 7. Implementation Phases

### Phase 1: Project Setup & Infrastructure (Week 1)

**Goal:** Establish development environment and basic project structure

**Tasks:**
1. Create project directory structure
2. Initialize Git repository
3. Set up ROS2 workspace
4. Create package.xml and setup.py
5. Configure dependencies (requirements.txt)
6. Set up development tools (linting, formatting)
7. Create basic documentation structure
8. Set up logging infrastructure

**Deliverables:**
- ✓ Buildable ROS2 package (`colcon build` succeeds)
- ✓ Configuration loading system
- ✓ Logging framework
- ✓ README with setup instructions

**Testing:**
- Verify package builds without errors
- Test configuration loading
- Test logging output

---

### Phase 2: Core ROS2 Nodes (Weeks 2-3)

**Goal:** Implement individual ROS2 nodes with basic functionality

#### Phase 2A: Router Node (Week 2)

**Tasks:**
1. Implement SSH connection manager with Paramiko
2. Create SCP file transfer functionality
3. Implement router node with timer callback
4. Define custom RouterData message type
5. Add reconnection logic and error handling
6. Create mock router for testing (SSH server)

**Deliverables:**
- ✓ Functional router_node that can SSH and SCP
- ✓ Published /router/data and /router/status topics
- ✓ Unit tests with mocked SSH

**Testing:**
- Mock SSH server test
- Connection failure recovery test
- Data publication test

#### Phase 2B: GPS and Camera Nodes (Week 3)

**GPS Node Tasks:**
1. Implement GPS device interface (gpsd or pyserial)
2. Parse NMEA sentences
3. Publish sensor_msgs/NavSatFix
4. Add GPS fix quality validation
5. Implement diagnostic publishing

**Camera Node Tasks:**
1. Implement OpenCV camera interface
2. Publish sensor_msgs/Image and CompressedImage
3. Add cv_bridge integration
4. Handle camera disconnection

**Deliverables:**
- ✓ Functional gps_node publishing /gps/fix
- ✓ Functional camera_node publishing /camera/image_compressed
- ✓ Unit tests with mock devices

**Testing:**
- Mock GPS data playback
- Mock camera (test images)
- Message format validation

---

### Phase 3: Data Synchronization & Storage (Week 4)

**Goal:** Implement synchronized data collection and storage

**Tasks:**
1. Implement data_sync_node with message_filters
2. Create ApproximateTimeSynchronizer
3. Implement storage_manager for file operations
4. Create metadata generation logic
5. Implement rosbag2 recording integration
6. Add storage space monitoring
7. Create session management (start/stop/resume)

**Deliverables:**
- ✓ Functional data_sync_node
- ✓ Synchronized data storage
- ✓ Metadata JSON generation
- ✓ rosbag recording

**Testing:**
- Synchronization accuracy test
- Storage operations test
- Metadata validation test
- rosbag replay test

---

### Phase 4: TUI Development (Week 5)

**Goal:** Create interactive terminal interface

**Tasks:**
1. Set up Textual application structure
2. Implement ROS bridge node for TUI
3. Create status panel widget
4. Create GPS panel widget
5. Create statistics panel widget
6. Create logs panel widget
7. Create controls panel widget
8. Implement keyboard shortcuts
9. Add CSS styling

**Deliverables:**
- ✓ Functional TUI displaying all data
- ✓ Keyboard controls working
- ✓ Real-time updates from ROS
- ✓ Professional appearance

**Testing:**
- Widget rendering test
- ROS communication test
- User interaction test
- Layout responsiveness test

---

### Phase 5: Integration & Launch Files (Week 6)

**Goal:** Integrate all components and create launch system

**Tasks:**
1. Create main launch file (collection.launch.py)
2. Implement service-based control
3. Add parameter configuration to launch
4. Create startup/shutdown sequences
5. Implement graceful error handling
6. Add diagnostic aggregator
7. Create helper scripts (run_tui.sh)

**Deliverables:**
- ✓ Single-command launch system
- ✓ TUI + all nodes working together
- ✓ Service-based control functional
- ✓ Clean startup and shutdown

**Testing:**
- Full system integration test
- Launch file parameter test
- Service call test
- Shutdown behavior test

---

### Phase 6: Testing & Documentation (Week 7)

**Goal:** Comprehensive testing and documentation

**Tasks:**
1. Write integration tests
2. Perform stress testing (long-duration runs)
3. Test error scenarios (disconnections, failures)
4. Write user documentation (USAGE.md)
5. Write configuration guide (CONFIGURATION.md)
6. Create troubleshooting guide
7. Add code documentation (docstrings)
8. Create example configurations

**Deliverables:**
- ✓ Test coverage > 80%
- ✓ Complete user documentation
- ✓ Troubleshooting guide
- ✓ Example configurations

**Testing:**
- 24-hour stress test
- Network failure scenarios
- Device disconnection scenarios
- Storage full scenarios

---

### Phase 7: Optimization & Polish (Week 8)

**Goal:** Performance optimization and final polish

**Tasks:**
1. Profile performance bottlenecks
2. Optimize data storage (compression, formats)
3. Tune synchronization parameters
4. Improve TUI responsiveness
5. Add any remaining features
6. Fix bugs from testing
7. Prepare for deployment

**Deliverables:**
- ✓ Optimized performance
- ✓ Polished user experience
- ✓ Bug-free operation
- ✓ Deployment-ready system

---

## 8. Configuration Strategy

### 8.1 Configuration Files

**config/default_config.yaml:**
```yaml
# System Configuration
system:
  session_name: "mmwave_collection"
  log_level: "INFO"  # DEBUG, INFO, WARN, ERROR
  data_base_path: "./data"
  organize_by: "date"  # date, session, custom

# Router Configuration
router:
  host: "192.168.1.1"
  port: 22
  username: "admin"
  auth_method: "key"  # key or password
  key_file: "~/.ssh/id_rsa"
  password: null  # Only if auth_method is password
  
  commands:
    pre_collection: null  # Optional command before collection
    collection: "cat /proc/net/mmwave_stats"
    post_collection: null  # Optional cleanup command
  
  data_file:
    remote_path: "/tmp/mmwave_data.csv"
    local_prefix: "router_data"
    format: "csv"
  
  timing:
    collection_interval: 60.0  # seconds
    timeout: 30.0
    retry_attempts: 3
    retry_delay: 5.0

# GPS Configuration
gps:
  enabled: true
  interface: "gpsd"  # gpsd or serial
  
  # For gpsd
  gpsd_host: "localhost"
  gpsd_port: 2947
  
  # For serial
  device: "/dev/ttyUSB0"
  baudrate: 9600
  
  # General
  min_fix_quality: 1  # 0=invalid, 1=GPS, 2=DGPS
  frame_id: "gps"
  
# Camera Configuration
camera:
  enabled: true
  device_id: 0  # 0 for /dev/video0, 1 for /dev/video1, etc.
  
  resolution:
    width: 1920
    height: 1080
  
  capture:
    fps: 30
    format: "MJPEG"  # MJPEG, YUYV
  
  compression:
    enabled: true
    quality: 85  # JPEG quality 1-100
  
  frame_id: "camera"

# Data Synchronization
synchronization:
  method: "approximate"  # approximate or exact
  slop: 0.5  # seconds (for approximate)
  queue_size: 10
  drop_incomplete: true  # Drop if not all sensors available

# Storage Configuration
storage:
  rosbag:
    enabled: true
    compression: "zstd"  # none, zstd, lz4
    split_size: 1024  # MB per bag file
  
  raw_files:
    save_router_data: true
    save_images: true
    image_format: "jpg"
  
  metadata:
    format: "json"
    include_system_info: true
  
  cleanup:
    auto_cleanup: false
    keep_days: 30
    min_free_space_gb: 10

# TUI Configuration
tui:
  refresh_rate: 10  # Hz
  theme: "default"  # default, dark, light
  panels:
    show_camera_preview: true
    log_buffer_lines: 100
  
# Diagnostics
diagnostics:
  enabled: true
  publish_rate: 1.0  # Hz
  thresholds:
    gps_satellites_warn: 6
    gps_satellites_error: 4
    storage_warn_gb: 20
    storage_error_gb: 5
```

### 8.2 ROS Parameters

Parameters can be overridden via:
1. YAML config file (loaded in launch file)
2. Command-line arguments
3. ROS parameter server (runtime)

**Example launch with custom config:**
```bash
ros2 launch mmwave_collection collection.launch.py config:=/path/to/custom_config.yaml
```

---

## 9. Data Management

### 9.1 Directory Structure

```
data/
└── 2025-10-22/                    # Date-based organization
    └── session_143052/            # Session with timestamp
        ├── metadata.json          # Session metadata
        ├── rosbags/               # ROS bag files
        │   ├── rosbag2_0.db3
        │   └── metadata.yaml
        ├── router_data/           # Raw router data
        │   ├── 143052_router.csv
        │   ├── 143112_router.csv
        │   └── ...
        ├── images/                # Camera images
        │   ├── 143052_camera.jpg
        │   ├── 143112_camera.jpg
        │   └── ...
        └── gps_track.csv          # Compiled GPS track
```

### 9.2 Metadata Format

**metadata.json:**
```json
{
  "session": {
    "id": "2025-10-22_143052",
    "start_time": "2025-10-22T14:30:52.123Z",
    "end_time": "2025-10-22T16:45:32.456Z",
    "duration_seconds": 8080.333,
    "status": "completed"
  },
  "system": {
    "hostname": "data-collection-laptop",
    "ros_distro": "humble",
    "python_version": "3.10.12",
    "os": "Ubuntu 22.04"
  },
  "configuration": {
    "router_host": "192.168.1.1",
    "collection_interval": 60.0,
    "sync_slop": 0.5
  },
  "statistics": {
    "total_samples": 135,
    "successful_samples": 133,
    "failed_samples": 2,
    "total_size_mb": 1250.5
  },
  "data_points": [
    {
      "index": 0,
      "timestamp": "2025-10-22T14:30:52.123Z",
      "gps": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "altitude": 10.5,
        "fix_quality": 2,
        "satellites": 12
      },
      "files": {
        "router_data": "router_data/143052_router.csv",
        "image": "images/143052_camera.jpg"
      },
      "status": "success"
    }
  ],
  "errors": [
    {
      "timestamp": "2025-10-22T15:15:30.000Z",
      "component": "router",
      "error": "SSH connection timeout",
      "severity": "ERROR"
    }
  ]
}
```

### 9.3 GPS Track Format

**gps_track.csv:**
```csv
timestamp,latitude,longitude,altitude,speed,heading,fix_quality,satellites
2025-10-22T14:30:52.123Z,37.7749,-122.4194,10.5,5.2,45.0,2,12
2025-10-22T14:31:52.456Z,37.7750,-122.4195,10.6,5.3,46.0,2,12
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Test Coverage Goals:**
- Core functionality: 90%
- ROS nodes: 80%
- TUI components: 70%
- Overall: 80%

**Key Test Areas:**
1. SSH/SCP operations with mock server
2. GPS parsing with synthetic NMEA data
3. Camera capture with mock device
4. Message synchronization logic
5. Storage operations
6. Configuration loading and validation

**Test Framework:**
```python
# Example test structure
tests/
├── unit/
│   ├── test_ssh_client.py
│   ├── test_gps_interface.py
│   ├── test_camera_interface.py
│   ├── test_storage_manager.py
│   └── test_config_loader.py
```

### 10.2 Integration Tests

**Test Scenarios:**
1. **Full Pipeline:** Mock all sensors → verify synchronized data storage
2. **ROS Communication:** Node-to-node message passing
3. **TUI Integration:** TUI controls → ROS service calls → node response
4. **rosbag Playback:** Record → playback → verify data integrity

### 10.3 System Tests

**Long-Duration Tests:**
- 24-hour continuous operation
- Monitor memory leaks
- Verify data consistency
- Check log file rotation

**Failure Scenarios:**
- Router SSH connection drops
- GPS device disconnected
- Camera unplugged
- Disk full
- Network interruption
- Process kill and restart

**Performance Tests:**
- High-frequency collection (1Hz, 10Hz)
- Large data files (> 100MB per collection)
- Limited bandwidth scenarios
- Low disk space scenarios

### 10.4 Mock Data

**Create Mock Devices:**
1. **Mock SSH Server:** Simple Python SSH server for testing
2. **Mock GPS Device:** Replay NMEA log file
3. **Mock Camera:** Serve test images
4. **Simulation Launch File:** Launch all mocks for development

---

## 11. Security Considerations

### 11.1 SSH Authentication

**Recommendations:**
- ✓ Use SSH key authentication (not passwords)
- ✓ Store private keys with proper permissions (600)
- ✓ Never commit keys to version control
- ✓ Support encrypted private keys
- ✓ Implement connection timeout limits

### 11.2 Configuration Security

**Sensitive Data Handling:**
- Store passwords/keys outside main config
- Use environment variables for secrets
- Provide `secrets.yaml` template (not tracked in git)
- Support loading from secure vaults (future)

**Example:**
```yaml
# config.yaml
router:
  username: "admin"
  key_file: "${SSH_KEY_PATH}"  # Load from environment

# .env (not committed)
SSH_KEY_PATH=/home/user/.ssh/mmwave_key
```

### 11.3 File Permissions

- Configuration files: 644
- SSH keys: 600
- Data directory: 755
- Log files: 644

### 11.4 Network Security

- Validate router hostname/IP
- Use known_hosts verification
- Implement rate limiting
- Log all SSH operations
- Support VPN/tunneled connections

---

## 12. Performance Requirements

### 12.1 Timing Requirements

| Operation | Target | Maximum | Notes |
|-----------|--------|---------|-------|
| SSH Connection | < 2s | 5s | Initial connection |
| Router Command Exec | < 5s | 15s | Depends on command |
| SCP Transfer | < 10s | 30s | Depends on file size |
| GPS Reading | < 100ms | 500ms | Near-instantaneous |
| Camera Capture | < 100ms | 500ms | Single frame |
| Data Synchronization | < 50ms | 200ms | Processing delay |
| TUI Refresh | 100ms | 200ms | 10Hz update rate |

### 12.2 Resource Requirements

**Minimum System:**
- CPU: 2 cores, 2.0 GHz
- RAM: 4 GB
- Storage: 50 GB free (for data)
- Network: 10 Mbps

**Recommended System:**
- CPU: 4 cores, 2.5 GHz
- RAM: 8 GB
- Storage: 500 GB SSD
- Network: 100 Mbps

### 12.3 Scalability

**Collection Frequency:**
- Tested: 1 sample/minute (baseline)
- Supported: Up to 1 sample/second
- Limitation: Router SSH/SCP latency

**Data Volume:**
- Typical: 100 MB/hour
- Maximum tested: 1 GB/hour
- Storage monitoring: Alert at 10GB free

### 12.4 Reliability Targets

- Uptime: 99% (excluding planned maintenance)
- Data loss rate: < 1% of samples
- Mean Time Between Failures: > 24 hours
- Recovery time: < 1 minute (auto-reconnect)

---

## 13. Risk Assessment

### 13.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Router SSH timeout | High | Medium | Retry logic, timeout config |
| GPS signal loss | Medium | Low | Buffer last known position |
| Camera failure | Low | Low | Continue without images |
| Disk full | Medium | High | Monitor space, auto-cleanup |
| Network interruption | High | Medium | Offline buffering (future) |
| ROS node crash | Low | High | Node restart policies |
| Time sync failure | Medium | High | Configurable slop, logging |
| Data corruption | Low | High | Checksums, validation |

### 13.2 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Incorrect configuration | Medium | High | Validation, examples |
| User error | Medium | Medium | Clear UI, confirmations |
| Insufficient storage | Medium | High | Pre-flight checks, alerts |
| Router access denied | Low | High | Test connection at startup |
| GPS device not found | Medium | Medium | Graceful degradation |
| Wrong permissions | Low | Medium | Setup script, docs |

### 13.3 Mitigation Strategies

1. **Comprehensive Error Handling:** Try-catch all operations, never crash
2. **Graceful Degradation:** Continue with partial data if possible
3. **Pre-flight Checks:** Validate all connections before starting
4. **Monitoring:** Real-time diagnostics via TUI and /diagnostics topic
5. **Logging:** Detailed logs for troubleshooting
6. **Documentation:** Clear usage and troubleshooting guides
7. **Testing:** Extensive failure scenario testing

---

## 14. Timeline & Milestones

### Overall Timeline: 8 Weeks

```
Week 1: [████████] Setup & Infrastructure
Week 2: [████████] Router Node
Week 3: [████████] GPS & Camera Nodes
Week 4: [████████] Data Sync & Storage
Week 5: [████████] TUI Development
Week 6: [████████] Integration & Launch
Week 7: [████████] Testing & Docs
Week 8: [████████] Optimization & Polish
```

### Key Milestones

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1 | Infrastructure Complete | Buildable package, config system |
| 2 | Router Node Working | SSH/SCP functional, data publishing |
| 3 | All Nodes Implemented | GPS, Camera, Router all publishing |
| 4 | Synchronized Collection | Data sync node, storage working |
| 5 | TUI Functional | Interactive interface complete |
| 6 | System Integrated | Single launch, all components working |
| 7 | Testing Complete | Test coverage > 80%, docs written |
| 8 | Production Ready | Optimized, polished, deployable |

### Go/No-Go Decision Points

**Week 3 Review:**
- ✓ All individual nodes publishing data?
- ✓ Tests passing?
- ✓ No major architectural issues?

**Week 6 Review:**
- ✓ Full system integration working?
- ✓ TUI responsive and usable?
- ✓ Data storage verified?

---

## 15. Future Enhancements

### Phase 2 Features (Post-MVP)

1. **Multi-Router Support**
   - Collect from multiple routers simultaneously
   - Aggregate data with spatial correlation

2. **Advanced GPS Features**
   - IMU integration (sensor fusion)
   - Coordinate transformation (UTM, local frames)
   - Path planning and waypoint navigation

3. **Enhanced Camera**
   - Multiple cameras
   - Video recording (not just stills)
   - Object detection integration

4. **Data Analysis Tools**
   - Real-time visualization
   - Post-processing scripts
   - Statistical analysis
   - Export to common formats (CSV, HDF5)

5. **Remote Monitoring**
   - Web dashboard
   - REST API
   - Email/SMS alerts
   - Cloud upload (S3, GCS)

6. **Automation**
   - Scheduled collections
   - Event-triggered collection
   - Conditional collection (speed, location)

7. **Advanced Synchronization**
   - Hardware timestamping
   - PTP (Precision Time Protocol)
   - External trigger support

8. **Quality of Service**
   - ROS2 QoS profiles for reliability
   - Message priority
   - Bandwidth management

9. **Calibration Tools**
   - Camera calibration
   - GPS/IMU calibration
   - Time offset calibration

10. **Mobile App**
    - Android/iOS companion app
    - Remote control
    - Live preview

### Integration Opportunities

- **SLAM Systems:** Integrate with RTAB-Map or Cartographer
- **LiDAR:** Add point cloud collection
- **Signal Analysis:** Real-time mmWave signal processing
- **Machine Learning:** Anomaly detection, prediction
- **GIS Integration:** Export to QGIS, ArcGIS

---

## Appendix A: Message Definitions

### RouterData.msg
```
std_msgs/Header header
string data_type          # csv, json, binary
uint64 data_size          # bytes
string local_file_path    # where data was saved
uint8 collection_status   # 0=success, 1=partial, 2=failed
string error_message      # if failed
```

### GetCollectionStatus.srv
```
# Request
---
# Response
bool is_collecting
uint64 session_start_time
uint32 total_samples
uint32 successful_samples
uint32 failed_samples
float64 data_size_mb
```

---

## Appendix B: Command Reference

### Build & Run Commands

```bash
# Build ROS2 workspace
cd ~/mmWave-data-collection
colcon build --symlink-install

# Source workspace
source install/setup.bash

# Launch full system (with TUI)
./scripts/run_tui.sh

# Launch nodes only (no TUI)
ros2 launch mmwave_collection collection.launch.py

# Launch with custom config
ros2 launch mmwave_collection collection.launch.py \
  config:=config/my_config.yaml

# Run TUI separately
python3 tui/app.py

# View topics
ros2 topic list
ros2 topic echo /gps/fix
ros2 topic echo /router/status

# Call services
ros2 service call /collection/start std_srvs/srv/Trigger
ros2 service call /collection/stop std_srvs/srv/Trigger

# Play back rosbag
ros2 bag play data/2025-10-22/session_143052/rosbags/

# Run tests
colcon test
colcon test-result --verbose
```

### Development Commands

```bash
# Format code
black src/ tui/ tests/

# Lint
flake8 src/ tui/ tests/

# Type check
mypy src/ tui/

# Run specific test
pytest tests/unit/test_router_node.py -v

# Coverage report
pytest --cov=mmwave_collection tests/
```

---

## Appendix C: Troubleshooting Quick Reference

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| "No module named 'mmwave_collection'" | Workspace not sourced | `source install/setup.bash` |
| Router node timeout | Network issue, wrong IP | Check router config, ping router |
| GPS not publishing | Device not found | Check `ls /dev/ttyUSB*`, verify device path |
| Camera not found | Wrong device ID | Try device_id: 0, 1, 2; check `v4l2-ctl --list-devices` |
| TUI not updating | ROS bridge error | Check ROS node running: `ros2 node list` |
| Sync node no output | Messages not aligned | Increase sync_slop parameter |
| Disk full errors | Insufficient space | Increase storage, enable auto-cleanup |
| SSH authentication failed | Wrong key/password | Verify credentials, test manual SSH |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-22 | AI Assistant | Initial planning document |

---

**END OF PLANNING DOCUMENT**

