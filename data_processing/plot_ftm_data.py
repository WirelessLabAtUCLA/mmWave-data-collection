#!/usr/bin/env python3
"""
Visualization script for FTM (Fine Time Measurement) data.

Produces two simple plots:
    1. RTT over batch index (nanoseconds)
    2. Distance over batch index (metres)
"""

from pathlib import Path
from typing import Optional
from session_data import SessionData
import numpy as np
import matplotlib.pyplot as plt


def plot_ftm_data(session: SessionData, save_path: Optional[Path] = None, show: bool = True):
    """Plot FTM RTT and distance for a session.

    Creates two figures:
        - RTT (ns) vs batch index
        - Distance (m) vs batch index

    Args:
        session:   SessionData object.
        save_path: Directory to save figures into. If None, figures are not saved.
        show:      Whether to display the figures interactively.
    """
    ftm = session.get_ftm_data()
    rtt_ns = ftm["rtt"] / 1000.0          # picoseconds → nanoseconds
    distance = ftm["distance"]
    indices = np.arange(len(rtt_ns))

    # ── Figure 1: RTT ────────────────────────────────────────────────────────
    fig_rtt, ax_rtt = plt.subplots(figsize=(10, 4))
    ax_rtt.plot(indices, rtt_ns, linewidth=1.0, color="steelblue")
    ax_rtt.set_xlabel("Batch index")
    ax_rtt.set_ylabel("RTT (ns)")
    ax_rtt.set_title(f"FTM Round-Trip Time — {session.session_id}")
    ax_rtt.grid(True, alpha=0.3)
    fig_rtt.tight_layout()

    if save_path:
        rtt_file = Path(save_path) / "ftm_rtt.png"
        fig_rtt.savefig(rtt_file, dpi=150, bbox_inches="tight")
        print(f"Saved RTT plot to: {rtt_file}")

    # ── Figure 2: Distance ───────────────────────────────────────────────────
    fig_dist, ax_dist = plt.subplots(figsize=(10, 4))
    ax_dist.plot(indices, distance, linewidth=1.0, color="darkorange")
    ax_dist.set_xlabel("Batch index")
    ax_dist.set_ylabel("Distance (m)")
    ax_dist.set_title(f"FTM Distance — {session.session_id}")
    ax_dist.grid(True, alpha=0.3)
    fig_dist.tight_layout()

    if save_path:
        dist_file = Path(save_path) / "ftm_distance.png"
        fig_dist.savefig(dist_file, dpi=150, bbox_inches="tight")
        print(f"Saved distance plot to: {dist_file}")

    if show:
        plt.show()
    else:
        plt.close("all")


def main():
    """Load a session and display FTM plots."""
    session_dir = Path("../data/2026-01-31/session_134250")

    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}")
        return

    print(f"Loading session from: {session_dir}")
    session = SessionData.from_directory(session_dir)

    print("\nSession Summary:")
    print(session.summary())

    save_path = session.get_save_plot_path()
    plot_ftm_data(session, save_path=save_path, show=True)


if __name__ == "__main__":
    main()
