# Discrete Data Collection Mode

This document explains how to use the discrete (trigger-based) data collection mode in the mmWave data collection system.

## Overview

The system now supports two modes of operation:

1. **Continuous Mode** (default): Data is collected automatically at regular intervals
2. **Discrete Mode**: Data is collected only when triggered by the user via the TUI

## How It Works

### Discrete Mode Architecture

In discrete mode:
- **GPS Node**: Continuously reads GPS data but only publishes when triggered
- **Camera Node**: Only captures images when triggered
- **Router Node**: Only collects CSI measurements when triggered
- **Sync Node**: Continues to work as before, synchronizing and saving triggered data

### Trigger Mechanism

All nodes subscribe to the `/trigger_collection` topic. When the TUI publishes an `Empty` message to this topic, all nodes in discrete mode will:
1. Capture/publish one sample (GPS, Camera)
2. Initiate one collection batch (Router)
3. The sync node will synchronize and save the data

## Usage

### 1. Launch in Discrete Mode

To start the system in discrete mode, use the `discrete_mode` launch argument:

```bash
ros2 launch mmwave_collection collection.launch.py discrete_mode:=true
```

For continuous mode (default):

```bash
ros2 launch mmwave_collection collection.launch.py discrete_mode:=false
# or simply:
ros2 launch mmwave_collection collection.launch.py
```

### 2. Start the TUI

In a separate terminal, start the text user interface:

```bash
cd tui
python3 app.py
```

### 3. Collect Data

In the TUI window:
- Press **SPACE** to trigger a data collection
- Press **C** to clear the log
- Press **Q** to quit

Each time you press SPACE:
1. A trigger is sent to all nodes
2. GPS publishes the latest fix
3. Camera captures and publishes an image
4. Router collects a batch of CSI measurements
5. The sync node saves all synchronized data to disk

### 4. Monitor Status

The TUI displays:
- **System Status**: Connection status for Router, GPS, and Camera
- **GPS Location**: Current GPS coordinates
- **Log**: Real-time log messages showing collection events

## Key Bindings

| Key | Action | Description |
|-----|--------|-------------|
| SPACE | Collect Sample | Trigger one data collection |
| C | Clear Log | Clear the log window |
| Q | Quit | Exit the TUI |

## Configuration

### Node Parameters

Each data collection node now has a `discrete_mode` parameter:

**GPS Node** (`gps_node.py`):
```yaml
discrete_mode: true/false
```
- `false`: Publishes GPS data continuously at 10Hz
- `true`: Only publishes GPS data when triggered

**Camera Node** (`camera_node.py`):
```yaml
discrete_mode: true/false
```
- `false`: Captures and publishes images continuously at 1Hz
- `true`: Only captures images when triggered

**Router Node** (`router_node.py`):
```yaml
discrete_mode: true/false
```
- `false`: Collects CSI measurements automatically at regular intervals
- `true`: Only collects CSI measurements when triggered

### Launch File

The launch file (`collection.launch.py`) passes the `discrete_mode` argument to all nodes:

```python
ros2 launch mmwave_collection collection.launch.py discrete_mode:=true
```

## Data Storage

Data is stored in the same format regardless of mode:
- **Directory**: `./data/YYYY-MM-DD/session_HHMMSS/`
- **Subdirectories**:
  - `rx_router_data/`: Router CSI measurements (JSON)
  - `images/`: Camera images (JPEG)
- **Metadata**: `metadata.json` contains GPS coordinates and references to all data files

## Use Cases

**Discrete Mode** is ideal for:
- Collecting data at specific locations
- Manual data collection campaigns
- Controlled experiments with precise timing
- Reducing data volume by only collecting when needed

**Continuous Mode** is ideal for:
- Mobile data collection
- Long-term monitoring
- Automated data collection
- Drive-test scenarios

## Tips

1. **GPS Fix**: Ensure GPS has a valid fix before collecting data in discrete mode
2. **Status Indicators**: Watch the status indicators to ensure all sensors are active
3. **Collection Rate**: You can collect samples as fast or slow as you want in discrete mode
4. **Data Sync**: The sync node uses time-based synchronization with a tolerance of 2 seconds

## Troubleshooting

### No Data Collected After Trigger

1. Check that all nodes are running: `ros2 node list`
2. Verify discrete mode is enabled: Check node logs for "discrete mode" message
3. Ensure GPS has a valid fix
4. Check camera is properly connected
5. Verify router SSH connection is established

### TUI Not Responding to SPACE Key

1. Make sure the TUI window has focus
2. Check that ROS2 is initialized properly
3. Verify the `/trigger_collection` topic exists: `ros2 topic list`

### Data Not Synchronized

The sync node requires all three data sources (GPS, Camera, Router) within the time tolerance (default 2 seconds). If collection is too slow, increase the `time_tolerance` parameter in the sync node.

## Example Workflow

1. **Setup**: Launch nodes in discrete mode and start TUI
2. **Navigate**: Move to your first data collection point
3. **Wait**: Ensure GPS has a good fix and all systems are ready
4. **Collect**: Press SPACE to collect a sample
5. **Verify**: Check the log for confirmation
6. **Repeat**: Move to next point and repeat steps 3-5
7. **Exit**: Press Q to quit when done

## Technical Details

### Topic Structure

- **Trigger Topic**: `/trigger_collection` (std_msgs/Empty)
- **GPS Topic**: `/gps/fix` (sensor_msgs/NavSatFix)
- **Camera Topic**: `/camera/image/compressed` (sensor_msgs/CompressedImage)
- **Router Topic**: `/rx_router/data` (std_msgs/String)

### Message Flow

```
TUI → /trigger_collection → GPS Node → /gps/fix ↘
                         → Camera Node → /camera/image/compressed → Sync Node → Disk
                         → Router Node → /rx_router/data ↗
```

### Code Changes

The implementation involved:
1. Adding `discrete_mode` parameter to all collection nodes
2. Adding trigger subscriber to each node
3. Modifying publish logic to be conditional on mode
4. Adding trigger publisher to TUI
5. Adding key binding for collection trigger
6. Updating launch file with discrete_mode argument

## Future Enhancements

Potential improvements:
- Add delay/debounce to prevent accidental double-triggers
- Add visual feedback in TUI when collection is in progress
- Add countdown timer for automatic collections
- Add ability to set collection intervals in discrete mode
- Add statistics on collection success rate

