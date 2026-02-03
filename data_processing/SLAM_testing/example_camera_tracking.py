"""
Example script demonstrating camera-based ground truth tracking.

This script shows the complete workflow:
1. Calibrate camera-to-ground-plane homography
2. Track TX device across video frames
3. Visualize and validate results
"""

import sys
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from camera_tracking import (
    HomographyCalibrator, 
    HomographyCalibration,
    TXTracker,
    visualize_tracking_results
)
from session_data import SessionData


def example_1_calibration_workflow():
    """Example 1: Complete calibration workflow with interactive point selection."""
    
    print("=" * 70)
    print("EXAMPLE 1: Interactive Homography Calibration")
    print("=" * 70)
    
    # Load a session
    session_dir = Path("../../data/2025-11-25/session_122307")
    session = SessionData.from_directory(session_dir)
    
    # Get first image for calibration
    image_paths = session.get_image_paths()
    calibration_image = image_paths[0]
    
    print(f"\nUsing calibration image: {calibration_image}")
    
    # Create calibrator
    calibrator = HomographyCalibrator(calibration_image)
    
    # Interactive point selection
    print("\n--- STEP 1: Select calibration points ---")
    print("TIP: Use the floor tiles as reference!")
    print("      Click on 4+ corner points that you know the real-world coordinates of")
    
    # For this example, we'll simulate point selection
    image_points = calibrator.select_points_interactive(num_points=4)
    
    # Example: Manually specify points (you should use interactive selection)
    # These are example coordinates - replace with your actual measurements!
    print("\nFor this example, we'll use pre-defined points.")
    print("In practice, you should use calibrator.select_points_interactive()")
    
    # Example points (replace with actual calibration!)
    # Format: pixel coordinates [x, y] and corresponding world coordinates [x_meters, y_meters]
    # image_points = np.array([
    #     [320, 480],   # Point 0: bottom-left tile corner
    #     [960, 480],   # Point 1: bottom-right tile corner
    #     [960, 240],   # Point 2: top-right tile corner
    #     [320, 240],   # Point 3: top-left tile corner
    # ], dtype=np.float32)
    
    # World coordinates in meters (example: 2m x 2m square on the ground)
    world_points = np.array([
        [0.0, 0.0],   # Point 0: origin
        [2.0, 0.0],   # Point 1: 2 meters right
        [2.0, 2.0],   # Point 2: 2 meters right, 2 meters forward
        [0.0, 2.0],   # Point 3: 2 meters forward
    ], dtype=np.float32)
    
    print(f"\nImage points (pixels):\n{image_points}")
    print(f"\nWorld points (meters):\n{world_points}")
    
    # Compute homography
    print("\n--- STEP 2: Compute homography ---")
    calibration = calibrator.calibrate(image_points, world_points)
    
    # Visualize calibration
    print("\n--- STEP 3: Visualize calibration ---")
    save_path = session.get_save_plot_path() / 'homography_calibration.png'
    calibrator.visualize_calibration(calibration, save_path=save_path)
    
    # Save calibration
    calib_file = session.session_dir / 'camera_calibration.json'
    calibration.save(calib_file)
    
    print("\n✓ Calibration complete!")
    print(f"  Calibration saved to: {calib_file}")
    print(f"  Visualization saved to: {save_path}")
    
    return calibration, session


def example_2_blob_tracking():
    """Example 2: Track TX using blob detection (for white rectangular objects)."""
    
    print("\n" + "=" * 70)
    print("EXAMPLE 2: TX Tracking with Blob Detection")
    print("=" * 70)
    
    # Load calibration and session
    session_dir = Path("../../data/2025-11-20/session_135938")
    session = SessionData.from_directory(session_dir)
    calib_file = session.session_dir / 'camera_calibration.json'
    
    if not calib_file.exists():
        print("\nNo calibration found. Running calibration first...")
        calibration, session = example_1_calibration_workflow()
    else:
        print(f"\nLoading calibration from: {calib_file}")
        calibration = HomographyCalibration.load(calib_file)
    
    # Create tracker with blob detection
    print("\n--- STEP 1: Initialize tracker ---")
    tracker = TXTracker(calibration)
    tracker.tracking_method = 'blob'
    
    print("Tracking method: Blob Detection")
    print("  - Detects white rectangular objects")
    print("  - Works well for simple, high-contrast scenes")
    
    # Track across all images
    print("\n--- STEP 2: Track TX across session ---")
    image_paths = session.get_image_paths()
    
    tracking_results = tracker.track_session(
        image_paths,
        min_area=100,      # Minimum blob area in pixels
        max_area=10000,    # Maximum blob area in pixels
        save_path=session.session_dir / 'tracking_results_blob.json'
    )
    
    # Visualize results
    print("\n--- STEP 3: Visualize tracking results ---")
    save_path = session.get_save_plot_path() / 'tracking_results_blob.png'
    visualize_tracking_results(
        tracking_results,
        calibration,
        sample_images=image_paths,
        num_samples=6,
        save_path=save_path
    )
    
    print("\n✓ Blob tracking complete!")
    print(f"  Results saved to: {session.session_dir / 'tracking_results_blob.json'}")
    print(f"  Visualization saved to: {save_path}")
    
    return tracking_results


