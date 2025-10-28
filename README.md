# mmWave Data Collection System

Automated batch data collection from 60GHz router with synchronized GPS and camera data using ROS2.

## Features

- **Batch CSI Collection**: Collects 5 CSI measurements per batch from router via SSH
- **Time-Synchronized**: GPS and camera data matched with CSI batches
- **Auto-Detection**: Automatically finds GPS devices on Ubuntu/macOS
- **TUI Monitoring**: Terminal interface for real-time status
- **Cross-Platform**: Works on Ubuntu and macOS

## Quick Start

### 1. Install ROS2

**Ubuntu:**
```bash
sudo apt update
sudo apt install ros-jazzy-desktop python3-colcon-common-extensions
```

**macOS:**
```bash
brew install ros-jazzy-desktop
```

### 2. Install Dependencies

```bash
# System packages (Ubuntu)
sudo apt install python3-pip gpsd v4l-utils

# Python packages (both platforms)
pip3 install --user paramiko textual opencv-python pyyaml pyserial pynmea2
```

### 3. Configure

Edit `config/default_config.yaml` with your router credentials:
```yaml
rx_router:
  host: "192.168.1.101"      # Your router IP
  username: "root"
  key_file: "~/.ssh/id_ed25519"
  mac_address: "\\xf4\\x1e\\x57\\x64\\x92\\xae"  # Target device MAC
  measurements_per_batch: 5
  batch_interval: 1.0
```

### 4. Build and Run

```bash
# Source ROS2
source /opt/ros/jazzy/setup.bash

# Build
colcon build --symlink-install
source install/setup.bash

# Run
ros2 launch mmwave_collection collection.launch.py
```

## How It Works

1. **Router Node**: Every 1 second, collects 5 CSI measurements from router and publishes as a batch
2. **GPS Node**: Continuously publishes location data
3. **Camera Node**: Captures images every ~5 seconds
4. **Sync Node**: Matches batches with closest GPS/camera data within 2 second window

## Data Output

Data is saved to `data/YYYY-MM-DD/session_HHMMSS/`:

```
session_151552/
├── metadata.json           # Session info with GPS coordinates
├── rx_router_data/         # CSI measurement batches (JSON)
│   └── batch*.json
└── images/                 # Synchronized images
    └── *.jpg
```

Each `metadata.json` entry contains:
- Synchronized timestamp
- GPS coordinates (lat, lon, alt)
- Path to CSI batch file (5 measurements)
- Path to image

## Troubleshooting

**GPS not found:**
```bash
# Ubuntu: Check devices and add user to dialout group
ls /dev/ttyUSB* /dev/ttyACM*
sudo usermod -a -G dialout $USER
# Log out and back in

# macOS: Check USB devices
ls /dev/cu.* /dev/tty.*
```

**Camera not working:**
```bash
# Try different device IDs in config
device_id: 0  # or 1, 2
```

**SSH connection fails:**
```bash
# Test SSH connection manually
ssh -i ~/.ssh/id_ed25519 root@192.168.1.101

# If using password auth instead of key, update config:
auth_method: "password"
```

**Python version mismatch (TUI):**
```bash
# TUI requires system Python matching ROS2
conda deactivate  # Exit conda if using it
python3 tui/app.py
```

## Optional: Terminal UI

Monitor collection in real-time:

```bash
# Deactivate conda (if using)
conda deactivate

# Install textual with system Python
pip3 install --user textual

# Source ROS2 and workspace
source /opt/ros/jazzy/setup.bash
source install/setup.bash

# Run TUI (in separate terminal from launch)
python3 tui/app.py
```

The TUI shows:
- ✅ Status of each node (router, GPS, camera)
- 📍 Live GPS coordinates  
- 📊 Sample count
- 📝 Activity log

## Project Structure

```
├── config/                 # Configuration files
├── src/mmwave_collection/  # ROS2 package
│   ├── nodes/              # Router, GPS, Camera, Sync nodes
│   ├── utils/              # Router script utilities
│   └── launch/             # Launch file
├── tui/                    # Terminal UI (optional)
├── data/                   # Collected data (auto-created)
└── scripts/                # Helper scripts
```

## Platform Notes

See `PLATFORM_COMPATIBILITY.md` for macOS-specific setup details.

## License

MIT
