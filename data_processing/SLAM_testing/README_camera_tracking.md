# Camera Ground Truth Tracking

Extract 2D ground truth positions from your tilted-down camera using homography transformation.

## Overview

Your camera setup is perfect for homography-based tracking:
- **Tilted-down view** of the ground plane
- **Floor tiles** provide metric reference
- **High contrast** white TX device is easy to detect

## Quick Start

### 1. Calibration (One-time setup)

Measure 4+ ground plane points and their real-world coordinates:

```python
from camera_tracking import HomographyCalibrator
from session_data import SessionData
import numpy as np

# Load session
session = SessionData.from_directory("path/to/session")
calibration_image = session.get_image_paths()[0]

# Create calibrator
calibrator = HomographyCalibrator(calibration_image)

# Define correspondence points
# Use floor tiles as reference!
image_points = np.array([
    [300, 500],  # Bottom-left tile corner (pixels)
    [900, 500],  # Bottom-right tile corner
    [850, 200],  # Top-right tile corner
    [350, 200],  # Top-left tile corner
], dtype=np.float32)

# Real-world coordinates (meters)
world_points = np.array([
    [0.0, 0.0],   # Origin
    [2.0, 0.0],   # 2m right
    [2.0, 2.5],   # 2m right, 2.5m forward
    [0.0, 2.5],   # 2.5m forward
], dtype=np.float32)

# Compute and save calibration
calibration = calibrator.calibrate(image_points, world_points)
calibration.save(session.session_dir / 'camera_calibration.json')
```

### 2. Track TX Device

Automatically detect TX position in all frames:

```python
from camera_tracking import TXTracker

# Load calibration
calibration = HomographyCalibration.load(
    session.session_dir / 'camera_calibration.json'
)

# Create tracker
tracker = TXTracker(calibration)
tracker.tracking_method = 'blob'  # Good for white rectangular objects

# Track across all images
image_paths = session.get_image_paths()
tracking_results = tracker.track_session(
    image_paths,
    min_area=100,
    max_area=10000,
    save_path=session.session_dir / 'tracking_results.json'
)

print(f"Detection rate: {tracking_results['detection_rate']*100:.1f}%")
```

### 3. Integrate with CSI Data

```python
import json

# Load CSI data
session.load_all_router_batches()
csi_data = session.get_csi_data(averaged=True)

# Load tracking results
with open(session.session_dir / 'tracking_results.json') as f:
    tracking_results = json.load(f)

# Create paired dataset
paired_data = {
    'csi_magnitude': np.abs(csi_data).tolist(),
    'csi_phase': np.angle(csi_data).tolist(),
    'ground_truth_xy': tracking_results['world_positions'],
    'valid': tracking_results['detected']
}

# Save for ML training
with open(session.session_dir / 'paired_csi_groundtruth.json', 'w') as f:
    json.dump(paired_data, f, indent=2)
```

## Methods

### Tracking Methods

The `TXTracker` supports three tracking methods:

#### 1. Blob Detection (Recommended)
- **Best for**: White/bright rectangular objects
- **Pros**: Fast, no manual setup
- **Cons**: Sensitive to lighting

```python
tracker.tracking_method = 'blob'
results = tracker.track_session(images, min_area=100, max_area=10000)
```

#### 2. Template Matching
- **Best for**: Complex backgrounds
- **Pros**: More robust to lighting
- **Cons**: Requires manual template selection

```python
tracker.set_template(first_image, bbox=(x, y, width, height))
tracker.tracking_method = 'template'
results = tracker.track_session(images, threshold=0.7)
```

#### 3. Color Segmentation
- **Best for**: Colored markers
- **Pros**: Can target specific colors
- **Cons**: Requires HSV tuning

```python
tracker.tracking_method = 'color'
results = tracker.track_session(
    images, 
    lower_hsv=(0, 0, 200),    # White lower bound
    upper_hsv=(180, 30, 255)  # White upper bound
)
```

## Examples

Three ways to get started:

### 1. Interactive Notebook (Recommended)
```bash
cd SLAM_testing
jupyter notebook camera_calibration_notebook.ipynb
```

