#!/usr/bin/env python3
"""
Quick test to debug checkerboard detection
"""

import cv2
import numpy as np
import glob
import os

# Test different checkerboard sizes
test_sizes = [
    (6, 7),  # 7x8 squares (most likely based on visual inspection)
    (7, 6),  # 8x7 squares (transposed)
    (6, 6),  # 7x7 squares
    (5, 6),  # 6x7 squares
    (6, 5),  # 7x6 squares
    (8, 6),  # 9x7 squares
    (8, 5),  # 9x6 squares
    (7, 5),  # 8x6 squares
]

IMAGE_DIR = "calibration_images"

# Get first image to test
images = glob.glob(f"{IMAGE_DIR}/*.jpg")
if len(images) == 0:
    print(f"Error: No images found in {IMAGE_DIR}/")
    exit(1)

test_image = images[0]
print(f"Testing with image: {test_image}\n")

img = cv2.imread(test_image)
if img is None:
    print(f"Error: Could not read image {test_image}")
    exit(1)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print(f"Image size: {gray.shape[1]}x{gray.shape[0]} (width x height)")
print(f"Image type: {img.dtype}, channels: {img.shape[2] if len(img.shape) > 2 else 1}\n")

print("Testing different checkerboard sizes:")
print("-" * 60)

for size in test_sizes:
    print(f"\nTrying size {size[0]}x{size[1]} (inner corners)...")
    
    # Try with different flags
    flags_to_try = [
        (None, "default"),
        (cv2.CALIB_CB_ADAPTIVE_THRESH, "adaptive threshold"),
        (cv2.CALIB_CB_NORMALIZE_IMAGE, "normalize image"),
        (cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE, "adaptive + normalize"),
        (cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK, "adaptive + normalize + fast"),
    ]
    
    for flags, desc in flags_to_try:
        ret, corners = cv2.findChessboardCorners(gray, size, flags)
        if ret:
            print(f"  ✓ FOUND with {desc}!")
            print(f"    Detected {len(corners)} corners")
            
            # Draw the corners
            img_copy = img.copy()
            cv2.drawChessboardCorners(img_copy, size, corners, ret)
            output_file = f"test_detection_{size[0]}x{size[1]}.jpg"
            cv2.imwrite(output_file, img_copy)
            print(f"    Saved visualization to: {output_file}")
            break
    else:
        print(f"  ✗ Not detected with any flags")

print("\n" + "=" * 60)
print("\nNow testing all images with detected size...")
