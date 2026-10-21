"""
Sorted phase changes per antenna (one curve each).

Default antennas: mikrotik_metadata.valid_antennas (S/A+/A tier).

For every antenna the phase difference between consecutive samples is wrapped to
(-pi, pi], sorted ascending, and plotted against the sorted sample index. A flat
curve near 0 means a stable antenna; the saturated steps at +-pi are phase wraps /
jumps, and a long middle slope means a noisy antenna.

  --level batch  : samples = batch-averaged post-processed phase (one per table angle)
  --level packet : samples = raw per-packet phase (diffs across batch boundaries dropped)

Antenna columns are physical indices 0..31. Batch-level phases use the packets kept by paper_figures'
processing of the 16 CSI antennas.

Usage
-----
    python plot_sorted_phase_changes.py
    python plot_sorted_phase_changes.py --dataset rotation_outdoor_15m --level packet

Output (PDF + PNG): <datasets>/paper_figures/<dataset>/fig_sorted_phase_changes_<level>.{pdf,png}
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from mikrotik_metadata import valid_antennas
from paper_figures import ANT_LABEL_OFFSET, OUT_ROOT, ROTATION_DATASETS
from paper_style import save
from plot_phase_over_time import load_phase_tracks


def phase_changes(avg_deg, raw_deg, raw_pos, level: str) -> np.ndarray:
    """Wrapped consecutive phase changes in radians, shape (n_samples - 1, n_antennas)."""
    if level == "batch":
        ph = np.radians(avg_deg)
        d = np.diff(ph, axis=0)
    else:
        ph = np.radians(raw_deg)
        d = np.diff(ph, axis=0)
        same_batch = np.floor(raw_pos[1:]) == np.floor(raw_pos[:-1])
        d = d[same_batch]
    return np.angle(np.exp(1j * d))


def plot_sorted_changes(name: str, level: str, antennas: list, out_dir: Path) -> None:
    _, _, avg, _, raw_ph, raw_pos = load_phase_tracks(name, antennas)
    d = np.sort(phase_changes(avg, raw_ph, raw_pos, level), axis=0)      # sort each antenna

    fig, ax = plt.subplots(figsize=(8, 4.8))
    cmap = plt.get_cmap("tab10")
    for k, a in enumerate(antennas):
        ax.plot(np.arange(1, len(d) + 1), d[:, k], lw=0.9, color=cmap(k % 10),
                ls=["-", "--", "-.", ":"][k // 10], label=f"Ant. {a + ANT_LABEL_OFFSET}")
    ax.set_ylim(-4, 4)
    ax.set_xlim(0, len(d))
    ax.set_xlabel("Sorted Sample Index")
    ax.set_ylabel("Phase Change (radians)")
    ax.set_title(f"Sorted Phase Changes per Antenna ({name}, {level}-level)", fontweight="bold")
    ax.grid(alpha=0.3)
    ax.legend(ncol=4, fontsize=6.5, loc="lower right", framealpha=0.9, columnspacing=0.8,
              handlelength=1.6)
    fig.tight_layout()
    save(fig, out_dir, f"fig_sorted_phase_changes_{level}")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", nargs="+", default=["rotation_outdoor_20m", "rotation_outdoor_15m"],
                    choices=list(ROTATION_DATASETS))
    ap.add_argument("--antennas", type=int, nargs="*", default=[int(a) for a in valid_antennas],
                    help="physical antenna indices (0-31) to plot")
    ap.add_argument("--level", choices=["batch", "packet"], default="batch")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    args = ap.parse_args()
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.usetex": False})
    for name in args.dataset:
        plot_sorted_changes(name, args.level, args.antennas, args.out / name)
        print(f"Wrote {args.out / name / f'fig_sorted_phase_changes_{args.level}.png'}")


if __name__ == "__main__":
    main()
