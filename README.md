# mmWave Data Collection System

Automated batch data collection from 60GHz router with synchronized GPS and camera data using ROS2.

## Features

- **Dual-Mode Collection**: Collect both CSI (AoA) and FTM (ToF) measurements simultaneously or separately
- **Batch CSI Collection**: Collects 5 CSI measurements per batch from router via SSH
- **FTM ToF Collection**: Fine Timing Measurement for Time-of-Flight distance estimation
- **Discrete & Continuous Modes**: Manual trigger-based or automatic continuous collection
- **Time-Synchronized**: GPS and camera data matched with CSI/FTM batches
- **Auto-Detection**: Automatically finds GPS devices on Ubuntu/macOS
- **TUI Monitoring**: Terminal interface for real-time status with collection trigger
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
  collection_mode: "both"    # Options: 'csi', 'ftm', 'both'
  mac_address: "\\xf4\\x1e\\x57\\x64\\x92\\xae"  # Target TX MAC when mac_addresses is empty
  mac_addresses: []  # e.g. ["\\xf4\\x1e\\x57\\x64\\x92\\xae", "\\xaa\\xbb\\xcc\\xdd\\xee\\xff"] — non-empty overrides mac_address; out-of-range TXs get UNREACHABLE placeholder lines (same slot count)
  measurements_per_batch: 5
  batch_interval: 1.0
```

**Collection Modes:**
- `csi` - Only collect CSI data for Angle of Arrival (AoA)
- `ftm` - Only collect FTM data for Time of Flight (ToF)
- `both` - Collect both CSI and FTM data simultaneously

**Multi-TX router topic JSON:** `measurements_by_mac` is a list of objects `{"mac_address": "...", "data": [...]}`; `data` is `[]` when that TX had no usable samples for the batch. A flattened `measurements` field (valid lines only, same MAC order) is kept for older consumers.

### 4. Build and Run

```bash
# Source ROS2
source /opt/ros/jazzy/setup.bash

# Build
colcon build --symlink-install
source install/setup.bash

# Run (Continuous Mode - automatic collection)
ros2 launch mmwave_collection collection.launch.py

# Run with specific collection mode
ros2 launch mmwave_collection collection.launch.py collection_mode:=csi    # CSI only
ros2 launch mmwave_collection collection.launch.py collection_mode:=ftm    # FTM only
ros2 launch mmwave_collection collection.launch.py collection_mode:=both   # Both (default)

# OR Run (Discrete Mode - manual trigger collection)
ros2 launch mmwave_collection collection.launch.py discrete_mode:=true
ros2 launch mmwave_collection collection.launch.py discrete_mode:=true collection_mode:=both
```

**See [DISCRETE_MODE.md](DISCRETE_MODE.md) for detailed guide on discrete collection mode.**

## How It Works

1. **Router Node**: Every 1 second, collects measurements from router and publishes as batches
   - **CSI Mode**: Collects 5 CSI measurements for Angle of Arrival (AoA) analysis
   - **FTM Mode**: Collects Fine Timing Measurements for Time of Flight (ToF) distance estimation
   - **Both Mode**: Collects both CSI and FTM data in each batch
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
├── ftm_data/               # FTM measurement batches (JSON)
│   └── batch*.json
└── images/                 # Synchronized images
    └── *.jpg
```

Each `metadata.json` entry contains:
- Synchronized timestamp
- GPS coordinates (lat, lon, alt)
- Data type (csi, ftm, or both)
- Path to CSI batch file (if CSI collected)
- Path to FTM batch file (if FTM collected)
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

## Terminal UI

Monitor and control collection in real-time:

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

**Key Bindings:**
- **SPACE** - Trigger data collection (discrete mode)
- **C** - Clear log
- **Q** - Quit

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