def example_3_template_tracking():
    """Example 3: Track TX using template matching (more robust)."""
    
    print("\n" + "=" * 70)
    print("EXAMPLE 3: TX Tracking with Template Matching")
    print("=" * 70)
    
    # Load calibration and session
    session_dir = Path("../../data/2025-11-20/session_135938")
    session = SessionData.from_directory(session_dir)
    calib_file = session.session_dir / 'camera_calibration.json'
    
    if not calib_file.exists():
        print("\nNo calibration found. Run example_1_calibration_workflow() first.")
        return None
    
    print(f"\nLoading calibration from: {calib_file}")
    calibration = HomographyCalibration.load(calib_file)
    
    # Create tracker
    print("\n--- STEP 1: Set TX template ---")
    tracker = TXTracker(calibration)
    
    # For template matching, you need to provide a template image and bbox
    # Example: manually specify TX location in first frame
    image_paths = session.get_image_paths()
    template_image = image_paths[0]
    
    print(f"Using template from: {template_image}")
    print("\nIn practice, you should:")
    print("  1. Open the first image")
    print("  2. Identify the TX device")
    print("  3. Specify its bounding box: (x, y, width, height)")
    
    # Example bbox (replace with actual TX location!)
    # Format: (x, y, width, height) in pixels
    tx_bbox = (600, 350, 80, 60)  # Example: TX at pixel (600, 350), 80x60 size
    
    print(f"\nTemplate bbox: {tx_bbox}")
    # Uncomment to actually set template:
    # tracker.set_template(template_image, tx_bbox)
    
    print("\nNote: Template matching requires manual TX location in first frame.")
    print("      Blob detection is recommended for automated tracking.")
    
    return None


def example_4_integrate_with_csi():
    """Example 4: Integrate camera ground truth with CSI/FTM data."""
    
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Integrate Camera Ground Truth with mmWave Data")
    print("=" * 70)
    
    # Load session
    session_dir = Path("../../data/2025-11-20/session_135938")
    session = SessionData.from_directory(session_dir)
    
    # Load tracking results
    tracking_file = session.session_dir / 'tracking_results_blob.json'
    
    if not tracking_file.exists():
        print("\nNo tracking results found. Run example_2_blob_tracking() first.")
        return None
    
    import json
    with open(tracking_file, 'r') as f:
        tracking_results = json.load(f)
    
    # Load CSI data
    print("\n--- Loading CSI data ---")
    session.load_all_router_batches()
    csi_data = session.get_csi_data(averaged=True)
    
    print(f"CSI data shape: {csi_data.shape}")
    print(f"Number of measurements: {len(csi_data)}")
    
    # Align with camera data
    world_positions = np.array(tracking_results['world_positions'])
    detected = np.array(tracking_results['detected'])
    
    print(f"\nCamera ground truth:")
    print(f"  Total frames: {len(world_positions)}")
    print(f"  Detected frames: {np.sum(detected)}")
    print(f"  Detection rate: {np.mean(detected)*100:.1f}%")
    
    # Match up CSI measurements with camera frames
    # Note: Your session might have multiple CSI measurements per image
    # You need to determine the correspondence based on your data collection setup
    
    print("\n--- Data alignment ---")
    print("Important: You need to align CSI measurements with camera frames.")
    print("This depends on your data collection timing:")
    print("  - If 1 image per CSI batch: direct correspondence")
    print("  - If multiple CSI per image: repeat ground truth positions")
    print("  - If asynchronous: use timestamps for interpolation")
    
    # Example: assuming 1 image per data point (1 CSI batch)
    num_data_points = len(session.data_points)
    
    if len(world_positions) == num_data_points:
        print(f"\n✓ Data aligned: {num_data_points} camera frames match {num_data_points} CSI batches")
        
        # Now you have paired data:
        # - csi_data[i] corresponds to world_positions[i]
        # This can be used for ML training, beamforming analysis, etc.
        
        # Example: save paired data
        paired_data = {
            'csi_magnitude': np.abs(csi_data).tolist(),
            'csi_phase': np.angle(csi_data).tolist(),
            'ground_truth_xy': world_positions.tolist(),
            'valid': detected.tolist()
        }
        
        output_file = session.session_dir / 'paired_csi_groundtruth.json'
        with open(output_file, 'w') as f:
            json.dump(paired_data, f, indent=2)
        
        print(f"  Paired data saved to: {output_file}")
    else:
        print(f"\n⚠ Data size mismatch:")
        print(f"  Camera frames: {len(world_positions)}")
        print(f"  CSI batches: {num_data_points}")
        print(f"  You need to determine the correct correspondence")
    
    return world_positions, csi_data


