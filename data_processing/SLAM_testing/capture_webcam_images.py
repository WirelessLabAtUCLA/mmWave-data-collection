#!/usr/bin/env python3
"""
Webcam Calibration - Image Capture Script
Press SPACE to capture an image, ESC to quit
"""

import cv2
import os
from datetime import datetime

# Create directory for calibration images
output_dir = "calibration_images"
os.makedirs(output_dir, exist_ok=True)

# Open webcam (0 is usually the default camera)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam")
    exit()

print("=" * 60)
print("WEBCAM CALIBRATION - IMAGE CAPTURE")
print("=" * 60)
print("\nInstructions:")
print("1. Move the checkerboard to different positions and angles")
print("2. Press SPACE to capture an image")
print("3. Capture 20-30 images from different viewpoints")
print("4. Press ESC when done\n")
print("Tips:")
print("- Fill the frame with the checkerboard")
print("- Tilt the board at different angles")
print("- Move it to corners and edges of the frame")
print("- Keep the board flat and well-lit")
print("=" * 60)

image_count = 0

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Error: Failed to capture frame")
        break
    
    # Display the frame
    display_frame = frame.copy()
    cv2.putText(display_frame, f"Images captured: {image_count}", 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(display_frame, "SPACE: Capture | ESC: Quit", 
                (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                0.7, (255, 255, 255), 2)
    
    cv2.imshow('Webcam Calibration - Press SPACE to capture', display_frame)
    
    key = cv2.waitKey(1) & 0xFF
    
    # Press SPACE to capture
    if key == ord(' '):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/calib_{image_count:03d}_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        print(f"✓ Captured image {image_count + 1}: {filename}")
        image_count += 1
    
    # Press ESC to quit
    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()

print(f"\n✓ Capture complete! {image_count} images saved to '{output_dir}/' directory")
print("\nNext step: Run the calibration script with these images")