#!/usr/bin/env python3
"""
Test script to demonstrate CSI phase heatmap visualization.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'data_processing'))

from session_data import SessionData
from visualize import plot_csi_phase_heatmap, plot_csi_magnitude_heatmap, plot_csi_combined_heatmap

def main():
    """Generate CSI heatmap visualizations."""
    
    # Load session
    session_dir = Path("data/2026-01-31/session_142318")
    
    if not session_dir.exists():
        print(f"Session not found: {session_dir}")
        print("Please update the session_dir path in this script")
        return
    
    print(f"Loading session from: {session_dir}")
    session = SessionData.from_directory(session_dir)
    
    # Load all router batches
    print("Loading CSI data...")
    session.load_all_router_batches()
    
    print("\nSession Summary:")
    print(session.summary())
    
    # Get save directory
    save_dir = session.get_save_plot_path()
    
    print("\n" + "="*60)
    print("Generating CSI Heatmap Visualizations")
    print("="*60)
    
    # 1. Phase heatmap (using all measurements)
    print("\n1. Creating phase heatmap (all measurements)...")
    plot_csi_phase_heatmap(
        session, 
        averaged=False,
        save_path=save_dir / 'csi_phase_heatmap_all.png',
        show=False,
        figsize=(24, 8)
    )
    
    # 2. Phase heatmap (averaged per batch)
    print("\n2. Creating phase heatmap (averaged per batch)...")
    plot_csi_phase_heatmap(
        session, 
        averaged=True,
        save_path=save_dir / 'csi_phase_heatmap_averaged.png',
        show=False,
        figsize=(16, 8)
    )
    
    # 3. Magnitude heatmap
    print("\n3. Creating magnitude heatmap...")
    plot_csi_magnitude_heatmap(
        session,
        averaged=False,
        save_path=save_dir / 'csi_magnitude_heatmap.png',
        show=False,
        figsize=(24, 8)
    )
    
    # 4. Combined heatmap (phase + magnitude)
    print("\n4. Creating combined heatmap...")
    plot_csi_combined_heatmap(
        session,
        averaged=False,
        save_path=save_dir / 'csi_combined_heatmap.png',
        show=False,
        figsize=(24, 14)
    )
    
    print("\n" + "="*60)
    print(f"All heatmaps saved to: {save_dir}")
    print("="*60)
    
    print("\nGenerated files:")
    print(f"  - csi_phase_heatmap_all.png (all measurements)")
    print(f"  - csi_phase_heatmap_averaged.png (averaged per batch)")
    print(f"  - csi_magnitude_heatmap.png")
    print(f"  - csi_combined_heatmap.png (phase + magnitude)")

if __name__ == "__main__":
    main()
