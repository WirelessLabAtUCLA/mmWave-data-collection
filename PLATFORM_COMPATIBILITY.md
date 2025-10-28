# Platform Compatibility Guide

This system works on both **Ubuntu** and **macOS** with minor configuration differences.

## Supported Platforms

✅ Ubuntu 22.04 / 24.04 (Recommended)  
✅ macOS 12+ (Intel & Apple Silicon)

## Installation by Platform

### Ubuntu 22.04/24.04

```bash
# Install ROS2 Jazzy
sudo apt update
sudo apt install ros-jazzy-desktop python3-colcon-common-extensions

# Install dependencies
sudo apt install python3-pip gpsd v4l-utils
pip3 install paramiko textual opencv-python pyyaml pyserial pynmea2

# Add user to dialout group for GPS access
sudo usermod -a -G dialout $USER
# Log out and back in for this to take effect

# Build
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### macOS (Intel or Apple Silicon)

```bash
# Install ROS2 via Homebrew
brew install ros-jazzy-desktop

# Install dependencies
brew install python@3.12 gpsd opencv
pip3 install paramiko textual opencv-python pyyaml pyserial pynmea2

# Build
source /opt/homebrew/opt/ros-jazzy/setup.bash  # Apple Silicon
# OR: source /usr/local/opt/ros-jazzy/setup.bash  # Intel
colcon build --symlink-install
source install/setup.bash
```

## Platform Differences

### GPS Devices

**Ubuntu:**
- Devices appear as `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
- Check: `ls /dev/ttyUSB* /dev/ttyACM*`
- Requires dialout group membership

**macOS:**
- Devices appear as `/dev/cu.usbserial-*`, `/dev/cu.usbmodem-*`
- Check: `ls /dev/cu.*`
- No special permissions usually needed
- May need USB serial drivers from manufacturer

### Camera Devices

**Ubuntu:**
- Uses V4L2 (`/dev/video0`, `/dev/video1`, etc.)
- Check: `v4l2-ctl --list-devices`

**macOS:**
- Uses AVFoundation (no `/dev/video*` files)
- OpenCV auto-selects correct backend
- May need to grant camera permission in System Preferences → Security & Privacy

### Configuration

The system auto-detects GPS devices on both platforms. Update `config/default_config.yaml` only if auto-detection fails:

```yaml
gps:
  device: "auto"  # Works on both platforms
  # Or specify manually:
  # device: "/dev/ttyUSB0"      # Ubuntu
  # device: "/dev/cu.usbserial" # macOS
```

## Common Issues

### GPS Not Found (Ubuntu)

```bash
# Check if device is connected
ls /dev/ttyUSB* /dev/ttyACM*

# Check if you're in dialout group
groups
# Should show: dialout

# If not, add yourself and reboot
sudo usermod -a -G dialout $USER
```

### GPS Not Found (macOS)

```bash
# Check USB devices
ls /dev/cu.* /dev/tty.*
system_profiler SPUSBDataType

# Install USB driver if device not found
# Check manufacturer website for macOS driver
```

### Camera Permission Denied (macOS)

1. Open **System Preferences** → **Security & Privacy** → **Camera**
2. Grant permission to **Terminal** or **iTerm2**
3. Restart terminal and try again

### ROS2 Not Found (macOS)

Add to `~/.zshrc` or `~/.bash_profile`:

```bash
# Apple Silicon
source /opt/homebrew/opt/ros-jazzy/setup.zsh

# Intel Mac
source /usr/local/opt/ros-jazzy/setup.bash
```

### Python Version Mismatch (TUI)

The TUI requires system Python matching ROS2 (Python 3.12 for Jazzy):

```bash
# Exit conda environment
conda deactivate

# Use system Python
python3 --version  # Should show 3.12.x

# Install packages with system pip
pip3 install --user textual
```

## Testing Checklist

**Before first use:**

- [ ] ROS2 builds successfully: `colcon build`
- [ ] GPS detected: Check logs for "Auto-detected GPS device"
- [ ] Camera works: Check logs for "Camera node started"
- [ ] SSH to router works: Test with `ssh user@router_ip`
- [ ] Data saves correctly: Check `data/` directory after collection

## Performance Notes

Both platforms perform identically for this application. Ubuntu is recommended for production use due to:
- Better hardware driver support
- More mature ROS2 ecosystem
- Easier troubleshooting

macOS works great for development and testing.
