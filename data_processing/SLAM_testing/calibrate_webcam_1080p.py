#!/usr/bin/env python3
"""
Webcam Calibration Script for ORB-SLAM3 at 1080p
Computes camera intrinsic parameters and distortion coefficients
"""

import cv2
import numpy as np
import glob
import yaml
import os

from calibrate_webcam import segment_checkerboard

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES FOR YOUR CHECKERBOARD
# ==============================================================================

# Checkerboard dimensions (number of INNER corners)
# For a 9x6 checkerboard (9 columns x 6 rows of squares), use (8, 5) inner corners
CHECKERBOARD_SIZE = (6, 5)  # (columns, rows) of inner corners - COMMON FOR 9x6 BOARDS

# Size of each square in mm (measure with a ruler!)
SQUARE_SIZE = 20.48  # millimeters - adjust based on your printed checkerboard

# Directory containing calibration images
IMAGE_DIR = "calibration_images_1080p"

# Output file for calibration results
OUTPUT_YAML = "webcam_calibration_1080p.yaml"

# ==============================================================================

def calibrate_camera(images_path, checkerboard_size, square_size):
    """
    Calibrate camera using checkerboard images
    
    Args:
        images_path: Path to directory with calibration images
        checkerboard_size: (columns, rows) of inner corners
        square_size: Size of checkerboard square in mm
        
    Returns:
        ret: RMS reprojection error
        camera_matrix: Camera intrinsic matrix
        dist_coeffs: Distortion coefficients
        rvecs: Rotation vectors
        tvecs: Translation vectors
    """
    # Termination criteria for corner refinement
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    
    # Prepare object points (0,0,0), (1,0,0), (2,0,0) ....,(checkerboard_size[0]-1,checkerboard_size[1]-1,0)
    objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1, 2)
    objp *= square_size
    
    # Arrays to store object points and image points from all images
    objpoints = []  # 3D points in real world space
    imgpoints = []  # 2D points in image plane
    
    # Get list of calibration images
    images = glob.glob(f'{images_path}/*.jpg') + glob.glob(f'{images_path}/*.png')
    
    if not images:
        print(f"Error: No images found in {images_path}")
        return None
    
    print(f"\n{'='*70}")
    print(f"Found {len(images)} calibration images")
    print(f"Checkerboard size: {checkerboard_size[0]}x{checkerboard_size[1]} inner corners")
    print(f"Square size: {square_size} mm")
    print(f"{'='*70}\n")
    
    successful_images = 0
    failed_images = []
    
    for idx, fname in enumerate(images, 1):
        img = cv2.imread(fname)
        img_segmented = segment_checkerboard(img)
        img_segmented = cv2.resize(img_segmented, (int(img_segmented.shape[1]/2), int(img_segmented.shape[0]/2)))
        gray = cv2.cvtColor(img_segmented, cv2.COLOR_BGR2GRAY)
        
        print(f"[{idx}/{len(images)}] Processing: {os.path.basename(fname)}")
        print(f"  Image size: {gray.shape[1]}x{gray.shape[0]}")
        
        # Find the checkerboard corners
        flags = (cv2.CALIB_CB_ADAPTIVE_THRESH + 
            cv2.CALIB_CB_NORMALIZE_IMAGE + 
            cv2.CALIB_CB_FAST_CHECK)
        ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, flags)
        
        # If found, add object points and image points
        if ret:
            objpoints.append(objp)
            
            # Refine corner positions
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners_refined)
            
            print(f"  ✓ Checkerboard detected successfully")
            successful_images += 1
            
            # Optional: Save visualization
            # img_with_corners = cv2.drawChessboardCorners(img.copy(), checkerboard_size, corners_refined, ret)
            # cv2.imwrite(f"{images_path}/detected_{os.path.basename(fname)}", img_with_corners)
        else:
            print(f"  ✗ Failed to detect checkerboard")
            failed_images.append(os.path.basename(fname))
    
    print(f"\n{'='*70}")
    print(f"Successfully processed: {successful_images}/{len(images)} images")
    
    if failed_images:
        print(f"\nFailed images:")
        for fname in failed_images:
            print(f"  - {fname}")
    
    if successful_images < 10:
        print(f"\n⚠ WARNING: Only {successful_images} images successful.")
        print("  You need at least 10-15 good images for accurate calibration.")
        print("  Consider capturing more images or adjusting lighting/focus.")
        return None
    
    print(f"\n{'='*70}")
    print("Running camera calibration...")
    print(f"{'='*70}\n")
    
    # Calibrate camera
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None
    )
    
    return ret, camera_matrix, dist_coeffs, rvecs, tvecs, successful_images


