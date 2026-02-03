"""
Camera-based ground truth tracking using homography transformation.

This module provides tools for:
1. Calibrating camera-to-ground-plane homography using floor reference points
2. Tracking TX device position in camera frames
3. Converting pixel coordinates to real-world XY coordinates
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import json
import matplotlib.pyplot as plt
from dataclasses import dataclass, asdict


@dataclass
class HomographyCalibration:
    """Stores homography calibration data."""
    image_points: np.ndarray  # Nx2 array of pixel coordinates
    world_points: np.ndarray  # Nx2 array of real-world coordinates (meters)
    homography_matrix: np.ndarray  # 3x3 homography matrix
    image_shape: Tuple[int, int]  # (height, width)
    calibration_image_path: Optional[str] = None
    
    def save(self, filepath: Path):
        """Save calibration to JSON file."""
        data = {
            'image_points': self.image_points.tolist(),
            'world_points': self.world_points.tolist(),
            'homography_matrix': self.homography_matrix.tolist(),
            'image_shape': self.image_shape,
            'calibration_image_path': self.calibration_image_path
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved calibration to: {filepath}")
    
    @classmethod
    def load(cls, filepath: Path) -> 'HomographyCalibration':
        """Load calibration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(
            image_points=np.array(data['image_points']),
            world_points=np.array(data['world_points']),
            homography_matrix=np.array(data['homography_matrix']),
            image_shape=tuple(data['image_shape']),
            calibration_image_path=data.get('calibration_image_path')
        )
    
    def pixel_to_world(self, pixel_points: np.ndarray) -> np.ndarray:
        """Transform pixel coordinates to world coordinates.
        
        Args:
            pixel_points: Nx2 array of pixel coordinates (x, y)
        
        Returns:
            Nx2 array of world coordinates (x, y) in meters
        """
        # Ensure input is 2D
        pixel_points = np.array(pixel_points)
        if pixel_points.ndim == 1:
            pixel_points = pixel_points.reshape(1, -1)
        
        # Convert to homogeneous coordinates
        pixel_points_h = np.column_stack([pixel_points, np.ones(len(pixel_points))])
        
        # Apply homography
        world_points_h = (self.homography_matrix @ pixel_points_h.T).T
        
        # Convert back from homogeneous coordinates
        world_points = world_points_h[:, :2] / world_points_h[:, 2:]
        
        return world_points


