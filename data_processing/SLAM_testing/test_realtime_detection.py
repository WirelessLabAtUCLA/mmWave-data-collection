#!/usr/bin/env python3
"""
Real-time checkerboard detection preview
Shows if checkerboard is detected before capturing images
"""

import cv2
import numpy as np

# Try multiple checkerboard sizes
CHECKERBOARD_SIZES = [
    (6, 7, "7x8 squares (6x7 corners)"),
    (7, 6, "8x7 squares (7x6 corners)"),
    (6, 6, "7x7 squares (6x6 corners)"),
    (5, 6, "6x7 squares (5x6 corners)"),
]

def main():
    print("=" * 70)
    print("REAL-TIME CHECKERBOARD DETECTION TEST")
    print("=" * 70)
    print("\nThis will help you position the checkerboard correctly.")
    print("\nTrying to detect these patterns:")
    for size_x, size_y, desc in CHECKERBOARD_SIZES:
        print(f"  - {desc}")
    
    print("\nControls:")
    print("  SPACE - Capture image if pattern detected")
    print("  Q     - Quit")
    print("\n" + "=" * 70)
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    capture_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        display_frame = frame.copy()
        
        # Try to detect checkerboard with different sizes
        detected = False
        detected_size = None
        detected_corners = None
        
        for size_x, size_y, desc in CHECKERBOARD_SIZES:
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK
            ret_detect, corners = cv2.findChessboardCorners(gray, (size_x, size_y), flags)
            
            if ret_detect:
                # Refine corners
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                
                # Draw the corners
                cv2.drawChessboardCorners(display_frame, (size_x, size_y), corners_refined, ret_detect)
                
                detected = True
                detected_size = desc
                detected_corners = len(corners)
                break
        
        # Add status text
        if detected:
            status_text = f"DETECTED: {detected_size}"
            color = (0, 255, 0)  # Green
            cv2.putText(display_frame, status_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(display_frame, "Press SPACE to capture", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        else:
            status_text = "NOT DETECTED - Adjust position"
            color = (0, 0, 255)  # Red
            cv2.putText(display_frame, status_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(display_frame, "Ensure all corners visible", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        cv2.putText(display_frame, f"Captured: {capture_count}", (10, display_frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Show the frame
        cv2.imshow('Checkerboard Detection Test', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord(' ') and detected:
            # Save the frame
            filename = f"test_capture_{capture_count:03d}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Captured: {filename} - {detected_size}")
            capture_count += 1
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\nCaptured {capture_count} images with detected checkerboard")
    print("If detection worked, update calibrate_webcam.py with the correct size")

if __name__ == "__main__":
    main()
