"""
Visualization utilities for mmWave session data.

Requires matplotlib. Install with: pip install matplotlib
"""


import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from antenna_array import AntennaArray
from session_data import SessionData
from mikrotik_metadata import ordering_sets
import shutil
from PIL import Image

def plot_animation_of_images(session: SessionData, save_path: Path = None):
    """Plot animation of the images.
    
    Args:
        session: SessionData object
        save_path: Optional path to save the animation video (e.g., 'animation.mp4')
                  If None, the video will be saved to './videos/{session_id}/images_animation.mp4'
    """
    image_paths = session.get_image_paths()
    num_samples = len(image_paths)
    
    if num_samples == 0:
        print("No images found in session!")
        return
    
    # Set default save path if not provided
    if save_path is None:
        save_path = Path(f'./videos/{session.session_id}/images_animation.mp4')
    else:
        save_path = Path(save_path)
    
    # Create directory if it doesn't exist
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create figure
    fig = plt.figure(figsize=(12, 10))
    
    # Animation update function
    def update_frame(frame_idx):
        """Update function for each frame of the animation."""
        fig.clear()
        
        ax = fig.add_subplot(111)
        img = Image.open(image_paths[frame_idx])
        ax.imshow(img)
        ax.axis('off')
        ax.set_title(f'Image {frame_idx + 1}/{num_samples}\n'
                    f'Session: {session.session_id}\n'
                    f'{image_paths[frame_idx].name}', 
                    pad=20, fontsize=14)
        
        print(f'Processed image {frame_idx + 1} of {num_samples}')
        
        return ax,
    
    # Create animation
    print(f"Creating animation with {num_samples} images...")
    anim = FuncAnimation(fig, update_frame, frames=num_samples, 
                        interval=500, blit=False, repeat=True)
    
    # Check if ffmpeg is available
    ffmpeg_available = shutil.which('ffmpeg') is not None
    
    if ffmpeg_available:
        # Use FFMpegWriter for high-quality MP4
        writer = FFMpegWriter(fps=2, metadata=dict(artist='mmWave-data-collection'),
                             bitrate=1800)
        print(f"Saving animation to: {save_path}")
    else:
        # Fallback to PillowWriter for GIF (if ffmpeg not available)
        print("FFmpeg not found. Falling back to GIF format...")
        save_path = save_path.with_suffix('.gif')
        writer = PillowWriter(fps=2, metadata=dict(artist='mmWave-data-collection'))
        print(f"Saving animation to: {save_path}")
        print("Tip: Install ffmpeg for MP4 output: conda install ffmpeg or sudo apt install ffmpeg")
    
    # Save animation
    anim.save(str(save_path), writer=writer)
    plt.close(fig)
    
    print(f"Animation saved successfully to: {save_path}")

