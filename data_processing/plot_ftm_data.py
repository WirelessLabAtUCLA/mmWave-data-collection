#!/usr/bin/env python3
"""
Visualization script for FTM (Fine Time Measurement) data.

This script provides various plotting functions for FTM data:
- RTT over time
- FTM timestamp distributions
- RTT histograms
- FTM data availability
"""

from pathlib import Path
from session_data import SessionData
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from datetime import datetime


def plot_rtt_over_time(session: SessionData, save_path: Path = None, show: bool = True):
    """Plot RTT (Round Trip Time) values over time.
    
    Args:
        session: SessionData object with loaded data
        save_path: Optional path to save the plot
        show: Whether to display the plot
    """
    # Get RTT data
    rtt_data = session.get_ftm_rtt_data()
    
    # Create measurement indices
    indices = np.arange(len(rtt_data))
    
    # Separate zero and non-zero values
    has_ftm = rtt_data != 0
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Plot RTT values (convert to nanoseconds for readability)
    rtt_ns = rtt_data / 1000.0
    
    # Plot non-zero values
    ax.scatter(indices[has_ftm], rtt_ns[has_ftm], c='blue', s=10, alpha=0.6, label='FTM RTT')
    
    # Mark regions without FTM data
    ax.scatter(indices[~has_ftm], np.zeros(np.sum(~has_ftm)), c='red', s=5, alpha=0.3, label='No FTM data')
    
    # Add mean line for valid RTT
    valid_rtt_ns = rtt_ns[has_ftm]
    if len(valid_rtt_ns) > 0:
        mean_rtt = np.mean(valid_rtt_ns)
        ax.axhline(y=mean_rtt, color='green', linestyle='--', linewidth=2, 
                   label=f'Mean RTT: {mean_rtt:.2f} ns')
    
    ax.set_xlabel('Measurement Index', fontsize=12)
    ax.set_ylabel('RTT (nanoseconds)', fontsize=12)
    ax.set_title(f'FTM Round Trip Time - {session.session_id}', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved RTT plot to: {save_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def plot_ftm_timestamps(session: SessionData, save_path: Path = None, show: bool = True):
    """Plot individual FTM timestamp values (t1, t2, t3, t4).
    
    Args:
        session: SessionData object with loaded data
        save_path: Optional path to save the plot
        show: Whether to display the plot
    """
    # Get FTM data
    ftm_data = session.get_ftm_data()
    
    # Filter to only measurements with FTM data
    has_ftm = np.any(ftm_data != 0, axis=1)
    ftm_valid = ftm_data[has_ftm]
    
    if len(ftm_valid) == 0:
        print("No FTM data available to plot")
        return
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'FTM Timestamp Analysis - {session.session_id}', 
                 fontsize=16, fontweight='bold')
    
    timestamp_names = ['t1 (Initiator Send)', 't2 (Responder Receive)', 
                       't3 (Responder ACK)', 't4 (Initiator ACK Receive)']
    colors = ['blue', 'green', 'orange', 'red']
    
    indices = np.arange(len(ftm_valid))
    
    for i, (ax, name, color) in enumerate(zip(axes.flat, timestamp_names, colors)):
        # Convert to nanoseconds (divide by 1000)
        timestamps_ns = ftm_valid[:, i] / 1000.0
        
        ax.plot(indices, timestamps_ns, color=color, linewidth=1, alpha=0.7)
        ax.scatter(indices, timestamps_ns, c=color, s=10, alpha=0.6)
        
        ax.set_xlabel('FTM Measurement Index', fontsize=10)
        ax.set_ylabel('Time (nanoseconds)', fontsize=10)
        ax.set_title(name, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        mean_val = np.mean(timestamps_ns)
        std_val = np.std(timestamps_ns)
        ax.text(0.02, 0.98, f'Mean: {mean_val:.2f} ns\nStd: {std_val:.2f} ns',
                transform=ax.transAxes, fontsize=9, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved timestamp plot to: {save_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def plot_rtt_histogram(session: SessionData, save_path: Path = None, show: bool = True):
    """Plot histogram of RTT values.
    
    Args:
        session: SessionData object with loaded data
        save_path: Optional path to save the plot
        show: Whether to display the plot
    """
    # Get RTT data
    rtt_data = session.get_ftm_rtt_data()
    
    # Filter to valid RTT values
    valid_rtt = rtt_data[rtt_data != 0]
    
    if len(valid_rtt) == 0:
        print("No FTM data available to plot")
        return
    
    # Convert to nanoseconds
    rtt_ns = valid_rtt / 1000.0
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot histogram
    n, bins, patches = ax.hist(rtt_ns, bins=30, color='steelblue', alpha=0.7, edgecolor='black')
    
    # Add mean and median lines
    mean_rtt = np.mean(rtt_ns)
    median_rtt = np.median(rtt_ns)
    
    ax.axvline(mean_rtt, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_rtt:.2f} ns')
    ax.axvline(median_rtt, color='green', linestyle='--', linewidth=2, label=f'Median: {median_rtt:.2f} ns')
    
    ax.set_xlabel('RTT (nanoseconds)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(f'FTM RTT Distribution - {session.session_id}', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add statistics text box
    stats_text = f'Statistics:\n'
    stats_text += f'Count: {len(rtt_ns)}\n'
    stats_text += f'Mean: {mean_rtt:.2f} ns\n'
    stats_text += f'Median: {median_rtt:.2f} ns\n'
    stats_text += f'Std: {np.std(rtt_ns):.2f} ns\n'
    stats_text += f'Min: {np.min(rtt_ns):.2f} ns\n'
    stats_text += f'Max: {np.max(rtt_ns):.2f} ns'
    
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved RTT histogram to: {save_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def plot_ftm_availability(session: SessionData, save_path: Path = None, show: bool = True):
    """Plot FTM data availability per batch.
    
    Args:
        session: SessionData object with loaded data
        save_path: Optional path to save the plot
        show: Whether to display the plot
    """
    # Load all batches
    session.load_all_router_batches()
    ftm_batches = session.load_all_ftm_batches()
    
    # Collect statistics per batch
    batch_indices = []
    csi_counts = []
    ftm_counts = []
    
    for i, (dp, ftm_batch) in enumerate(zip(session.data_points, ftm_batches)):
        router_batch = dp.router_batch
        batch_indices.append(dp.index)
        csi_counts.append(len(router_batch.csi_processed_data))
        ftm_counts.append(ftm_batch.count if ftm_batch is not None else 0)
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f'FTM Data Availability - {session.session_id}', 
                 fontsize=14, fontweight='bold')
    
    # Plot 1: CSI vs FTM counts
    x = np.arange(len(batch_indices))
    width = 0.35
    
    ax1.bar(x - width/2, csi_counts, width, label='CSI Measurements', color='steelblue', alpha=0.7)
    ax1.bar(x + width/2, ftm_counts, width, label='FTM Measurements', color='coral', alpha=0.7)
    
    ax1.set_xlabel('Data Point Index', fontsize=12)
    ax1.set_ylabel('Measurement Count', fontsize=12)
    ax1.set_title('CSI vs FTM Measurement Counts per Batch', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(batch_indices)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Plot 2: FTM availability percentage
    ftm_percentages = [100 * ftm / csi if csi > 0 else 0 
                       for ftm, csi in zip(ftm_counts, csi_counts)]
    
    colors_bar = ['green' if p > 50 else 'orange' if p > 0 else 'red' for p in ftm_percentages]
    ax2.bar(x, ftm_percentages, color=colors_bar, alpha=0.7, edgecolor='black')
    
    ax2.set_xlabel('Data Point Index', fontsize=12)
    ax2.set_ylabel('FTM Availability (%)', fontsize=12)
    ax2.set_title('FTM Data Coverage per Batch', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(batch_indices)
    ax2.set_ylim([0, 105])
    ax2.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add overall statistics
    total_csi = sum(csi_counts)
    total_ftm = sum(ftm_counts)
    overall_percentage = 100 * total_ftm / total_csi if total_csi > 0 else 0
    
    stats_text = f'Overall:\n'
    stats_text += f'Total CSI: {total_csi}\n'
    stats_text += f'Total FTM: {total_ftm}\n'
    stats_text += f'Coverage: {overall_percentage:.1f}%'
    
    ax2.text(0.98, 0.98, stats_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved availability plot to: {save_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def plot_ftm_comprehensive(session: SessionData, save_dir: Path = None, show: bool = True):
    """Create a comprehensive multi-panel plot with all FTM visualizations.
    
    Args:
        session: SessionData object with loaded data
        save_dir: Optional directory to save individual plots
        show: Whether to display the plots
    """
    print(f"\nGenerating comprehensive FTM plots for session: {session.session_id}")
    print("="*60)
    
    # Ensure plots directory exists
    if save_dir is None:
        save_dir = session.get_save_plot_path()
    else:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate all plots
    print("\n1. Plotting RTT over time...")
    plot_rtt_over_time(session, save_path=save_dir / 'ftm_rtt_over_time.png', show=show)
    
    print("2. Plotting FTM timestamps...")
    plot_ftm_timestamps(session, save_path=save_dir / 'ftm_timestamps.png', show=show)
    
    print("3. Plotting RTT histogram...")
    plot_rtt_histogram(session, save_path=save_dir / 'ftm_rtt_histogram.png', show=show)
    
    print("4. Plotting FTM availability...")
    plot_ftm_availability(session, save_path=save_dir / 'ftm_availability.png', show=show)
    
    print("\n" + "="*60)
    print(f"All plots saved to: {save_dir}")
    print("="*60)


def main():
    """Main function to demonstrate FTM plotting."""
    
    # Load session with FTM data
    session_dir = Path("../data/2026-01-31/session_132737")
    
    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}")
        return
    
    print(f"Loading session from: {session_dir}")
    session = SessionData.from_directory(session_dir)
    
    print("\nSession Summary:")
    print(session.summary())
    
    # Generate all plots
    plot_ftm_comprehensive(session, show=False)
    
    print("\nDone! Check the plots/ directory in the session folder.")


if __name__ == "__main__":
    main()
