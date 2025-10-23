# Cross-Platform Compatibility Analysis
## macOS & Ubuntu Support for mmWave Data Collection System

**Date:** October 22, 2025  
**Platforms:** macOS (Apple Silicon & Intel) | Ubuntu 22.04/24.04

---

## Executive Summary

✅ **The system CAN work on both macOS and Ubuntu** with some platform-specific configurations.

**Overall Compatibility:**
- ✅ ROS2: Supported on both (with caveats)
- ✅ TUI (Textual): Fully cross-platform
- ✅ SSH/SCP (Paramiko): Fully cross-platform
- ⚠️ GPS: Different device paths and drivers
- ⚠️ Camera: Different device handling
- ✅ Python libraries: All cross-platform

---

## 1. ROS2 Compatibility

### Ubuntu ✅ **FULLY SUPPORTED** (Recommended)
- **ROS2 Humble/Iron:** Official tier 1 support
- **Installation:** `apt install ros-humble-desktop`
- **Best experience:** Native integration, all packages available

### macOS ⚠️ **SUPPORTED WITH LIMITATIONS**

#### macOS Support Status:
| ROS2 Version | Apple Silicon (M1/M2/M3) | Intel Mac | Notes |
|--------------|--------------------------|-----------|-------|
| **Humble** | ✅ Homebrew build | ✅ Official | Recommended |
| **Iron** | ✅ Homebrew build | ✅ Official | Latest LTS |
| **Jazzy** | ✅ Homebrew build | ✅ Official | Newest |

#### Installation Methods:

**Option 1: Homebrew (Recommended for Mac)**
```bash
# Install ROS2 via Homebrew
brew install ros-humble-desktop

# Source setup
source /opt/homebrew/opt/ros-humble/setup.bash  # Apple Silicon
# OR
source /usr/local/opt/ros-humble/setup.bash     # Intel
```

**Option 2: Build from source**
- More control, but time-consuming
- Required for custom message types anyway

#### macOS Limitations:
- ⚠️ Some visualization tools (RViz) may have rendering issues
- ⚠️ Fewer pre-built packages available (not a problem for our custom nodes)
- ✅ Core functionality (rclpy, messages, services) works perfectly
- ✅ rosbag2 works on macOS

**Verdict:** ✅ ROS2 works fine on macOS for this project. Our custom nodes don't rely on Mac-unsupported packages.

---

## 2. GPS Hardware & Drivers

### ⚠️ **PLATFORM DIFFERENCES - Configuration Required**

#### Device Paths:

**Ubuntu:**
```bash
# USB GPS devices typically appear as:
/dev/ttyUSB0, /dev/ttyUSB1, ...
/dev/ttyACM0, /dev/ttyACM1, ...  # Some USB-serial adapters

# Check with:
ls /dev/tty*
dmesg | grep tty
```

**macOS:**
```bash
# USB GPS devices typically appear as:
/dev/tty.usbserial-XXXXXXXX
/dev/cu.usbserial-XXXXXXXX   # Use cu.* for output
/dev/tty.usbmodem-XXXXXXXX

# Check with:
ls /dev/tty.*
ls /dev/cu.*
system_profiler SPUSBDataType  # Show USB devices
```

#### Driver Support:

**Ubuntu:**
- ✅ FTDI, Prolific, CH340 drivers built into kernel
- ✅ Most USB GPS devices work out-of-the-box
- ✅ gpsd package: `sudo apt install gpsd gpsd-clients`

