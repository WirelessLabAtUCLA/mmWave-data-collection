#!/bin/bash
# Test script for discrete mode functionality

echo "=== Testing Discrete Mode Data Collection ==="
echo ""
echo "This script will test the discrete collection mode by sending trigger messages."
echo ""

# Source ROS2
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
else
    echo "Error: ROS2 not found. Please source your ROS2 installation."
    exit 1
fi

# Source workspace
if [ -f "install/setup.bash" ]; then
    source install/setup.bash
else
    echo "Error: Workspace not built. Please run 'colcon build' first."
    exit 1
fi

echo "Testing discrete collection trigger..."
echo ""
echo "Sending 3 collection triggers with 3 second intervals..."
echo ""

for i in {1..3}; do
    echo "Trigger $i/3"
    ros2 topic pub --once /trigger_collection std_msgs/msg/Empty
    if [ $i -lt 3 ]; then
        echo "Waiting 3 seconds..."
        sleep 3
    fi
done

echo ""
echo "Done! Check the logs and data directory for collected samples."
echo ""
echo "To monitor in real-time:"
echo "  Terminal 1: ros2 launch mmwave_collection collection.launch.py discrete_mode:=true"
echo "  Terminal 2: python3 tui/app.py"
echo "  In TUI, press SPACE to trigger collection"

