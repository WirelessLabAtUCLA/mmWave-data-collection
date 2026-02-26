#!/usr/bin/env python3
"""
Webcam Calibration - Image Capture Script at 1080p
Press SPACE to capture an image, ESC to quit
"""

import cv2
import os
from datetime import datetime

# Create directory for calibration images
output_dir = "calibration_images_1080p"
os.makedirs(output_dir, exist_ok=True)

# Open webcam (0 is usually the default camera)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam")
    exit()

# Set resolution to 1920x1080
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Verify resolution
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print("=" * 60)
print("WEBCAM CALIBRATION - IMAGE CAPTURE (1080p)")
print("=" * 60)
print(f"\nCamera resolution: {actual_width}x{actual_height}")
if actual_width != 1920 or actual_height != 1080:
    print("WARNING: Could not set 1920x1080. Using available resolution.")
print("\nInstructions:")
print("1. Print or display a checkerboard pattern (9x6 or similar)")
print("2. Move the checkerboard to different positions and angles")
print("3. Press SPACE to capture an image")
print("4. Capture 20-30 images from different viewpoints")
print("5. Press ESC when done\n")
print("Tips:")
print("- Fill the frame with the checkerboard")
print("- Tilt the board at different angles")
print("- Move it to corners and edges of the frame")
print("- Keep the board flat and well-lit")
print("- Avoid motion blur - hold steady when capturing")
print("=" * 60)

image_count = 0

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Error: Failed to capture frame")
        break
    
    # Display the frame (scaled down for display if too large)
    display_frame = frame.copy()
    display_scale = 0.7  # Scale down for display
    display_frame = cv2.resize(display_frame, None, fx=display_scale, fy=display_scale)
    
    cv2.putText(display_frame, f"Images captured: {image_count}", 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(display_frame, "SPACE: Capture | ESC: Quit", 
                (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(display_frame, f"Resolution: {actual_width}x{actual_height}", 
                (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
    cv2.imshow('Webcam Calibration (1080p)', display_frame)
    
    key = cv2.waitKey(1) & 0xFF
    
    if key == 27:  # ESC key
        print("\nCapture completed!")
        break
    elif key == 32:  # SPACE key
        # Save the full resolution image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/calib_{image_count:03d}_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        print(f"Captured: {filename}")
        image_count += 1

cap.release()
cv2.destroyAllWindows()

print(f"\nTotal images captured: {image_count}")
print(f"Images saved to: {output_dir}/")
if image_count >= 20:
    print("\n✓ Good! You have enough images for calibration.")
    print(f"Next step: Run the calibration script on {output_dir}/")
else:
    print(f"\n⚠ Warning: You should capture at least 20 images (you have {image_count})")
