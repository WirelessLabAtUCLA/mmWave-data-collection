#!/usr/bin/env python3
"""
Extract sample frames from video for camera calibration at native resolution
"""

import cv2
import sys
from pathlib import Path

def extract_calibration_frames(video_path, output_dir, num_frames=30):
    """Extract evenly spaced frames from video for calibration"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Cannot open video file {video_path}")
        return
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(total_frames // num_frames, 1)
    
    print(f"Video has {total_frames} frames")
    print(f"Extracting {num_frames} frames (every {frame_interval} frames)")
    
    extracted = 0
    frame_idx = 0
    
    while extracted < num_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % frame_interval == 0:
            output_file = output_path / f"calib_{extracted:03d}.png"
            cv2.imwrite(str(output_file), frame)
            print(f"Saved: {output_file.name} (frame {frame_idx})")
            extracted += 1
        
        frame_idx += 1
    
    cap.release()
    print(f"\nExtracted {extracted} frames to {output_path}")
    print(f"Frame resolution: {frame.shape[1]}x{frame.shape[0]}")
    print(f"\nNext steps:")
    print(f"1. Review the frames to ensure they show the checkerboard clearly")
    print(f"2. Delete any blurry or unsuitable frames")
    print(f"3. Run calibration on these frames at native resolution")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_calibration_frames.py <video_file> <output_dir> [num_frames]")
        print("Example: python extract_calibration_frames.py video.mp4 calib_frames 30")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_dir = sys.argv[2]
    num_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    
    extract_calibration_frames(video_path, output_dir, num_frames)