**macOS:**
- ✅ Most USB-serial drivers work (may need to install)
- ⚠️ FTDI: Usually works, may need [VCP driver](https://ftdichip.com/drivers/vcp-drivers/)
- ⚠️ CH340: Needs driver from manufacturer
- ✅ gpsd via Homebrew: `brew install gpsd`

#### Solution: Auto-detect GPS device

```python
# Platform-agnostic GPS device detection
import platform
import glob

def find_gps_device():
    """Auto-detect GPS device across platforms"""
    system = platform.system()
    
    if system == "Linux":
        # Try common Linux paths
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    elif system == "Darwin":  # macOS
        # Try macOS paths
        candidates = glob.glob("/dev/cu.usbserial*") + \
                    glob.glob("/dev/cu.usbmodem*")
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
    
    return candidates[0] if candidates else None
```

---

## 3. Camera Support

### ⚠️ **PLATFORM DIFFERENCES - Different APIs**

#### Device Handling:

**Ubuntu:**
```bash
# V4L2 (Video4Linux2) devices:
/dev/video0, /dev/video1, ...

# Check available cameras:
v4l2-ctl --list-devices
ls /dev/video*
```

**macOS:**
```bash
# No /dev/video* devices
# Cameras accessed via AVFoundation framework

# Check available cameras:
system_profiler SPCameraDataType
```

#### OpenCV Support:

**Good News:** ✅ OpenCV abstracts platform differences!

```python
import cv2

# Works on BOTH platforms!
cap = cv2.VideoCapture(0)  # Device ID 0, 1, 2, etc.
ret, frame = cap.read()
```

**Ubuntu:** OpenCV uses V4L2 backend
**macOS:** OpenCV uses AVFoundation backend

**Caveats on macOS:**
- ⚠️ Device IDs may differ (test with `cv2.VideoCapture(0), (1), (2)...`)
- ⚠️ Some advanced camera controls may not work
- ✅ Basic capture, resolution, format settings work fine

#### ROS2 usb_cam Package:

**Ubuntu:** ✅ Full support with V4L2
**macOS:** ⚠️ May not work (V4L2 specific)

**Solution:** Use our custom camera_node with OpenCV (cross-platform)

---

## 4. Python Libraries

### ✅ **ALL FULLY CROSS-PLATFORM**

| Library | Ubuntu | macOS | Installation |
|---------|--------|-------|--------------|
| **Paramiko** | ✅ | ✅ | `pip install paramiko` |
| **Textual** | ✅ | ✅ | `pip install textual` |
| **OpenCV** | ✅ | ✅ | `pip install opencv-python` |
| **PyYAML** | ✅ | ✅ | `pip install pyyaml` |
| **gpsd-py3** | ✅ | ✅ | `pip install gpsd-py3` |
| **pyserial** | ✅ | ✅ | `pip install pyserial` |
| **pynmea2** | ✅ | ✅ | `pip install pynmea2` |

---

## 5. File Paths & Conventions

### Configuration Updates Needed:

**Current (Linux-only):**
```yaml
gps:
  device: "/dev/ttyUSB0"  # ❌ Won't work on Mac

camera:
  device_id: 0  # ✅ Works on both
```

**Updated (Cross-platform):**
```yaml
gps:
  device: "auto"  # Auto-detect, or specify per platform
  # device: "/dev/ttyUSB0"        # Ubuntu
  # device: "/dev/cu.usbserial-*" # macOS
  auto_detect: true  # Try to find GPS automatically

camera:
  device_id: 0  # Works on both
  # Try 0, 1, 2 if not found
```

### Path Separators:
✅ Python's `pathlib` handles this automatically:
```python
from pathlib import Path

# Works on both platforms
data_path = Path("data") / "session" / "images"
```

---

## 6. SSH/SCP (Paramiko)

### ✅ **FULLY CROSS-PLATFORM**

**No changes needed!** Paramiko works identically on Ubuntu and macOS.

**SSH Key Locations:**
- Ubuntu: `~/.ssh/id_rsa`
- macOS: `~/.ssh/id_rsa`
- ✅ Same path, works on both

---

## 7. Terminal & TUI (Textual)

### ✅ **FULLY CROSS-PLATFORM**

**Textual support:**
- ✅ Ubuntu: Terminal, iTerm2, etc.
- ✅ macOS: Terminal.app, iTerm2, Warp, etc.
- ✅ Windows: PowerShell, Windows Terminal (bonus!)

**No changes needed!**

---

## 8. Build System & Colcon

### ✅ **WORKS ON BOTH**

**Ubuntu:**
```bash
sudo apt install python3-colcon-common-extensions
```

**macOS:**
```bash
pip3 install colcon-common-extensions
# OR
brew install colcon
```

---

## 9. Required Configuration Changes

### Update: `config/default_config.yaml`

```yaml
# Platform-specific settings
platform:
  auto_detect: true  # Automatically detect platform
  
gps:
  enabled: true
  auto_detect: true  # NEW: Auto-detect GPS device
  
  # Platform-specific overrides (optional)
  device_linux: "/dev/ttyUSB0"
  device_macos: "/dev/cu.usbserial-*"
  
  # OR just specify and let code handle it
  device: "auto"
  
  interface: "gpsd"  # Works on both
  # Alternative: "serial" also works on both with pyserial

camera:
  enabled: true
  device_id: 0  # Try 0, then 1, then 2
  auto_detect: true  # NEW: Try multiple device IDs
  fallback_devices: [0, 1, 2]  # Try in order
```

### Add: Platform Detection Utility

**New file: `src/mmwave_collection/utils/platform_utils.py`**

```python
import platform
import glob
from pathlib import Path
from typing import Optional, List

def get_platform() -> str:
    """Get platform name: 'linux', 'macos', or 'windows'"""
    system = platform.system()
    if system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "macos"
    elif system == "Windows":
        return "windows"
    else:
        return "unknown"

def find_gps_devices() -> List[str]:
    """Find all potential GPS serial devices"""
    platform_name = get_platform()
    
    if platform_name == "linux":
        devices = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    elif platform_name == "macos":
        devices = glob.glob("/dev/cu.usbserial*") + \
                 glob.glob("/dev/cu.usbmodem*") + \
                 glob.glob("/dev/tty.usbserial*")
    else:
        devices = []
    
    return sorted(devices)

def find_camera_devices() -> List[int]:
    """Find available camera device IDs"""
    import cv2
    
    available = []
    # Try first 5 device IDs
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    
    return available

def get_home_dir() -> Path:
    """Get user home directory (cross-platform)"""
    return Path.home()

def get_ssh_key_path() -> Path:
    """Get default SSH key path"""
    return get_home_dir() / ".ssh" / "id_rsa"
```

---

## 10. Installation Instructions

### Ubuntu 22.04/24.04

```bash
# 1. Install ROS2 Humble
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions

# 2. Install system dependencies
sudo apt install -y \
    python3-pip \
    gpsd gpsd-clients \
    v4l-utils \
    libopencv-dev

# 3. Install Python dependencies
pip3 install -r requirements.txt

# 4. Build workspace
cd ~/mmWave-data-collection
colcon build --symlink-install

# 5. Source workspace
source install/setup.bash
```

### macOS (Apple Silicon or Intel)

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install ROS2 Humble
brew install ros-humble-desktop

# 3. Install system dependencies
brew install \
    python@3.10 \
    gpsd \
    opencv

# 4. Install Python dependencies
pip3 install -r requirements.txt

# 5. Install USB drivers (if needed)
# Check if your GPS device is recognized first:
ls /dev/cu.*
# If not, install drivers from manufacturer

# 6. Build workspace
cd ~/mmWave-data-collection
colcon build --symlink-install

# 7. Source workspace (Apple Silicon)
source /opt/homebrew/opt/ros-humble/setup.bash
source install/setup.bash

# OR (Intel Mac)
# source /usr/local/opt/ros-humble/setup.bash
# source install/setup.bash
```

---

## 11. Testing Matrix

### Recommended Testing:

| Test | Ubuntu 22.04 | Ubuntu 24.04 | macOS Intel | macOS Apple Silicon |
|------|--------------|--------------|-------------|---------------------|
| ROS2 build | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Router node (SSH/SCP) | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| GPS node | ✅ Required | ✅ Required | ⚠️ If GPS available | ⚠️ If GPS available |
| Camera node | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Data sync | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| TUI | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| rosbag recording | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

---

## 12. Known Issues & Workarounds

### Issue 1: GPS Device Permissions (Ubuntu)

**Problem:** Cannot access `/dev/ttyUSB0` (permission denied)

**Solution:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Issue 2: GPS Device Permissions (macOS)

**Problem:** Cannot access `/dev/cu.usbserial-*`

**Solution:**
```bash
# Usually no permission issues, but if needed:
sudo chmod 666 /dev/cu.usbserial-*
```

### Issue 3: Camera Access (macOS)

**Problem:** "Camera access denied" on macOS

**Solution:**
1. System Preferences → Security & Privacy → Camera
2. Grant permission to Terminal or iTerm2
3. May need to grant permission to Python

### Issue 4: ROS2 Environment (macOS)

**Problem:** `ros2` command not found

**Solution:**
```bash
# Add to ~/.zshrc or ~/.bash_profile
source /opt/homebrew/opt/ros-humble/setup.zsh  # Apple Silicon, zsh
# OR
source /opt/homebrew/opt/ros-humble/setup.bash # bash
```

### Issue 5: Homebrew vs System Python (macOS)

**Problem:** Python version mismatch

**Solution:**
```bash
# Use Homebrew Python
brew install python@3.10
# Add to PATH in ~/.zshrc:
export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"
```

---

## 13. CI/CD Considerations

### GitHub Actions Matrix:

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-22.04, ubuntu-24.04, macos-13, macos-14]  # Intel & Apple Silicon
        ros_distro: [humble]
    
    runs-on: ${{ matrix.os }}
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup ROS2 (Ubuntu)
        if: runner.os == 'Linux'
        uses: ros-tooling/setup-ros@v0.6
        with:
          required-ros-distributions: ${{ matrix.ros_distro }}
      
      - name: Setup ROS2 (macOS)
        if: runner.os == 'macOS'
        run: brew install ros-${{ matrix.ros_distro }}-desktop
      
      - name: Build and Test
        run: |
          source /opt/ros/${{ matrix.ros_distro }}/setup.bash || \
          source /opt/homebrew/opt/ros-${{ matrix.ros_distro }}/setup.bash
          
          colcon build
          colcon test
          colcon test-result --verbose
```

---

## 14. Recommendations

### Development Strategy:

1. **Primary Development:** Ubuntu (best ROS2 support)
2. **Secondary Testing:** macOS (ensure compatibility)
3. **Use Containers:** Consider Docker for consistent environments

### Deployment Strategy:

**For Production/Field Use:**
- ✅ **Recommended:** Ubuntu on dedicated hardware
- ⚠️ **Alternative:** macOS laptop for testing/demos

**Reasons:**
- Ubuntu has better hardware driver support
- ROS2 packages more mature on Linux
- Easier to troubleshoot in the field

### Docker Option (Advanced):

```dockerfile
# Dockerfile for cross-platform development
FROM ros:humble

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    gpsd \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /workspace
WORKDIR /workspace

# Build
RUN . /opt/ros/humble/setup.sh && \
    colcon build

CMD ["/bin/bash"]
```

**Use on both platforms:**
```bash
docker build -t mmwave-collection .
docker run -it --device=/dev/ttyUSB0 --device=/dev/video0 mmwave-collection
```

---

## 15. Updated Planning Document Sections

### Section to Add: Platform Support

**Insert after Section 5 (Technical Stack):**

#### 5.4 Platform Support

| Component | Ubuntu 22.04+ | macOS 12+ | Notes |
|-----------|---------------|-----------|-------|
| ROS2 Core | ✅ Native | ✅ Homebrew | Full support |
| Python 3.10+ | ✅ | ✅ | Identical |
| Paramiko (SSH/SCP) | ✅ | ✅ | No changes needed |
| Textual (TUI) | ✅ | ✅ | No changes needed |
| OpenCV | ✅ | ✅ | Auto backend selection |
| GPS (gpsd) | ✅ | ✅ Homebrew | Different device paths |
| GPS (serial) | ✅ | ✅ | Different device paths |
| rosbag2 | ✅ | ✅ | No changes needed |

**Platform-specific code:**
- Auto-detection for GPS devices
- Auto-detection for cameras
- Path handling via `pathlib`
- Platform utility module

---

## 16. Action Items

### Before Implementation:

- [x] Document platform differences
- [ ] Add platform detection utility
- [ ] Update configuration schema
- [ ] Add auto-detect for GPS/camera
- [ ] Update installation docs
- [ ] Create platform-specific setup scripts
- [ ] Add CI/CD for both platforms

### During Development:

- [ ] Test on Ubuntu 22.04
- [ ] Test on Ubuntu 24.04
- [ ] Test on macOS Intel (if available)
- [ ] Test on macOS Apple Silicon
- [ ] Document any platform-specific issues

### Testing Checklist:

**Ubuntu:**
- [ ] ROS2 builds successfully
- [ ] GPS device detected (`/dev/ttyUSB*`)
- [ ] Camera device works (`/dev/video0`)
- [ ] SSH/SCP to router works
- [ ] TUI renders correctly
- [ ] rosbag records data

**macOS:**
- [ ] ROS2 builds successfully (Homebrew)
- [ ] GPS device detected (`/dev/cu.*`)
- [ ] Camera device works (built-in or USB)
- [ ] SSH/SCP to router works
- [ ] TUI renders correctly (Terminal.app + iTerm2)
- [ ] rosbag records data

---

## Summary

### ✅ **YES, IT WILL WORK ON BOTH PLATFORMS**

**Required changes:**
1. ✅ Add platform detection utility
2. ✅ Auto-detect GPS devices (different paths)
3. ✅ Auto-detect camera devices (same API, different backends)
4. ✅ Update installation documentation
5. ✅ Test on both platforms

**No changes needed for:**
- SSH/SCP (Paramiko)
- TUI (Textual)
- ROS2 core functionality
- Python libraries
- Data storage

**Bottom line:** The architecture is sound for cross-platform support. We just need to add smart device detection and provide platform-specific installation instructions.

---

## Next Steps

1. **Add `platform_utils.py`** to handle device detection
2. **Update `config/default_config.yaml`** with auto-detect options
3. **Create separate installation guides:**
   - `docs/INSTALL_UBUNTU.md`
   - `docs/INSTALL_MACOS.md`
4. **Update PLANNING.md** with platform support section
5. **Begin Phase 1 implementation** with cross-platform considerations

Ready to proceed? 🚀

