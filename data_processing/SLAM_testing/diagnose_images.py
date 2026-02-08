#!/usr/bin/env python3
"""
Detailed diagnostic for checkerboard detection issues
"""

import cv2
import numpy as np
import glob
import os

IMAGE_DIR = "calibration_images"

# Get a few sample images
images = sorted(glob.glob(f"{IMAGE_DIR}/*.jpg"))[:5]

if len(images) == 0:
    print(f"Error: No images found in {IMAGE_DIR}/")
    exit(1)

print("=" * 70)
print("CHECKERBOARD DETECTION DIAGNOSTICS")
print("=" * 70)

for img_path in images:
    print(f"\nAnalyzing: {os.path.basename(img_path)}")
    print("-" * 70)
    
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Image statistics
    print(f"  Image size: {gray.shape[1]}x{gray.shape[0]}")
    print(f"  Mean brightness: {np.mean(gray):.1f}")
    print(f"  Std brightness: {np.std(gray):.1f}")
    print(f"  Min/Max: {np.min(gray)}/{np.max(gray)}")
    
    # Try adaptive histogram equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Try different preprocessing
    preprocessed_images = [
        ("Original", gray),
        ("Enhanced (CLAHE)", enhanced),
        ("Gaussian Blur", cv2.GaussianBlur(gray, (5, 5), 0)),
        ("Bilateral Filter", cv2.bilateralFilter(gray, 9, 75, 75)),
    ]
    
    sizes_to_try = [(6, 7), (7, 6), (6, 6), (5, 6), (6, 5)]
    
    found = False
    for preprocess_name, processed_img in preprocessed_images:
        for size in sizes_to_try:
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            ret, corners = cv2.findChessboardCorners(processed_img, size, flags)
            
            if ret:
                print(f"\n  ✓ FOUND with preprocessing: {preprocess_name}")
                print(f"    Size: {size[0]}x{size[1]} inner corners")
                print(f"    Corners detected: {len(corners)}")
                
                # Draw and save
                img_copy = img.copy()
                cv2.drawChessboardCorners(img_copy, size, corners, ret)
                output = f"detected_{os.path.basename(img_path)}"
                cv2.imwrite(output, img_copy)
                print(f"    Saved: {output}")
                found = True
                break
        
        if found:
            break
    
    if not found:
        print(f"\n  ✗ No detection with any preprocessing or size")
        
        # Save enhanced version for manual inspection
        output = f"enhanced_{os.path.basename(img_path)}"
        cv2.imwrite(output, enhanced)
        print(f"    Saved enhanced image: {output}")

print("\n" + "=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
print("\nPossible issues:")
print("  1. Tape covering corners - remove all tape from checkerboard edges")
print("  2. Poor lighting/contrast - ensure even lighting")
print("  3. Blur/motion - keep camera steady")
print("  4. Wrong checkerboard size configuration")
print("  5. Checkerboard not fully visible in frame")