def example_5_manual_calibration():
    """Example 5: Quick manual calibration without interactive selection."""
    
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Quick Manual Calibration")
    print("=" * 70)
    
    session_dir = Path("../../data/2025-11-20/session_135938")
    session = SessionData.from_directory(session_dir)
    
    calibration_image = session.get_image_paths()[0]
    calibrator = HomographyCalibrator(calibration_image)
    
    print("\nQUICK START GUIDE:")
    print("-" * 70)
    print("1. Open your calibration image in an image viewer")
    print("2. Identify 4+ points on the ground plane with known coordinates")
    print("   (e.g., floor tile corners)")
    print("3. Measure the pixel coordinates (x, y) of each point")
    print("4. Measure or estimate the real-world coordinates (x_meters, y_meters)")
    print("5. Enter them below:")
    
    # Example calibration points (REPLACE WITH YOUR ACTUAL MEASUREMENTS!)
    print("\n--- Example calibration (REPLACE WITH YOUR VALUES!) ---")
    
    image_points = np.array([
        [300, 500],   # Bottom-left corner
        [900, 500],   # Bottom-right corner  
        [850, 200],   # Top-right corner
        [350, 200],   # Top-left corner
    ], dtype=np.float32)
    
    # Real-world coordinates (example: 2m x 2m area)
    # Origin at bottom-left, X=right, Y=forward
    world_points = np.array([
        [0.0, 0.0],   # Bottom-left: origin
        [2.0, 0.0],   # Bottom-right: 2m to the right
        [2.0, 2.5],   # Top-right: 2m right, 2.5m forward
        [0.0, 2.5],   # Top-left: 2.5m forward
    ], dtype=np.float32)
    
    print("\nImage points (pixels):")
    for i, pt in enumerate(image_points):
        print(f"  Point {i}: ({pt[0]:.0f}, {pt[1]:.0f})")
    
    print("\nWorld points (meters):")
    for i, pt in enumerate(world_points):
        print(f"  Point {i}: ({pt[0]:.1f}, {pt[1]:.1f})")
    
    # Compute homography
    calibration = calibrator.calibrate(image_points, world_points)
    
    # Test a point
    print("\n--- Test the calibration ---")
    test_pixel = np.array([[640, 360]])  # Center of image
    test_world = calibration.pixel_to_world(test_pixel)
    print(f"Pixel (640, 360) -> World ({test_world[0, 0]:.2f}, {test_world[0, 1]:.2f}) meters")
    
    # Save
    calib_file = session.session_dir / 'camera_calibration.json'
    calibration.save(calib_file)
    
    # Visualize
    save_path = session.get_save_plot_path() / 'calibration_manual.png'
    calibrator.visualize_calibration(calibration, save_path=save_path)
    
    print(f"\n✓ Calibration saved to: {calib_file}")
    print(f"✓ Visualization saved to: {save_path}")
    
    return calibration


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "CAMERA GROUND TRUTH TRACKING" + " " * 25 + "║")
    print("║" + " " * 20 + "Example Workflows" + " " * 31 + "║")
    print("╚" + "═" * 68 + "╝")
    
    print("\nThis script demonstrates camera-based ground truth extraction.")
    print("\nAvailable examples:")
    print("  1. example_1_calibration_workflow() - Interactive calibration")
    print("  2. example_2_blob_tracking() - Automatic TX tracking (blob detection)")
    print("  3. example_3_template_tracking() - Template-based tracking")
    print("  4. example_4_integrate_with_csi() - Pair with CSI/FTM data")
    print("  5. example_5_manual_calibration() - Quick manual calibration")
    
    print("\n" + "-" * 70)
    print("RECOMMENDED WORKFLOW:")
    print("-" * 70)
    print("Step 1: Run example_5_manual_calibration()")
    print("        - Measure calibration points from your camera image")
    print("        - Use floor tiles as reference for metric scale")
    print("")
    print("Step 2: Run example_2_blob_tracking()")
    print("        - Automatically track TX device across all frames")
    print("        - Generates world coordinates for each frame")
    print("")
    print("Step 3: Run example_4_integrate_with_csi()")
    print("        - Pair camera ground truth with CSI measurements")
    print("        - Ready for ML training or beamforming analysis")
    print("-" * 70)
    
    # Uncomment to run examples:
    example_1_calibration_workflow()
    # calibration = example_5_manual_calibration()
    # tracking_results = example_2_blob_tracking()
    # world_pos, csi_data = example_4_integrate_with_csi()
    
    print("\nUncomment the examples above to run them!")
