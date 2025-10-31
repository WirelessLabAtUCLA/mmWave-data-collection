# mmWave Data Processing

This module provides Python classes for reading and processing mmWave data collection session data.

## Overview

The data processing module includes several classes that represent different levels of the data hierarchy:

- **`GPSCoordinate`**: Represents GPS location data (latitude, longitude, altitude)
- **`RouterMeasurement`**: Represents a single mmWave measurement from the router
- **`RouterBatch`**: Represents a batch of router measurements
- **`DataPoint`**: Represents a single data collection point (GPS + router batch + image)
- **`SessionData`**: Represents a complete data collection session

## Installation

Make sure you have the required dependencies:

```bash
pip install -r ../requirements.txt
```

## Quick Start

### Loading a Single Session

```python
from pathlib import Path
from data_processing import SessionData

# Load a session from directory
session_dir = Path("../data/2025-10-30/session_141256")
session = SessionData.from_directory(session_dir)

# Print summary
print(session.summary())
```

### Loading All Sessions from a Date

```python
from pathlib import Path
from data_processing import load_all_sessions

# Load all sessions
data_dir = Path("../data/2025-10-30")
sessions = load_all_sessions(data_dir)

# Iterate through sessions
for session_id, session_data in sessions.items():
    print(f"{session_id}: {session_data.total_samples} samples")
```

## Usage Examples

### Accessing GPS Data

```python
# Get GPS trajectory as numpy array
trajectory = session.get_gps_trajectory()  # Shape: (N, 3) [lat, lon, alt]

# Access individual GPS coordinates
for dp in session.data_points:
    lat = dp.gps.latitude
    lon = dp.gps.longitude
    alt = dp.gps.altitude
```

### Working with Router Data

```python
# Get a specific data point
data_point = session.get_data_point(19)

# Load router batch data
router_batch = data_point.load_router_batch(session.session_dir)

# Access measurements
for measurement in router_batch.measurements:
    print(f"MAC: {measurement.mac_address}")
    print(f"Timestamp: {measurement.timestamp_seconds}")
    
    # Get phase data (last 40 values)
    phase_data = measurement.get_phase_data()
    
    # Get RSSI data
    rssi_data = measurement.get_rssi_data()
```

### Analyzing Phase Data

```python
# Get all phase data from a batch
phase_data = router_batch.get_all_phase_data()  # Shape: (measurements, phase_values)

# Compute statistics
mean_phase = phase_data.mean()
std_phase = phase_data.std()
```

### Working with Images

```python
# Get all image paths
image_paths = session.get_image_paths()

# Load an image with OpenCV
import cv2
image = cv2.imread(str(data_point.image_path))
```

### Time Series Analysis

```python
# Get all timestamps
timestamps = session.get_timestamps()

# Calculate time intervals
time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
              for i in range(len(timestamps)-1)]
avg_interval = sum(time_diffs) / len(time_diffs)
```

## Data Structure

### Session Directory Structure

```
session_HHMMSS/
├── metadata.json              # Session metadata and index
├── images/                    # Captured images
│   ├── YYYYMMDD_HHMMSS_mmm.jpg
│   └── ...
└── rx_router_data/           # Router measurement batches
    ├── YYYYMMDD_HHMMSS_mmm_batchN.json
    └── ...
```

### Metadata JSON Format

```json
{
  "session_id": "session_141256",
  "start_time": "2025-10-30T14:12:56.472452",
  "end_time": "2025-10-30T14:16:53.635509",
  "total_samples": 86,
  "data_points": [
    {
      "index": 1,
      "timestamp": "2025-10-30T14:13:01.777468",
      "gps": {
        "latitude": 34.0686765,
        "longitude": -118.444395,
        "altitude": 130.4
      },
      "router_batch": {
        "batch_id": 0,
        "measurement_count": 5,
        "file": "rx_router_data/20251030_141301_777_batch0.json"
      },
      "image": "images/20251030_141301_777.jpg"
    }
  ]
}
```

### Router Batch JSON Format

```json
{
  "batch_id": 18,
  "timestamp": "2025-10-30T14:13:48.877555",
  "measurements": [
    "[ 530.502229] [AOA] Measurement: 0,1626941747.663218,f4:1e:57:64:92:ae,2,1,2,0,128,355,44,928,..."
  ],
  "count": 5
}
```

## Class Reference

### SessionData

Main class for loading and working with session data.

**Methods:**
- `from_directory(session_dir)`: Load session from directory (class method)
- `load_all_router_batches()`: Load all router batch data
- `get_data_point(index)`: Get specific data point by index
- `get_gps_trajectory()`: Get GPS trajectory as numpy array
- `get_timestamps()`: Get list of all timestamps
- `get_duration()`: Get session duration in seconds
- `get_image_paths()`: Get list of all image paths
- `summary()`: Get summary string

### DataPoint

Represents a single data collection point.

**Attributes:**
- `index`: Data point index
- `timestamp`: Collection timestamp
- `gps`: GPSCoordinate object
- `router_batch_info`: Batch metadata dict
- `image_path`: Path to image file
- `router_batch`: RouterBatch object (loaded lazily)

**Methods:**
- `load_router_batch(session_dir)`: Load router batch data
- `to_dict()`: Convert to dictionary

### RouterBatch

Batch of router measurements.

**Attributes:**
- `batch_id`: Batch identifier
- `timestamp`: Batch timestamp
- `measurements`: List of RouterMeasurement objects
- `count`: Number of measurements
- `file_path`: Source file path

**Methods:**
- `from_file(file_path)`: Load from JSON file (class method)
- `get_all_phase_data()`: Get phase data as numpy array
- `get_all_rssi_data()`: Get RSSI data as numpy array

### RouterMeasurement

Single mmWave measurement.

**Attributes:**
- `measurement_index`: Measurement index
- `timestamp_seconds`: Unix timestamp
- `mac_address`: Router MAC address
- `raw_data`: Raw integer values
- `raw_string`: Original measurement string

**Methods:**
- `from_string(measurement_string)`: Parse from string (class method)
- `get_phase_data()`: Extract phase data (last 40 values)
- `get_rssi_data()`: Extract RSSI data

### GPSCoordinate

GPS location data.

**Attributes:**
- `latitude`: Latitude in degrees
- `longitude`: Longitude in degrees
- `altitude`: Altitude in meters

**Methods:**
- `from_dict(data)`: Create from dictionary (class method)
- `to_dict()`: Convert to dictionary

## Example Script

See `example_usage.py` for a complete working example:

```bash
cd data_processing
python example_usage.py
```

## Notes

- Router batch data is loaded lazily to save memory
- Phase data extraction assumes specific data format (last 40 values)
- RSSI data extraction assumes specific positions (adjust as needed)
- All timestamps use ISO 8601 format
- GPS coordinates use WGS84 datum

## Future Enhancements

Potential improvements:
- Add data validation and sanity checks
- Support for data export formats (HDF5, CSV, etc.)
- Visualization utilities
- Data filtering and preprocessing
- Machine learning dataset preparation
- Signal processing utilities for phase/RSSI data