### 2. Python Script
```bash
cd SLAM_testing
python example_camera_tracking.py
```
Edit the script to uncomment examples:
- `example_5_manual_calibration()` - Quick calibration
- `example_2_blob_tracking()` - Track TX device
- `example_4_integrate_with_csi()` - Pair with CSI data

### 3. Standalone Script
```python
# See example_camera_tracking.py for complete examples
```

## Output Files

After running, you'll have:

```
session_XXXXXX/
├── camera_calibration.json          # Homography calibration
├── tracking_results.json            # TX positions (pixel + world coords)
├── paired_csi_groundtruth.json      # CSI + ground truth dataset
└── plots/
    ├── homography_calibration.png   # Calibration visualization
    └── tracking_results.png         # Trajectory + sample detections
```

## Calibration Tips

### Using Floor Tiles

Floor tiles are perfect calibration references:

1. **Identify tile pattern**: Look for grid lines
2. **Measure tile size**: e.g., 30cm × 30cm or 12in × 12in
3. **Pick corner points**: Use intersections of grid lines
4. **Count tiles**: Calculate real-world distances

Example: If tiles are 30cm × 30cm:
- 1 tile = 0.3m
- 4 tiles horizontally = 1.2m
- 6 tiles vertically = 1.8m

### Best Practices

- **More points = better**: Use 6-8 points instead of minimum 4
- **Cover the area**: Select points spread across the visible ground plane
- **Avoid distortion**: Don't pick points near image edges
- **Check reprojection error**: Should be < 0.05m for good calibration

## Validation

### Check Calibration Quality

```python
# Compute reprojection error
world_pred = calibration.pixel_to_world(calibration.image_points)
error = np.sqrt(np.mean((world_pred - calibration.world_points)**2))
print(f"RMSE: {error:.4f} meters")  # Should be < 0.05m
```

### Visualize Results

```python
from camera_tracking import visualize_tracking_results

visualize_tracking_results(
    tracking_results,
    calibration,
    sample_images=image_paths,
    num_samples=6,
    save_path='tracking_visualization.png'
)
```

## Troubleshooting

### Low Detection Rate

If detection rate is low:

1. **Adjust blob parameters**:
   ```python
   tracker.track_session(images, min_area=50, max_area=20000)
   ```

2. **Try color segmentation**:
   ```python
   tracker.tracking_method = 'color'
   # Adjust HSV thresholds for your TX color
   ```

3. **Use template matching**:
   ```python
   tracker.set_template(first_image, bbox=(x, y, w, h))
   ```

### Poor Calibration

If reprojection error is high (> 0.1m):

- Double-check pixel coordinates (use image viewer with coordinates)
- Verify real-world measurements (measure twice!)
- Add more calibration points
- Ensure points are on the same plane (the ground)

### TX Not Detected

- Check lighting (avoid overexposure/underexposure)
- Verify TX is in view and on the ground plane
- Adjust tracking method parameters
- Try a different tracking method

## Advanced Usage

### Interactive Point Selection

Use OpenCV GUI to select points:

```python
calibrator = HomographyCalibrator(calibration_image)
image_points = calibrator.select_points_interactive(num_points=4)
# Then manually enter world coordinates
```

### Custom Detection

Implement your own detection method:

```python
class MyTracker(TXTracker):
    def detect_tx_custom(self, image):
        # Your custom detection logic
        return (cx, cy)  # Return center pixel coordinates
```

### Batch Processing

Process multiple sessions:

```python
from pathlib import Path

sessions = Path("../../data/2025-11-20").glob("session_*")
for session_dir in sessions:
    session = SessionData.from_directory(session_dir)
    # ... calibrate and track ...
```

## API Reference

See docstrings in `camera_tracking.py` for detailed API documentation:

```python
help(HomographyCalibrator)
help(TXTracker)
help(HomographyCalibration)
```

## Requirements

- OpenCV (`cv2`)
- NumPy
- Matplotlib
- Existing session data with camera images

Install with:
```bash
pip install opencv-python numpy matplotlib
```

## Paper Reference

This implementation is based on standard computer vision techniques:

- **Homography**: Hartley & Zisserman, "Multiple View Geometry"
- **Blob Detection**: OpenCV documentation
- **Template Matching**: OpenCV `matchTemplate()`

For camera calibration details, see:
- Zhang (2000), "A Flexible New Technique for Camera Calibration"
