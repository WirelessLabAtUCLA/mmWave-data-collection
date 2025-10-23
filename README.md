# mmWave Data Collection System

Automated data collection from 60GHz router with synchronized GPS and camera data.

## Features

- **ROS2-based** sensor synchronization
- **SSH/SCP** data collection from router
- **GPS** location tracking  
- **Webcam** image capture
- **TUI** for monitoring
- **Cross-platform** (Ubuntu & macOS)

## Quick Start

### 1. Install Dependencies

**Ubuntu:**
```bash
# Install ROS2 Humble
sudo apt update
sudo apt install ros-humble-desktop python3-colcon-common-extensions

# Install system packages
sudo apt install python3-pip gpsd v4l-utils

# Install Python packages
pip3 install -r requirements.txt
```

**macOS:**
```bash
# Install ROS2 via Homebrew
brew install ros-humble-desktop

# Install Python packages
pip3 install -r requirements.txt
```

### 2. Configure

Edit `config/default_config.yaml`:
- Set router IP, username, SSH key path
- Adjust GPS device path (or use auto-detect)
- Configure camera settings

### 3. Build

```bash
# Source ROS2
source /opt/ros/humble/setup.bash  # Ubuntu
# source /opt/homebrew/opt/ros-humble/setup.bash  # macOS

# Build
colcon build --symlink-install

# Source workspace
source install/setup.bash
```

### 4. Run

**Option A: With TUI (recommended)**
```bash
# Terminal 1: Launch ROS nodes
ros2 launch mmwave_collection collection.launch.py

# Terminal 2: Launch TUI
python3 tui/app.py
```

**Option B: Nodes only**
```bash
ros2 launch mmwave_collection collection.launch.py
```

## Data Output

Data is saved to `./data/` organized by date:
```
data/
└── 2025-10-22/
    └── session_143052/
        ├── metadata.json       # Session info & GPS track
        ├── router_data/        # Router data files
        │   └── *.txt
        └── images/             # Camera images
            └── *.jpg
```

## Configuration

Key settings in `config/default_config.yaml`:

- **Router**: SSH credentials, command to run, collection interval
- **GPS**: Device path, baudrate, auto-detect
- **Camera**: Device ID, resolution, JPEG quality
- **Storage**: Data path, organization

## Troubleshooting

**GPS not found:**
- Ubuntu: Check `ls /dev/ttyUSB*`, add user to dialout group
- macOS: Check `ls /dev/cu.*`, install USB drivers if needed

**Camera not working:**
- Try different device_id values (0, 1, 2)
- macOS: Grant camera permission in System Preferences

**SSH connection fails:**
- Verify router IP and SSH key path
- Test manually: `ssh -i ~/.ssh/id_rsa admin@192.168.1.1`

See `PLATFORM_COMPATIBILITY.md` for detailed platform-specific instructions.

## Project Structure

```
├── config/                 # Configuration files
├── src/mmwave_collection/ # ROS2 package
│   ├── nodes/             # Router, GPS, Camera, Sync nodes
│   ├── utils/             # Platform utilities, config loader
│   └── launch/            # Launch files
├── tui/                   # Terminal UI
└── data/                  # Collected data (gitignored)
```

## License

MIT

