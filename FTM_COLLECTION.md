# FTM (Fine Timing Measurement) Collection

This document describes the FTM functionality added to the mmWave data collection system for Time-of-Flight (ToF) distance estimation.

## Overview

The system now supports three collection modes:
- **CSI Mode** (`collection_mode: 'csi'`) - Collects Channel State Information for Angle of Arrival (AoA) analysis
- **FTM Mode** (`collection_mode: 'ftm'`) - Collects Fine Timing Measurements for Time of Flight (ToF) distance estimation
- **Both Mode** (`collection_mode: 'both'`) - Collects both CSI and FTM data (default)

## How FTM Collection Works

FTM collection follows a different process than CSI collection:

1. **Connection Establishment**: The router establishes a Wi-Fi connection via `wpa_supplicant`
2. **FTM Request**: Sends a ToF vendor command using `iw dev wlan0 vendor recv 0x001374 0x81 -`
3. **Measurement Retrieval**: Reads FTM measurements from `dmesg` that contain timing information
4. **Retry Logic**: If no measurements are received, the connection is reset and retried (up to 10 times)
5. **Batch Completion**: Collects the specified number of measurements before completing

### Key Differences from CSI Collection

| Feature | CSI Collection | FTM Collection |
|---------|---------------|----------------|
| Vendor Command | `0x93` | `0x81` |
| MAC Address | Target device MAC | Broadcast (`\xaa\xaa\xaa\xaa\xaa\xaa`) |
| Retry Strategy | Single attempt | Multiple reconnection attempts |
| Connection Stability | Expects stable connection | Handles intermittent measurements |

## Configuration

### In `config/default_config.yaml`

```yaml
rx_router:
  host: "192.168.1.101"
  collection_mode: "both"  # Options: 'csi', 'ftm', 'both'
  measurements_per_batch: 5
  connection_timeout: 10
```

### Via Launch Arguments

**Continuous Mode:**
```bash
ros2 launch mmwave_collection collection.launch.py collection_mode:=ftm
ros2 launch mmwave_collection collection.launch.py collection_mode:=both
```

**Discrete/Automated Mode:**
```bash
ros2 launch mmwave_collection automated_collection.launch.py collection_mode:=ftm
ros2 launch mmwave_collection automated_collection.launch.py collection_mode:=both
```

## Data Storage

When FTM collection is enabled, data is stored in a separate directory:

```
data/YYYY-MM-DD/session_HHMMSS/
├── metadata.json
├── rx_router_data/          # CSI data (if collection_mode is 'csi' or 'both')
│   └── *.json
├── ftm_data/                # FTM data (if collection_mode is 'ftm' or 'both')
│   └── *.json
└── images/
    └── *.jpg
```

### FTM Data Format

Each FTM batch file contains:

```json
{
  "data_type": "ftm",
  "batch_id": 0,
  "timestamp": "2025-01-31T12:34:56.789000",
  "measurements": [
    "[ 1234.567890] Measurement: ...",
    "[ 1234.567891] Measurement: ...",
    ...
  ],
  "count": 5
}
```

### Metadata Format

The `metadata.json` file now includes data type information:

```json
{
  "session_id": "session_123456",
  "start_time": "2025-01-31T12:34:56",
  "data_points": [
    {
      "index": 1,
      "timestamp": "2025-01-31T12:34:56.789",
      "gps": {...},
      "router_batch": {
        "data_type": "ftm",
        "batch_id": 0,
        "measurement_count": 5,
        "file": "ftm_data/20250131_123456_789_batch0.json"
      },
      "image": "images/20250131_123456_789.jpg"
    }
  ]
}
```

## Implementation Details

### Router Node Changes

The router node (`router_node.py`) has been enhanced to:

1. **Support Collection Mode Parameter**: Accepts `collection_mode` parameter ('csi', 'ftm', or 'both')
2. **Upload Multiple Scripts**: Uploads both CSI and FTM collection scripts to the router
3. **Separate Data Collection**: Maintains separate batch counters for CSI and FTM
4. **Labeled Publishing**: Publishes data with `data_type` field to distinguish CSI from FTM

### Router Utils Changes

New function added to `router_utils.py`:

- `prepare_ftm_collection_script()`: Generates the FTM collection bash script with:
  - Connection retry logic
  - FTM-specific vendor commands
  - Measurement parsing from dmesg
  - Robust error handling

### Sync Node Changes

The sync node (`sync_node.py`) has been updated to:

1. **Create FTM Directory**: Automatically creates `ftm_data/` subdirectory
2. **Route Data by Type**: Saves CSI data to `rx_router_data/` and FTM data to `ftm_data/`
3. **Include Type in Metadata**: Records the data type in metadata entries

## Troubleshooting

### No FTM Measurements Received

If you see "No FTM for a long time" errors:

1. **Check Wi-Fi Connection**: Ensure the router can connect to the access point
   ```bash
   # On router
   cat /sys/kernel/debug/ieee80211/phy0/wil6210/stations
   ```

2. **Verify FTM Support**: Ensure both devices support FTM
   ```bash
   # On router
   iw dev wlan0 info | grep FTM
   ```

3. **Check dmesg Output**: Look for measurement lines
   ```bash
   # On router
   dmesg | grep Measurement
   ```

### Connection Timeout Issues

If connection timeouts are frequent:

1. **Increase Connection Timeout**: In config file:
   ```yaml
   connection_timeout: 20  # Increase from 10
   ```

2. **Check Network Interference**: Ensure 60GHz band is clear

3. **Verify wpa_supplicant Config**: Check `/etc/wpa_supplicant.conf` on router

### Mixed CSI/FTM Data

When using `collection_mode: 'both'`, the system collects both types sequentially for each trigger. If you need them to be more synchronized, consider:

1. Reducing `batch_interval` for faster collection
2. Using discrete mode with manual triggers
3. Adjusting `measurements_per_batch` to balance speed vs. data quantity

## Performance Considerations

- **FTM Collection is Slower**: Due to retry logic, FTM collection typically takes 2-3x longer than CSI
- **Both Mode Duration**: When using 'both' mode, expect ~2-4 seconds per collection cycle
- **Connection Overhead**: Each FTM batch requires connection reset, adding latency
- **Batch Size**: Larger batch sizes reduce overhead but increase collection time linearly

## Testing

To test FTM collection:

```bash
# Test FTM only
ros2 launch mmwave_collection collection.launch.py \
  discrete_mode:=true \
  collection_mode:=ftm

# In another terminal, trigger collection
ros2 topic pub /trigger_collection std_msgs/msg/Empty "{}"

# Check the data
cat data/$(date +%Y-%m-%d)/session_*/ftm_data/*.json
```

## References

- FTM Standard: IEEE 802.11-2016 (Fine Timing Measurement)
- Vendor Commands: Talon/Sparrow 60GHz chipset documentation
- iw utility: https://wireless.wiki.kernel.org/en/users/documentation/iw
