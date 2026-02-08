#!/usr/bin/env python3
"""
Webcam Calibration Script for ORB-SLAM3
Computes camera intrinsic parameters and distortion coefficients
"""

import cv2
import numpy as np
import glob
import yaml
import os

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES FOR YOUR CHECKERBOARD
# ==============================================================================

# Checkerboard dimensions (number of INNER corners)
# For a standard 9x7 checkerboard, use (8, 6) - that's corners, not squares!
CHECKERBOARD_SIZE = (8, 6)  # (columns, rows) of inner corners

# Size of each square in mm (measure with a ruler!)
SQUARE_SIZE = 20.47# millimeters

# Directory containing calibration images
IMAGE_DIR = "calibration_images"

# Output file for calibration results
OUTPUT_YAML = "webcam_calibration.yaml"

# ==============================================================================

def calibrate_camera(images_path, checkerboard_size, square_size):
    """
    Calibrate camera using checkerboard images
    
    Args:
        images_path: Path to directory with calibration images
        checkerboard_size: (columns, rows) of inner corners
        square_size: Size of checkerboard square in mm
    
    Returns:
        Camera matrix, distortion coefficients, and image size
    """
    
    # Termination criteria for corner refinement
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    
    # Prepare object points (0,0,0), (1,0,0), (2,0,0) ... scaled by square_size
    objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:checkerboard_size[0], 
                            0:checkerboard_size[1]].T.reshape(-1, 2)
    objp *= square_size
    
    # Arrays to store object points and image points
    objpoints = []  # 3D points in real world space
    imgpoints = []  # 2D points in image plane
    
    # Get list of calibration images
    images = glob.glob(f"{images_path}/*.jpg") + glob.glob(f"{images_path}/*.png")
    
    if len(images) == 0:
        print(f"Error: No images found in {images_path}/")
        return None, None, None, None
    
    print(f"\nFound {len(images)} calibration images")
    print("Processing images...\n")
    
    successful_images = 0
    img_shape = None
    
    for idx, fname in enumerate(images):
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if img_shape is None:
            img_shape = gray.shape[::-1]  # (width, height)
        
        # Find the checkerboard corners
        ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, None)
        
        # If found, add object points and image points
        if ret:
            objpoints.append(objp)
            
            # Refine corner positions to sub-pixel accuracy
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners_refined)
            
            successful_images += 1
            print(f"✓ Image {idx + 1}/{len(images)}: {os.path.basename(fname)} - Checkerboard detected")
            
            # Optional: Draw and display the corners (uncomment to visualize)
            cv2.drawChessboardCorners(img, checkerboard_size, corners_refined, ret)
            cv2.imshow('Checkerboard', img)
            cv2.waitKey(100)
        else:
            print(f"✗ Image {idx + 1}/{len(images)}: {os.path.basename(fname)} - Checkerboard NOT detected")
    
    cv2.destroyAllWindows()
    
    print(f"\nSuccessfully processed {successful_images}/{len(images)} images")
    
    # if successful_images < 10:
    #     print("\n⚠ Warning: Less than 10 successful images. Calibration may be inaccurate.")
    #     print("   Capture more images with the checkerboard clearly visible.")
    #     return None, None, None, None
    
    # Perform camera calibration
    print("\nPerforming camera calibration...")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_shape, None, None
    )
    
    if not ret:
        print("Calibration failed!")
        return None, None, None, None
    
    # Calculate reprojection error
    mean_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], 
                                          camera_matrix, dist_coeffs)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
        mean_error += error
    
    mean_error /= len(objpoints)
    
    return camera_matrix, dist_coeffs, img_shape, mean_error


def save_calibration_yaml(camera_matrix, dist_coeffs, img_shape, mean_error, output_file):
    """
    Save calibration results in ORB-SLAM3 YAML format
    """
    
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    
    k1 = dist_coeffs[0, 0]
    k2 = dist_coeffs[0, 1]
    p1 = dist_coeffs[0, 2]
    p2 = dist_coeffs[0, 3]
    k3 = dist_coeffs[0, 4] if len(dist_coeffs[0]) > 4 else 0.0
    
    width, height = img_shape
    
    # Create YAML content in ORB-SLAM3 format
    yaml_content = f"""# ORB-SLAM3 Camera Calibration File
# Generated by webcam calibration script
# Reprojection Error: {mean_error:.6f} pixels

%YAML:1.0
---

File.version: "1.0"

Camera.type: "PinHole"

# Camera resolution
Camera.width: {width}
Camera.height: {height}

# Camera intrinsic parameters
Camera1.fx: {fx:.8f}
Camera1.fy: {fy:.8f}
Camera1.cx: {cx:.8f}
Camera1.cy: {cy:.8f}

# Distortion coefficients (radial-tangential model)
Camera1.k1: {k1:.8f}
Camera1.k2: {k2:.8f}
Camera1.p1: {p1:.8f}
Camera1.p2: {p2:.8f}
Camera1.k3: {k3:.8f}

# Camera frames per second (adjust based on your webcam)
Camera.fps: 30

# Color order (0: BGR, 1: RGB)
Camera.RGB: 0

# ORB Extractor parameters
ORBextractor.nFeatures: 1000
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7

# Viewer parameters
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
"""
    
    with open(output_file, 'w') as f:
        f.write(yaml_content)
    
    print(f"\n✓ Calibration file saved: {output_file}")


def main():
    print("=" * 70)
    print("WEBCAM CALIBRATION FOR ORB-SLAM3")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Checkerboard size: {CHECKERBOARD_SIZE[0]}x{CHECKERBOARD_SIZE[1]} inner corners")
    print(f"  Square size: {SQUARE_SIZE} mm")
    print(f"  Image directory: {IMAGE_DIR}/")
    print(f"  Output file: {OUTPUT_YAML}")
    
    # Check if image directory exists
    if not os.path.exists(IMAGE_DIR):
        print(f"\nError: Directory '{IMAGE_DIR}' not found!")
        print("Please run capture_calibration_images.py first to capture images.")
        return
    
    # Calibrate camera
    camera_matrix, dist_coeffs, img_shape, mean_error = calibrate_camera(
        IMAGE_DIR, CHECKERBOARD_SIZE, SQUARE_SIZE
    )
    
    if camera_matrix is None:
        print("\nCalibration failed. Please check your images and configuration.")
        return
    
    # Print results
    print("\n" + "=" * 70)
    print("CALIBRATION RESULTS")
    print("=" * 70)
    print(f"\nReprojection Error: {mean_error:.6f} pixels")
    print("(Good calibration: < 0.5 pixels)")
    
    print("\nCamera Matrix:")
    print(camera_matrix)
    
    print("\nDistortion Coefficients:")
    print(f"k1: {dist_coeffs[0,0]:.8f}")
    print(f"k2: {dist_coeffs[0,1]:.8f}")
    print(f"p1: {dist_coeffs[0,2]:.8f}")
    print(f"p2: {dist_coeffs[0,3]:.8f}")
    print(f"k3: {dist_coeffs[0,4]:.8f}")
    
    print(f"\nImage Size: {img_shape[0]} x {img_shape[1]}")
    
    # Save to YAML
    save_calibration_yaml(camera_matrix, dist_coeffs, img_shape, mean_error, OUTPUT_YAML)
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print(f"\n1. Your calibration file is ready: {OUTPUT_YAML}")
    print("2. Use this file with ORB-SLAM3:")
    print("   ./Examples/Monocular/mono_tum Vocabulary/ORBvoc.txt webcam_calibration.yaml")
    print("\n✓ Calibration complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()