class HomographyCalibrator:
    """Interactive tool for calibrating camera-to-ground-plane homography."""
    
    def __init__(self, image_path: Path):
        """Initialize calibrator with an image.
        
        Args:
            image_path: Path to calibration image
        """
        self.image_path = Path(image_path)
        self.image = cv2.imread(str(image_path))
        if self.image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        self.image_rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        self.image_points = []
        self.world_points = []
        
    def select_points_interactive(self, num_points: int = 4) -> List[Tuple[float, float]]:
        """Interactively select calibration points on the image.
        
        Args:
            num_points: Number of points to select (minimum 4)
        
        Returns:
            List of selected pixel coordinates
        """
        print(f"\nCalibration Mode: Select {num_points} points on the ground plane")
        print("Instructions:")
        print("  - Click on known ground plane points (e.g., floor tile corners)")
        print("  - Press 'r' to reset and start over")
        print("  - Press 'q' when done selecting points")
        print(f"  - You need at least {num_points} points")
        
        # Create a copy for drawing
        display_image = self.image_rgb.copy()
        selected_points = []
        
        def mouse_callback(event, x, y, flags, param):
            nonlocal display_image, selected_points
            
            if event == cv2.EVENT_LBUTTONDOWN:
                selected_points.append((x, y))
                
                # Redraw image with all points
                display_image = self.image_rgb.copy()
                for i, (px, py) in enumerate(selected_points):
                    cv2.circle(display_image, (px, py), 5, (255, 0, 0), -1)
                    cv2.putText(display_image, f"P{i}", (px + 10, py - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                # Draw connecting lines
                if len(selected_points) > 1:
                    for i in range(len(selected_points) - 1):
                        cv2.line(display_image, selected_points[i], selected_points[i+1],
                               (0, 255, 0), 2)
                
                cv2.imshow('Calibration', cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR))
        
        cv2.namedWindow('Calibration', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Calibration', 1280, 720)
        cv2.imshow('Calibration', cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR))
        cv2.setMouseCallback('Calibration', mouse_callback)
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('r'):
                # Reset
                selected_points = []
                display_image = self.image_rgb.copy()
                cv2.imshow('Calibration', cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR))
                print("Reset - select points again")
            
            elif key == ord('q'):
                if len(selected_points) >= num_points:
                    break
                else:
                    print(f"Need at least {num_points} points. Currently have {len(selected_points)}")
        
        cv2.destroyAllWindows()
        return selected_points
    
    def calibrate(self, image_points: np.ndarray, world_points: np.ndarray) -> HomographyCalibration:
        """Compute homography from corresponding points.
        
        Args:
            image_points: Nx2 array of pixel coordinates
            world_points: Nx2 array of world coordinates in meters
        
        Returns:
            HomographyCalibration object
        """
        if len(image_points) < 4 or len(world_points) < 4:
            raise ValueError("Need at least 4 point correspondences")
        
        if len(image_points) != len(world_points):
            raise ValueError("Number of image points must match number of world points")
        
        # Compute homography
        H, status = cv2.findHomography(image_points, world_points, cv2.RANSAC, 5.0)
        
        if H is None:
            raise ValueError("Failed to compute homography")
        
        # Store calibration
        calibration = HomographyCalibration(
            image_points=image_points,
            world_points=world_points,
            homography_matrix=H,
            image_shape=self.image.shape[:2],
            calibration_image_path=str(self.image_path)
        )
        
        # Compute reprojection error
        world_points_pred = calibration.pixel_to_world(image_points)
        error = np.sqrt(np.mean((world_points_pred - world_points)**2))
        print(f"\nCalibration complete!")
        print(f"Reprojection RMSE: {error:.4f} meters")
        
        return calibration
    
    def visualize_calibration(self, calibration: HomographyCalibration, 
                             save_path: Optional[Path] = None):
        """Visualize calibration points and reprojection.
        
        Args:
            calibration: HomographyCalibration object
            save_path: Optional path to save visualization
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Left: Image with calibration points
        ax1.imshow(self.image_rgb)
        ax1.scatter(calibration.image_points[:, 0], calibration.image_points[:, 1],
                   c='red', s=100, marker='x', linewidths=3, label='Calibration points')
        
        for i, (x, y) in enumerate(calibration.image_points):
            ax1.annotate(f'P{i}', (x, y), xytext=(10, -10), 
                        textcoords='offset points', color='red', fontsize=12)
        
        ax1.set_title('Image Points (Pixels)', fontsize=14)
        ax1.legend()
        ax1.axis('off')
        
        # Right: World coordinates
        ax2.scatter(calibration.world_points[:, 0], calibration.world_points[:, 1],
                   c='blue', s=100, marker='o', label='Ground truth')
        
        # Compute reprojection
        world_points_pred = calibration.pixel_to_world(calibration.image_points)
        ax2.scatter(world_points_pred[:, 0], world_points_pred[:, 1],
                   c='red', s=100, marker='x', linewidths=3, label='Reprojected')
        
        # Draw error vectors
        for i in range(len(calibration.world_points)):
            ax2.plot([calibration.world_points[i, 0], world_points_pred[i, 0]],
                    [calibration.world_points[i, 1], world_points_pred[i, 1]],
                    'k--', alpha=0.5)
            ax2.annotate(f'P{i}', calibration.world_points[i], xytext=(0.05, 0.05),
                        textcoords='offset points', color='blue', fontsize=12)
        
        ax2.set_xlabel('X (meters)', fontsize=12)
        ax2.set_ylabel('Y (meters)', fontsize=12)
        ax2.set_title('World Coordinates (Meters)', fontsize=14)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.axis('equal')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved calibration visualization to: {save_path}")
        else:
            plt.show()
        
        plt.close()


class TXTracker:
    """Tracks TX device position in camera frames."""
    
    def __init__(self, calibration: HomographyCalibration):
        """Initialize tracker with calibration.
        
        Args:
            calibration: HomographyCalibration object
        """
        self.calibration = calibration
        self.template = None
        self.tracking_method = 'blob'  # 'blob', 'template', or 'color'
    
    def set_template(self, image_path: Path, bbox: Tuple[int, int, int, int]):
        """Set template for template matching.
        
        Args:
            image_path: Path to image containing the TX
            bbox: Bounding box (x, y, width, height) around TX
        """
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        x, y, w, h = bbox
        self.template = image[y:y+h, x:x+w]
        self.tracking_method = 'template'
        print(f"Template set from {image_path}")
        print(f"Template size: {w}x{h}")
    
    def detect_tx_blob(self, image: np.ndarray, 
                       min_area: int = 100, 
                       max_area: int = 10000) -> Optional[Tuple[float, float]]:
        """Detect TX using blob detection (for white rectangular object).
        
        Args:
            image: Input image (BGR)
            min_area: Minimum blob area in pixels
            max_area: Maximum blob area in pixels
        
        Returns:
            (x, y) pixel coordinates of blob center, or None if not found
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Threshold to detect white objects
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Filter by area and find largest
        valid_contours = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
        
        if not valid_contours:
            return None
        
        # Get the largest valid contour
        largest_contour = max(valid_contours, key=cv2.contourArea)
        
        # Compute centroid
        M = cv2.moments(largest_contour)
        if M['m00'] == 0:
            return None
        
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        
        return (cx, cy)
    
    def detect_tx_template(self, image: np.ndarray, 
                          threshold: float = 0.7) -> Optional[Tuple[float, float]]:
        """Detect TX using template matching.
        
        Args:
            image: Input image (BGR)
            threshold: Matching threshold (0-1)
        
        Returns:
            (x, y) pixel coordinates of match center, or None if not found
        """
        if self.template is None:
            raise ValueError("Template not set. Call set_template() first.")
        
        # Template matching
        result = cv2.matchTemplate(image, self.template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val < threshold:
            return None
        
        # Compute center of matched region
        h, w = self.template.shape[:2]
        cx = max_loc[0] + w / 2
        cy = max_loc[1] + h / 2
        
        return (cx, cy)
    
    def detect_tx_color(self, image: np.ndarray,
                       lower_hsv: Tuple[int, int, int] = (0, 0, 200),
                       upper_hsv: Tuple[int, int, int] = (180, 30, 255)) -> Optional[Tuple[float, float]]:
        """Detect TX using color-based segmentation.
        
        Args:
            image: Input image (BGR)
            lower_hsv: Lower HSV threshold for white/light objects
            upper_hsv: Upper HSV threshold for white/light objects
        
        Returns:
            (x, y) pixel coordinates of detected center, or None if not found
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create mask
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        
        # Morphological operations to clean up
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Get largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Compute centroid
        M = cv2.moments(largest_contour)
        if M['m00'] == 0:
            return None
        
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        
        return (cx, cy)
    
    def track_position(self, image: np.ndarray, **kwargs) -> Optional[np.ndarray]:
        """Track TX position and convert to world coordinates.
        
        Args:
            image: Input image (BGR)
            **kwargs: Additional arguments for detection method
        
        Returns:
            World coordinates (x, y) in meters, or None if not detected
        """
        # Detect in pixel coordinates
        if self.tracking_method == 'blob':
            pixel_pos = self.detect_tx_blob(image, **kwargs)
        elif self.tracking_method == 'template':
            pixel_pos = self.detect_tx_template(image, **kwargs)
        elif self.tracking_method == 'color':
            pixel_pos = self.detect_tx_color(image, **kwargs)
        else:
            raise ValueError(f"Unknown tracking method: {self.tracking_method}")
        
        if pixel_pos is None:
            return None
        
        # Convert to world coordinates
        world_pos = self.calibration.pixel_to_world(np.array([pixel_pos]))
        return world_pos[0]
    
    def track_session(self, image_paths: List[Path], 
                     save_path: Optional[Path] = None,
                     **kwargs) -> Dict[str, Any]:
        """Track TX position across all images in a session.
        
        Args:
            image_paths: List of image file paths
            save_path: Optional path to save tracking results
            **kwargs: Additional arguments for detection method
        
        Returns:
            Dictionary containing:
                - 'pixel_positions': Nx2 array of pixel coordinates
                - 'world_positions': Nx2 array of world coordinates
                - 'detected': boolean array indicating successful detections
                - 'image_paths': list of image paths
        """
        pixel_positions = []
        world_positions = []
        detected = []
        
        print(f"\nTracking TX across {len(image_paths)} images...")
        
        for i, img_path in enumerate(image_paths):
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"Warning: Failed to load {img_path}")
                pixel_positions.append([np.nan, np.nan])
                world_positions.append([np.nan, np.nan])
                detected.append(False)
                continue
            
            world_pos = self.track_position(image, **kwargs)
            
            if world_pos is not None:
                # Get pixel position for recording
                if self.tracking_method == 'blob':
                    pixel_pos = self.detect_tx_blob(image, **kwargs)
                elif self.tracking_method == 'template':
                    pixel_pos = self.detect_tx_template(image, **kwargs)
                elif self.tracking_method == 'color':
                    pixel_pos = self.detect_tx_color(image, **kwargs)
                
                pixel_positions.append(pixel_pos)
                world_positions.append(world_pos)
                detected.append(True)
            else:
                pixel_positions.append([np.nan, np.nan])
                world_positions.append([np.nan, np.nan])
                detected.append(False)
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(image_paths)} images")
        
        results = {
            'pixel_positions': np.array(pixel_positions),
            'world_positions': np.array(world_positions),
            'detected': np.array(detected),
            'image_paths': [str(p) for p in image_paths],
            'tracking_method': self.tracking_method,
            'detection_rate': np.mean(detected)
        }
        
        print(f"\nTracking complete!")
        print(f"Detection rate: {results['detection_rate']*100:.1f}%")
        print(f"Detected in {np.sum(detected)}/{len(image_paths)} images")
        
        if save_path:
            # Convert to JSON-serializable format
            save_data = {
                'pixel_positions': results['pixel_positions'].tolist(),
                'world_positions': results['world_positions'].tolist(),
                'detected': results['detected'].tolist(),
                'image_paths': results['image_paths'],
                'tracking_method': results['tracking_method'],
                'detection_rate': float(results['detection_rate'])
            }
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            print(f"Saved tracking results to: {save_path}")
        
        return results


def visualize_tracking_results(tracking_results: Dict[str, Any],
                               calibration: HomographyCalibration,
                               sample_images: Optional[List[Path]] = None,
                               num_samples: int = 6,
                               save_path: Optional[Path] = None):
    """Visualize tracking results.
    
    Args:
        tracking_results: Results from TXTracker.track_session()
        calibration: HomographyCalibration object
        sample_images: Optional list of sample image paths to display
        num_samples: Number of sample images to show
        save_path: Optional path to save visualization
    """
    fig = plt.figure(figsize=(18, 10))
    
    # Top: Trajectory in world coordinates
    ax1 = plt.subplot(2, 3, (1, 3))
    
    world_pos = tracking_results['world_positions']
    detected = tracking_results['detected']
    
    # Plot trajectory
    ax1.plot(world_pos[detected, 0], world_pos[detected, 1], 
            'b-', alpha=0.3, linewidth=1, label='Trajectory')
    scatter = ax1.scatter(world_pos[detected, 0], world_pos[detected, 1],
                         c=np.arange(np.sum(detected)), cmap='viridis',
                         s=30, alpha=0.7, label='Detected positions')
    
    # Mark start and end
    if np.any(detected):
        first_idx = np.where(detected)[0][0]
        last_idx = np.where(detected)[0][-1]
        ax1.plot(world_pos[first_idx, 0], world_pos[first_idx, 1], 
                'go', markersize=12, label='Start', zorder=5)
        ax1.plot(world_pos[last_idx, 0], world_pos[last_idx, 1], 
                'ro', markersize=12, label='End', zorder=5)
    
    ax1.set_xlabel('X (meters)', fontsize=12)
    ax1.set_ylabel('Y (meters)', fontsize=12)
    ax1.set_title(f'TX Ground Truth Trajectory\n'
                 f'Detection Rate: {tracking_results["detection_rate"]*100:.1f}%',
                 fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axis('equal')
    plt.colorbar(scatter, ax=ax1, label='Frame Index')
    
    # Bottom: Sample images with detected positions
    if sample_images is not None and len(sample_images) > 0:
        detected_indices = np.where(detected)[0]
        if len(detected_indices) > 0:
            # Sample evenly across detected frames
            sample_indices = np.linspace(0, len(detected_indices)-1, 
                                        min(num_samples, len(detected_indices)), 
                                        dtype=int)
            sample_indices = detected_indices[sample_indices]
            
            for i, idx in enumerate(sample_indices[:6]):  # Max 6 samples
                ax = plt.subplot(2, 6, i + 7)
                
                img_path = Path(tracking_results['image_paths'][idx])
                if img_path.exists():
                    img = cv2.imread(str(img_path))
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    
                    ax.imshow(img_rgb)
                    
                    # Draw detected position
                    px, py = tracking_results['pixel_positions'][idx]
                    ax.plot(px, py, 'r+', markersize=20, markeredgewidth=3)
                    ax.plot(px, py, 'yo', markersize=10, fillstyle='none', 
                           markeredgewidth=2)
                    
                    ax.set_title(f'Frame {idx}', fontsize=10)
                    ax.axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved tracking visualization to: {save_path}")
    else:
        plt.show()
    
    plt.close()


if __name__ == "__main__":
    print("Camera tracking module loaded.")
    print("See example_camera_tracking.py for usage examples.")