def plot_animation_of_beamformer(session: SessionData, save_path: Path = None, plot_image: bool = False, azimuth: bool = True, averaged: bool = True):
    """Plot animation of the beamformer.
    
    Args:    
        session: SessionData object
        save_path: Optional path to save the animation video (e.g., 'animation.mp4')
        plot_image: Whether to plot the camera image side by side with the beamformer pattern
        azimuth: Whether to plot the beamformer pattern in azimuth (True) or elevation (False)
    """
    if azimuth:
        plot_type = 'azimuth'
    else:
        plot_type = 'elevation'

    channel_data = session.get_csi_data(averaged=averaged)
    num_samples = channel_data.shape[0]
    valid_antennas = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27]

    # Create antenna arrays for each sample
    spacing = 0.58 * session.frequency / 60.48
    antenna_arrays = [AntennaArray() for _ in range(num_samples)]
    for i in range(num_samples):
        for antenna in range(32):
            if antenna not in valid_antennas:
                continue
            antenna_arrays[i].add_element(ordering_sets[antenna, 0]*spacing - np.sign(ordering_sets[antenna, 0])*spacing/2, 
                0, ordering_sets[antenna, 1]*spacing - np.sign(ordering_sets[antenna, 1])*spacing/2)
        antenna_arrays[i].set_weights(np.conjugate(channel_data[i, :]))
    
    # Set default save path if not provided
    if save_path is None:
        save_path = session.get_save_plot_path() / f'csi_polar_{plot_type}.mp4'
    else:
        save_path = Path(save_path)
        
    # Get image paths if plot_image is True
    image_paths = None

    # Handle both old format (router_batch) and new format (csi_batch)
    first_data_point = session.metadata['data_points'][0]
    batch_info = first_data_point.get('csi_batch') or first_data_point.get('router_batch')
    measurements_per_image = int(batch_info['measurement_count'])
    if plot_image:
        image_paths = session.get_image_paths()
        image_paths = np.repeat(image_paths, measurements_per_image)[global_indices]
    
    # Create figure with appropriate layout
    if plot_image:
        fig = plt.figure(figsize=(20, 8))
    else:
        fig = plt.figure(figsize=(12, 8))
    
    # Animation update function
    def update_frame(frame_idx):
        """Update function for each frame of the animation."""
        fig.clear()
        
        if plot_image:
            # Create subplots: image on left, beamformer on right
            ax_img = fig.add_subplot(121)
            ax_polar = fig.add_subplot(122, projection='polar')
            
            img = Image.open(image_paths[frame_idx])
            ax_img.imshow(img)
            ax_img.set_title(f'Webcam Image {frame_idx + 1}/{len(image_paths)}\n'
                           f'(Measurement {frame_idx + 1}/{num_samples})')
            ax_img.axis('off')
        else:
            # Only beamformer plot
            ax_polar = fig.add_subplot(111, projection='polar')
        
        # Configure polar plot
        ax_polar.set_thetamin(-90)
        ax_polar.set_thetamax(90)
        
        # Plot the polar array pattern for the current frame
        if azimuth:
            antenna_arrays[frame_idx].show_polar_array_pattern_azimuth(ax_polar, el=0, N=1024, full=True)
        else:
            antenna_arrays[frame_idx].show_polar_array_pattern_elevation(ax_polar, az=np.deg2rad(5), N=1024, full=True)

        # Add frame counter and session info
        ax_polar.set_title(f'Beamformer Pattern - Frame {frame_idx + 1}/{num_samples}\n'
                          f'Session: {session.session_id}', pad=20)
        
        print(f'Processed frame {frame_idx + 1} of {num_samples}')
        
        if plot_image:
            return ax_img, ax_polar
        else:
            return ax_polar,
    
    # Create animation
    print(f"Creating animation with {num_samples} frames...")
    anim = FuncAnimation(fig, update_frame, frames=num_samples, 
                        interval=100, blit=False, repeat=True)
    
    # Check if ffmpeg is available
    ffmpeg_available = shutil.which('ffmpeg') is not None
    
    if ffmpeg_available:
        # Use FFMpegWriter for high-quality MP4
        writer = FFMpegWriter(fps=5, metadata=dict(artist='mmWave-data-collection'),
                             bitrate=1800)
        print(f"Saving animation to: {save_path}")
    else:
        # Fallback to PillowWriter for GIF (if ffmpeg not available)
        print("FFmpeg not found. Falling back to GIF format...")
        save_path = save_path.with_suffix('.gif')
        writer = PillowWriter(fps=5, metadata=dict(artist='mmWave-data-collection'))
        print(f"Saving animation to: {save_path}")
        print("Tip: Install ffmpeg for MP4 output: conda install ffmpeg or sudo apt install ffmpeg")
    
    # Save animation
    anim.save(str(save_path), writer=writer)
    plt.close(fig)
    
    print(f"Animation saved successfully to: {session.get_save_plot_path() / save_path}")

def plot_ftm_timeseries(session: SessionData, save_path: Path = None):
    """Plot FTM RTT and distance timeseries.

    Args:
        session: SessionData object
        save_path: Optional path to save the figure
    """
    ftm_data = session.get_ftm_data()
    indices = np.arange(len(ftm_data['rtt']))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    ax1.plot(indices, ftm_data['rtt'], linewidth=1.5)
    ax1.set_ylabel('RTT (ps)')
    ax1.set_title(f'FTM Timeseries - {session.session_id}')
    ax1.grid(True, alpha=0.3)

    ax2.plot(indices, ftm_data['distance'], linewidth=1.5, color='tab:orange')
    ax2.set_xlabel('Batch Index')
    ax2.set_ylabel('Distance (m)')
    ax2.set_title('FTM Distance')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"FTM timeseries plot saved to: {save_path}")
    else:
        plt.show()

