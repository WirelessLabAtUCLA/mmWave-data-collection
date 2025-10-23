#!/bin/bash
# Quick launch script

# Detect ROS2 setup file
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
elif [ -f "/opt/homebrew/opt/ros-humble/setup.bash" ]; then
    source /opt/homebrew/opt/ros-humble/setup.bash
elif [ -f "/usr/local/opt/ros-humble/setup.bash" ]; then
    source /usr/local/opt/ros-humble/setup.bash
fi

# Source workspace
if [ -f "install/setup.bash" ]; then
    source install/setup.bash
else
    echo "Workspace not built! Run: colcon build"
    exit 1
fi

# Launch
echo "Starting mmWave data collection..."
ros2 launch mmwave_collection collection.launch.py

