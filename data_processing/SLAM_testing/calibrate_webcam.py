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
# HELPER FUNCTIONS
# ==============================================================================

def segment_checkerboard(img):
    """
    Perform color segmentation to extract checkerboard region and remove background artifacts
    
    This function:
    1. Converts image to HSV color space for better color segmentation
    2. Detects black squares using HSV thresholding
    3. Uses edge detection to find the paper boundary
    4. Combines these to isolate just the checkerboard pattern
    5. Removes background to make the board more visible
    
    Args:
        img: Input BGR image
        
    Returns:
        Segmented image with background removed
    """
    # Convert to HSV color space and grayscale
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Step 1: Detect black squares (low V value in HSV)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 100])
    mask_black = cv2.inRange(hsv, lower_black, upper_black)
    
    # Step 2: Use edge detection to find checkerboard/paper boundaries
    edges = cv2.Canny(gray, 50, 150)
    
    # Dilate edges to connect nearby edges
    kernel_dilate = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel_dilate, iterations=2)
    
    # Find contours to locate the paper/checkerboard
    contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Create mask for the largest rectangular contour (the paper)
    mask_paper = np.zeros(gray.shape, dtype=np.uint8)
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        cv2.drawContours(mask_paper, [largest_contour], -1, 255, -1)
    
    # Step 3: Combine black squares detection with paper boundary
    mask_combined = cv2.bitwise_and(mask_black, mask_paper)
    
    # Apply morphological operations to clean up noise
    kernel_open = np.ones((3, 3), np.uint8)
    kernel_close = np.ones((7, 7), np.uint8)
    mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_OPEN, kernel_open)
    mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_CLOSE, kernel_close)
    
    # Create result with white background outside paper
    result = img.copy()
    result[mask_paper == 0] = [255, 255, 255]
    
    return result

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES FOR YOUR CHECKERBOARD
# ==============================================================================

# Checkerboard dimensions (number of INNER corners)
# For a 6x7 checkerboard (6 columns x 7 rows of squares), use (5, 6) inner corners
CHECKERBOARD_SIZE = (5, 6)  # (columns, rows) of inner corners

# Size of each square in mm (measure with a ruler!)
SQUARE_SIZE = 20.48# millimeters

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
        
        # Apply color segmentation to remove background artifacts
        img_segmented = segment_checkerboard(img)
        
        # Resize if needed for faster processing
        img_segmented = cv2.resize(img_segmented, (int(img_segmented.shape[1]/2), int(img_segmented.shape[0]/2)))
        gray = cv2.cvtColor(img_segmented, cv2.COLOR_BGR2GRAY)
        
        if img_shape is None:
            img_shape = gray.shape[::-1]  # (width, height)
        
        # Find the checkerboard corners with flags for better detection
        flags = (cv2.CALIB_CB_ADAPTIVE_THRESH + 
                 cv2.CALIB_CB_NORMALIZE_IMAGE + 
                 cv2.CALIB_CB_FAST_CHECK)
        ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, flags)
        
        # If found, add object points and image points
        if ret:
            objpoints.append(objp)
            
            # Refine corner positions to sub-pixel accuracy
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners_refined)
            
            successful_images += 1
            print(f"✓ Image {idx + 1}/{len(images)}: {os.path.basename(fname)} - Checkerboard detected")
            
            # Optional: Draw and display the corners (uncomment to visualize)
            cv2.drawChessboardCorners(img_segmented, checkerboard_size, corners_refined, ret)
            cv2.imshow('Checkerboard', img_segmented)
            cv2.waitKey(100)
        else:
            print(f"✗ Image {idx + 1}/{len(images)}: {os.path.basename(fname)} - Checkerboard NOT detected")
    
    cv2.destroyAllWindows()
    
    print(f"\nSuccessfully processed {successful_images}/{len(images)} images")
    
    if successful_images < 10:
        print("\n⚠ Warning: Less than 10 successful images. Calibration may be inaccurate.")
        print("   Capture more images with the checkerboard clearly visible.")
        return None, None, None, None
    
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