def plot_slam_trajectory(session: SessionData, save_path: Path = None):
    """Plot SLAM XY trajectory in metres.

    Left panel: top-down XY path coloured by data-point index.
    Right panel: Z (height) profile over time.

    Args:
        session: SessionData object
        save_path: Optional path to save the figure
    """
    trajectory = session.get_slam_trajectory()

    if len(trajectory) == 0:
        print("No SLAM pose data available in this session. "
              "Was RTAB-Map running during collection?")
        return

    indices = np.arange(len(trajectory))

    fig = plt.figure(figsize=(14, 6))

    # Top-down XY trajectory
    scatter = plt.scatter(trajectory[:, 0], trajectory[:, 2],
                          c=indices, cmap='viridis', s=50, alpha=0.7)
    plt.plot(trajectory[:, 0], trajectory[:, 2], 'k-', alpha=0.25, linewidth=1)
    plt.plot(trajectory[0, 0], trajectory[0, 2], 'go',
             markersize=10, label='Start', zorder=5)
    plt.plot(trajectory[-1, 0], trajectory[-1, 2], 'ro',
             markersize=10, label='End', zorder=5)
    plt.xlabel('X (m)')
    plt.ylabel('Y (m)')
    plt.title(f'SLAM Trajectory - {session.session_id}')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.colorbar(scatter, label='Data Point Index')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"SLAM trajectory plot saved to: {save_path}")
    else:
        plt.show()


def plot_csi_phase_data(session: SessionData, save_path: Path = None, averaged: bool = True):
    """Plot CSI phase data.
    
    Args:
        session: SessionData object
        save_path: Optional path to save the figure
    """
    fig, axes = plt.subplots(4, 4, figsize=(18, 8))
    axes = axes.flatten()
    channel_data = session.get_csi_data(averaged=averaged)
    phase_data = np.angle(channel_data, True)
    # Set titles and labels for each subplot
    for antenna in range(16):
        axes[antenna].plot(phase_data[:, antenna], markersize=3, alpha=0.7)
        axes[antenna].set_title(f"Antenna {antenna+1}")
        axes[antenna].set_xlabel('Sample Index')
        axes[antenna].set_ylabel('Phase (degrees)')
        axes[antenna].grid(True, alpha=0.3)
        axes[antenna].set_ylim(-180, 180)
    
    plt.suptitle(f'CSI Phase Data - {session.session_id}', fontsize=16)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"CSI phase plot saved to: {save_path}")
    else:
        plt.show()


