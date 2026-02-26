#!/usr/bin/env python3
"""
Convert video file to TUM RGB-D dataset format for ORB_SLAM3
Creates a directory with extracted frames and rgb.txt timestamp file
"""

import cv2
import os
import sys
from pathlib import Path

def video_to_tum_dataset(video_path, output_dir, fps_sample=None):
    """
    Extract frames from video and create TUM dataset structure
    
    Args:
        video_path: Path to input video file
        output_dir: Path to output directory
        fps_sample: If set, sample at this FPS (otherwise uses video's native FPS)
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rgb_dir = output_path / "rgb"
    rgb_dir.mkdir(exist_ok=True)
    
    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Cannot open video file {video_path}")
        return
    
    # Get video properties
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Video FPS: {video_fps}")
    print(f"Total frames: {total_frames}")
    
    # Determine frame sampling
    if fps_sample:
        frame_skip = int(video_fps / fps_sample)
        print(f"Sampling at {fps_sample} FPS (every {frame_skip} frames)")
    else:
        frame_skip = 1
        fps_sample = video_fps
        print(f"Using native FPS: {video_fps}")
    
    # Create rgb.txt file
    rgb_txt_path = output_path / "rgb.txt"
    
    frame_count = 0
    saved_count = 0
    
    with open(rgb_txt_path, 'w') as f:
        # Write header (TUM format)
        f.write("# color images\n")
        f.write("# file: 'video_dataset.txt'\n")
        f.write("# timestamp filename\n")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Sample frames according to fps_sample
            if frame_count % frame_skip == 0:
                # Calculate timestamp (in seconds)
                timestamp = frame_count / video_fps
                
                # Save frame
                frame_filename = f"{timestamp:.6f}.png"
                frame_path = rgb_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                
                # Write to rgb.txt: timestamp filename
                f.write(f"{timestamp:.6f} rgb/{frame_filename}\n")
                
                saved_count += 1
                
                if saved_count % 100 == 0:
                    print(f"Processed {saved_count} frames...")
            
            frame_count += 1
    
    cap.release()
    
    print(f"\nDone!")
    print(f"Total frames saved: {saved_count}")
    print(f"Output directory: {output_path}")
    print(f"rgb.txt file: {rgb_txt_path}")
    print(f"\nTo run ORB_SLAM3:")
    print(f"./Examples/Monocular/mono_tum Vocabulary/ORBvoc.txt <path_to_settings.yaml> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python video_to_tum_dataset.py <video_file> <output_dir> [fps_sample]")
        print("Example: python video_to_tum_dataset.py video.mp4 dataset_output 10")
        print("         (samples at 10 FPS if specified, otherwise uses video's native FPS)")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_dir = sys.argv[2]
    fps_sample = float(sys.argv[3]) if len(sys.argv) > 3 else None
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    video_to_tum_dataset(video_path, output_dir, fps_sample)
