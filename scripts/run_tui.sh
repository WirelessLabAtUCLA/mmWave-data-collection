#!/bin/bash
# Launch the data collection TUI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Source ROS Jazzy
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
else
    echo "Error: ROS Jazzy not found at /opt/ros/jazzy"
    exit 1
fi

# Source workspace
if [ -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    source "$WORKSPACE_DIR/install/setup.bash"
else
    echo "Workspace not built! Run: colcon build"
    exit 1
fi

# Check if textual is installed
if ! python3 -c "import textual" 2>/dev/null; then
    echo "Warning: textual package not found. Installing..."
    python3 -m pip install textual --user
fi

# Launch TUI
cd "$WORKSPACE_DIR"
echo "Starting data collection TUI..."
python3 tui/app.py