def plot_temporal_analysis(session: SessionData, save_path: Path = None):
    """Plot temporal analysis of the session.
    
    Args:
        session: SessionData object
        save_path: Optional path to save the figure
    """
    timestamps = session.get_timestamps()
    
    # Calculate time intervals
    time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                  for i in range(len(timestamps)-1)]
    
    # Calculate relative time from start
    start_time = timestamps[0]
    relative_times = [(t - start_time).total_seconds() for t in timestamps]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Sampling intervals
    ax1.plot(range(len(time_diffs)), time_diffs, 'b.-', linewidth=1, markersize=3)
    ax1.axhline(np.mean(time_diffs), color='r', linestyle='--', 
                label=f'Mean: {np.mean(time_diffs):.3f}s')
    ax1.set_xlabel('Sample Index')
    ax1.set_ylabel('Time Interval (seconds)')
    ax1.set_title('Sampling Intervals')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Cumulative samples over time
    ax2.plot(relative_times, range(len(relative_times)), 'g-', linewidth=2)
    ax2.set_xlabel('Time since start (seconds)')
    ax2.set_ylabel('Cumulative Samples')
    ax2.set_title('Data Collection Progress')
    ax2.grid(True, alpha=0.3)
    
    # Add session info
    info_text = (f"Session: {session.session_id}\n"
                f"Duration: {session.get_duration():.1f}s\n"
                f"Samples: {session.total_samples}\n"
                f"Avg Rate: {session.total_samples/session.get_duration():.2f} Hz")
    ax2.text(0.02, 0.98, info_text, transform=ax2.transAxes,
            verticalalignment='top', bbox=dict(boxstyle='round', 
            facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Temporal analysis plot saved to: {save_path}")
    else:
        plt.show()


def create_all_plots(session: SessionData, output_dir: Path, include_animation: bool = False):
    """Create all visualization plots for a session.
    
    Args:
        session: SessionData object
        output_dir: Directory to save plots
        include_animation: Whether to create beamformer animation (default: False, as it can be time-consuming)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating visualizations for {session.session_id}...")
    print("-" * 60)
    
    # SLAM trajectory
    plot_slam_trajectory(session, output_dir / 'slam_trajectory.png')
    
    # CSI phase data
    plot_csi_phase_data(session, output_dir / 'csi_phase_data.png')
    
    # Temporal analysis
    plot_temporal_analysis(session, output_dir / 'temporal_analysis.png')
    
    # Beamformer animation (optional, can be time-consuming)
    if include_animation:
        print("\nCreating beamformer animation (this may take a while)...")
        plot_animation_of_beamformer(session, output_dir / 'beamformer_animation.mp4')
    
    print("-" * 60)
    print(f"All plots saved to: {output_dir}")


def plot_csi_phase_heatmap(session: SessionData, averaged: bool = False, 
                          save_path: Path = None, show: bool = False,
                          figsize: tuple = (20, 8), cmap: str = 'twilight'):
    """Plot CSI phase data as a heatmap with antennas as rows and time as columns.
    
    Creates a large heatmap where:
    - Each row represents one antenna (16 antennas total)
    - Each column represents one measurement in time
    - Color represents the phase angle (-π to π)
    
    Args:
        session: SessionData object with loaded router batches
        averaged: If True, uses averaged CSI per batch. If False, uses all measurements
        save_path: Optional path to save the plot (e.g., 'csi_heatmap.png')
        show: Whether to display the plot
        figsize: Figure size as (width, height) tuple
        cmap: Matplotlib colormap name (default: 'twilight' for circular phase data)
    """
    # Get CSI data
    csi_data = session.get_csi_data(averaged=averaged)
    num_measurements, num_antennas = csi_data.shape
    
    print(f"Creating CSI phase heatmap: {num_measurements} measurements × {num_antennas} antennas")
    
    # Extract phase angles from complex CSI data
    phase_data = np.angle(csi_data).T  # Transpose to get (antennas, time)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create heatmap
    im = ax.imshow(phase_data, aspect='auto', cmap=cmap, 
                   vmin=-np.pi, vmax=np.pi, interpolation='nearest')
    
    # Configure axes
    ax.set_xlabel('Measurement Index (Time →)', fontsize=12)
    ax.set_ylabel('Antenna Index', fontsize=12)
    ax.set_title(f'CSI Phase Heatmap - {session.session_id}\n'
                 f'({num_measurements} measurements × {num_antennas} antennas)', 
                 fontsize=14, fontweight='bold')
    
    # Set y-axis ticks to show all antennas
    ax.set_yticks(range(num_antennas))
    ax.set_yticklabels([f'Ant {i}' for i in range(num_antennas)])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Phase (radians)')
    cbar.set_ticks([-np.pi, -np.pi/2, 0, np.pi/2, np.pi])
    cbar.set_ticklabels(['-π', '-π/2', '0', 'π/2', 'π'])
    
    # Add grid for better readability
    ax.set_xticks(np.arange(0, num_measurements, max(1, num_measurements // 20)))
    ax.grid(False)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved CSI phase heatmap to: {save_path}")
    
    # Show if requested
    if show:
        plt.show()
    else:
        plt.close()


def plot_csi_magnitude_heatmap(session: SessionData, averaged: bool = False,
                               save_path: Path = None, show: bool = False,
                               figsize: tuple = (20, 8), cmap: str = 'viridis'):
    """Plot CSI magnitude data as a heatmap with antennas as rows and time as columns.
    
    Creates a large heatmap where:
    - Each row represents one antenna (16 antennas total)
    - Each column represents one measurement in time
    - Color represents the magnitude/amplitude
    
    Args:
        session: SessionData object with loaded router batches
        averaged: If True, uses averaged CSI per batch. If False, uses all measurements
        save_path: Optional path to save the plot (e.g., 'csi_magnitude_heatmap.png')
        show: Whether to display the plot
        figsize: Figure size as (width, height) tuple
        cmap: Matplotlib colormap name (default: 'viridis')
    """
    # Get CSI data
    csi_data = session.get_csi_data(averaged=averaged)
    num_measurements, num_antennas = csi_data.shape
    
    print(f"Creating CSI magnitude heatmap: {num_measurements} measurements × {num_antennas} antennas")
    
    # Extract magnitude from complex CSI data
    magnitude_data = np.abs(csi_data).T  # Transpose to get (antennas, time)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create heatmap
    im = ax.imshow(magnitude_data, aspect='auto', cmap=cmap, interpolation='nearest')
    
    # Configure axes
    ax.set_xlabel('Measurement Index (Time →)', fontsize=12)
    ax.set_ylabel('Antenna Index', fontsize=12)
    ax.set_title(f'CSI Magnitude Heatmap - {session.session_id}\n'
                 f'({num_measurements} measurements × {num_antennas} antennas)', 
                 fontsize=14, fontweight='bold')
    
    # Set y-axis ticks to show all antennas
    ax.set_yticks(range(num_antennas))
    ax.set_yticklabels([f'Ant {i}' for i in range(num_antennas)])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Magnitude')
    
    # Add grid for better readability
    ax.set_xticks(np.arange(0, num_measurements, max(1, num_measurements // 20)))
    ax.grid(False)
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved CSI magnitude heatmap to: {save_path}")
    
    # Show if requested
    if show:
        plt.show()
    else:
        plt.close()


def plot_csi_combined_heatmap(session: SessionData, averaged: bool = False,
                              save_path: Path = None, show: bool = False,
                              figsize: tuple = (20, 12)):
    """Plot both phase and magnitude CSI heatmaps in a single figure.
    
    Creates two stacked heatmaps:
    - Top: Phase heatmap
    - Bottom: Magnitude heatmap
    
    Args:
        session: SessionData object with loaded router batches
        averaged: If True, uses averaged CSI per batch. If False, uses all measurements
        save_path: Optional path to save the plot (e.g., 'csi_combined_heatmap.png')
        show: Whether to display the plot
        figsize: Figure size as (width, height) tuple
    """
    # Get CSI data
    csi_data = session.get_csi_data(averaged=averaged)
    num_measurements, num_antennas = csi_data.shape
    
    print(f"Creating combined CSI heatmap: {num_measurements} measurements × {num_antennas} antennas")
    
    # Extract phase and magnitude
    phase_data = np.angle(csi_data).T
    magnitude_data = np.abs(csi_data).T
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    
    # Phase heatmap
    im1 = ax1.imshow(phase_data, aspect='auto', cmap='twilight',
                     vmin=-np.pi, vmax=np.pi, interpolation='nearest')
    ax1.set_ylabel('Antenna Index', fontsize=11)
    ax1.set_title(f'CSI Phase and Magnitude Heatmaps - {session.session_id}\n'
                  f'Phase (top) and Magnitude (bottom)', 
                  fontsize=13, fontweight='bold')
    ax1.set_yticks(range(num_antennas))
    ax1.set_yticklabels([f'Ant {i}' for i in range(num_antennas)])
    
    cbar1 = plt.colorbar(im1, ax=ax1, label='Phase (radians)')
    cbar1.set_ticks([-np.pi, -np.pi/2, 0, np.pi/2, np.pi])
    cbar1.set_ticklabels(['-π', '-π/2', '0', 'π/2', 'π'])
    
    # Magnitude heatmap
    im2 = ax2.imshow(magnitude_data, aspect='auto', cmap='viridis', interpolation='nearest')
    ax2.set_xlabel('Measurement Index (Time →)', fontsize=11)
    ax2.set_ylabel('Antenna Index', fontsize=11)
    ax2.set_yticks(range(num_antennas))
    ax2.set_yticklabels([f'Ant {i}' for i in range(num_antennas)])
    
    cbar2 = plt.colorbar(im2, ax=ax2, label='Magnitude')
    
    # Set x-axis ticks
    ax2.set_xticks(np.arange(0, num_measurements, max(1, num_measurements // 20)))
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved combined CSI heatmap to: {save_path}")
    
    # Show if requested
    if show:
        plt.show()
    else:
        plt.close()


if __name__ == "__main__":
    # Example usage
    session_dir = Path("../data/2025-10-30/session_141256")
    session = SessionData.from_directory(session_dir)
    
    # Create all visualizations (without animation by default)
    output_dir = Path("./visualizations")
    # create_all_plots(session, output_dir)
    
    # Create all visualizations including beamformer animation
    # create_all_plots(session, output_dir, include_animation=True)
    
    # Or create individual plots
    plot_slam_trajectory(session)
    plot_temporal_analysis(session)
    plot_csi_phase_data(session)
    
    # Create beamformer animation
    # plot_animation_of_beamformer(session)


