# Camera Calibration at 1080p for ORB-SLAM3

## Step-by-Step Guide

### Prerequisites
1. **Print a checkerboard pattern**:
   - Download and print: https://markhedleyjones.com/projects/calibration-checkerboard-collection
   - Recommended: 9x6 checkerboard (8x5 inner corners)
   - Mount it on a flat, rigid board (cardboard is fine)
   - Measure the square size with a ruler and update `SQUARE_SIZE` in the script

   **OR** display a checkerboard on a tablet/monitor

### Step 1: Capture Calibration Images

```bash
cd /home/kanishka/Projects/mmWave-data-collection/data_processing/SLAM_testing
uv run capture_webcam_images_1080p.py
```

**Tips for capturing:**
- Capture 25-30 images
- Move the checkerboard to different positions:
  - Center, corners, edges
  - Close to camera, far from camera
  - Tilted at different angles
- Keep the checkerboard flat and well-lit
- Avoid motion blur - hold steady when pressing SPACE
- Make sure all checkerboard corners are visible

### Step 2: Update Checkerboard Configuration

Edit `calibrate_webcam_1080p.py` and update these values:

```python
# If you have a 9x6 checkerboard (9 cols x 6 rows of squares)
CHECKERBOARD_SIZE = (8, 5)  # Inner corners = (9-1, 6-1)

# Measure a square with a ruler!
SQUARE_SIZE = 25.0  # millimeters - UPDATE THIS!
```

### Step 3: Run Calibration

```bash
cd /home/kanishka/Projects/mmWave-data-collection/data_processing/SLAM_testing
uv run calibrate_webcam_1080p.py
```

This will:
- Process all images in `calibration_images_1080p/`
- Compute camera parameters
- Save results to `webcam_calibration_1080p.yaml`

**What to look for:**
- At least 20 images should be successfully processed
- RMS Reprojection Error should be < 1.0 pixels (< 0.5 is excellent)

### Step 4: Use with ORB-SLAM3

Once calibrated, convert your video and run SLAM:

```bash
# Convert video to TUM format (if not already done)
cd /home/kanishka/Projects/mmWave-data-collection/data_processing/SLAM_testing
uv run video_to_tum_dataset.py \
  ../../data/videos/session_20260208_121146.mp4 \
  ../../data/slam_dataset/session_20260208_1080p \
  10

# Run ORB-SLAM3 with the new calibration
cd /home/kanishka/Projects/ORB_SLAM3
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
./Examples/Monocular/mono_tum \
  Vocabulary/ORBvoc.txt \
  /home/kanishka/Projects/mmWave-data-collection/data_processing/SLAM_testing/webcam_calibration_1080p.yaml \
  /home/kanishka/Projects/mmWave-data-collection/data/slam_dataset/session_20260208_1080p
```

## Troubleshooting

**"Failed to detect checkerboard"**
- Check CHECKERBOARD_SIZE matches your pattern
- Ensure good lighting
- Make sure checkerboard is flat and all corners visible
- Try different angles/distances

**High reprojection error (> 1.0 pixels)**
- Some images may be blurry - delete them and recalibrate
- Check SQUARE_SIZE is correct
- Capture more images with better variety

**ORB-SLAM3 still fails to track**
- Check the video quality (lighting, focus, motion speed)
- Try slower camera movements
- Ensure the scene has enough texture/features
- Lower FPS when converting video (try 5 FPS instead of 10)