def save_calibration_to_yaml(camera_matrix, dist_coeffs, image_size, reprojection_error, output_file):
    """
    Save calibration parameters in ORB-SLAM3 compatible YAML format
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
    
    calibration_data = f"""%YAML:1.0

#--------------------------------------------------------------------------------------------
# Camera Parameters - Calibrated at 1080p
# Generated by webcam calibration script
# Reprojection Error: {reprojection_error:.6f} pixels
#--------------------------------------------------------------------------------------------
File.version: "1.0"

Camera.type: "PinHole"

# Camera calibration and distortion parameters (OpenCV)
Camera1.fx: {fx:.8f}
Camera1.fy: {fy:.8f}
Camera1.cx: {cx:.8f}
Camera1.cy: {cy:.8f}

Camera1.k1: {k1:.8f}
Camera1.k2: {k2:.8f}
Camera1.p1: {p1:.8f}
Camera1.p2: {p2:.8f}
Camera1.k3: {k3:.8f}

# Camera frames per second
Camera.fps: 10

# Color order of the images (0: BGR, 1: RGB. It is ignored if images are grayscale)
Camera.RGB: 0

# Camera resolution
Camera.width: {image_size[0]}
Camera.height: {image_size[1]}

#--------------------------------------------------------------------------------------------
# ORB Parameters
#--------------------------------------------------------------------------------------------

# ORB Extractor: Number of features per image
ORBextractor.nFeatures: 2000

# ORB Extractor: Scale factor between levels in the scale pyramid
ORBextractor.scaleFactor: 1.2

# ORB Extractor: Number of levels in the scale pyramid
ORBextractor.nLevels: 8

# ORB Extractor: Fast threshold
# Image is divided in a grid. At each cell FAST are extracted imposing a minimum response.
# Firstly we impose iniThFAST. If no corners are detected we impose a lower value minThFAST
# You can lower these values if your images have low contrast
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7

#--------------------------------------------------------------------------------------------
# Viewer Parameters
#--------------------------------------------------------------------------------------------
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
        f.write(calibration_data)
    
    print(f"\n✓ Calibration saved to: {output_file}")


def main():
    """Main calibration routine"""
    print("\n" + "="*70)
    print("WEBCAM CALIBRATION FOR ORB-SLAM3 (1080p)")
    print("="*70)
    
    # Check if image directory exists
    if not os.path.exists(IMAGE_DIR):
        print(f"\nError: Image directory '{IMAGE_DIR}' not found!")
        print(f"\nPlease:")
        print(f"  1. Run capture_webcam_images_1080p.py to capture calibration images")
        print(f"  2. Make sure you have at least 20 images")
        print(f"  3. Then run this script again")
        return
    
    # Run calibration
    result = calibrate_camera(IMAGE_DIR, CHECKERBOARD_SIZE, SQUARE_SIZE)
    
    if result is None:
        print("\n✗ Calibration failed!")
        return
    
    ret, camera_matrix, dist_coeffs, rvecs, tvecs, num_images = result
    
    # Get image size from first image
    test_img = cv2.imread(glob.glob(f'{IMAGE_DIR}/*.jpg')[0])
    image_size = (test_img.shape[1], test_img.shape[0])
    
    # Print calibration results
    print("="*70)
    print("CALIBRATION RESULTS")
    print("="*70)
    print(f"\nRMS Reprojection Error: {ret:.6f} pixels")
    print(f"  (Lower is better; < 0.5 pixels is excellent, < 1.0 is good)")
    
    print(f"\nCamera Matrix (K):")
    print(f"  fx: {camera_matrix[0, 0]:.2f}")
    print(f"  fy: {camera_matrix[1, 1]:.2f}")
    print(f"  cx: {camera_matrix[0, 2]:.2f}")
    print(f"  cy: {camera_matrix[1, 2]:.2f}")
    
    print(f"\nDistortion Coefficients:")
    print(f"  k1: {dist_coeffs[0, 0]:.6f}")
    print(f"  k2: {dist_coeffs[0, 1]:.6f}")
    print(f"  p1: {dist_coeffs[0, 2]:.6f}")
    print(f"  p2: {dist_coeffs[0, 3]:.6f}")
    print(f"  k3: {dist_coeffs[0, 4]:.6f}")
    
    print(f"\nImage Resolution: {image_size[0]}x{image_size[1]}")
    print(f"Number of calibration images used: {num_images}")
    
    # Save to YAML
    save_calibration_to_yaml(camera_matrix, dist_coeffs, image_size, ret, OUTPUT_YAML)
    
    print("\n" + "="*70)
    print("✓ CALIBRATION COMPLETE!")
    print("="*70)
    print(f"\nYou can now use {OUTPUT_YAML} with ORB-SLAM3")
    print("\n")


if __name__ == "__main__":
    main()
