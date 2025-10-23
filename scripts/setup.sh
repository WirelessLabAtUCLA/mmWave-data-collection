#!/bin/bash
# Setup script for mmWave data collection

set -e

echo "==================================="
echo "mmWave Data Collection Setup"
echo "==================================="
echo ""

# Detect platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
    echo "Platform: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
    echo "Platform: macOS"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found!"
    exit 1
fi

echo "Python: $(python3 --version)"

# Check ROS2
if [ -f "/opt/ros/humble/setup.bash" ]; then
    echo "ROS2 Humble found (Ubuntu)"
    source /opt/ros/humble/setup.bash
elif [ -f "/opt/homebrew/opt/ros-humble/setup.bash" ]; then
    echo "ROS2 Humble found (macOS - Apple Silicon)"
    source /opt/homebrew/opt/ros-humble/setup.bash
elif [ -f "/usr/local/opt/ros-humble/setup.bash" ]; then
    echo "ROS2 Humble found (macOS - Intel)"
    source /usr/local/opt/ros-humble/setup.bash
else
    echo "Warning: ROS2 Humble not found!"
    echo "Please install ROS2 Humble first:"
    if [ "$PLATFORM" = "linux" ]; then
        echo "  sudo apt install ros-humble-desktop"
    else
        echo "  brew install ros-humble-desktop"
    fi
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create directories
echo ""
echo "Creating data directories..."
mkdir -p data logs

# Platform-specific setup
if [ "$PLATFORM" = "linux" ]; then
    echo ""
    echo "Linux-specific setup:"
    echo "- To access GPS devices, add your user to the dialout group:"
    echo "    sudo usermod -a -G dialout $USER"
    echo "    (requires logout/login)"
fi

# Build ROS2 workspace
echo ""
echo "Building ROS2 workspace..."
colcon build --symlink-install

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit config/default_config.yaml with your router details"
echo "2. Source the workspace:"
echo "     source install/setup.bash"
echo "3. Launch the system:"
echo "     ros2 launch mmwave_collection collection.launch.py"
echo "4. (Optional) In another terminal, run the TUI:"
echo "     python3 tui/app.py"
echo ""

