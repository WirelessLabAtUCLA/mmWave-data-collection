"""
Phase stability map of the 6x6 antenna array.

Each cell is one physical antenna (0-31, placed with mikrotik_metadata.ordering_sets; the
four corners have no CSI). Cell colour = phase variance of the raw packets, computed per
batch (table stationary) and averaged over all batches of a rotation dataset.

Phase variance is the angular variance 2 (1 - R), R = |mean(exp(j phi))|, so it lies in
[0, 2]: 0 = perfectly stable phase, ~2 = phase uniformly random.

Outlines
--------
  red : reliable antennas = mikrotik_metadata.valid_antennas (19: S/A+/A tier)

Labels are 1-indexed (#1..#32 = physical antenna index + 1). The code (valid_antennas,
CSI_ANTENNAS, --extra, --reliable ...) always uses 0-indexed physical indices; pass
--zero-indexed to label the cells with those instead.

Usage
-----
    python plot_phase_stability_map.py
    python plot_phase_stability_map.py --dataset rotation_outdoor_15m --extra 12 14
    python plot_phase_stability_map.py --reliable pipeline  # the 16 columns of session_data

Output (PDF + PNG): <datasets>/paper_figures/<dataset>/fig_phase_stability_map.{pdf,png}
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch, Rectangle

from mikrotik_metadata import ordering_sets, valid_antennas
from paper_figures import ANT_LABEL_OFFSET, PIPELINE_ANTENNAS, OUT_ROOT, ROTATION_DATASETS, _batch_info, _parse_measurements
from paper_style import save
from plot_phase_over_time import load_phase_tracks

N_ANT = 32
RELIABLE_COLOR = "#E5384F"
TITLE_COLOR = "#0B3C5D"
# dark blue (stable) -> light blue -> beige -> yellow (unstable)
CMAP = LinearSegmentedColormap.from_list(
    "stability", [(0.00, "#124A7C"), (0.25, "#2F78B5"), (0.40, "#6FA3D8"), (0.50, "#9CBFE6"),
                  (0.62, "#C5D1C6"), (0.75, "#F0E6B0"), (0.88, "#F8DC6A"), (1.00, "#FFD100")])
# ordering_sets coordinate -> grid index (x is mirrored: x=+3 is column 1; z=+3 is row 1)
_X_TO_COL = {3: 1, 2: 2, 1: 3, -1: 4, -2: 5, -3: 6}
_Z_TO_ROW = {3: 1, 2: 2, 1: 3, -1: 4, -2: 5, -3: 6}


def angular_variance(phase_rad: np.ndarray, axis: int = 0) -> np.ndarray:
    """2 (1 - R): 0 for identical phases, 2 for uniformly random (R -> 0)."""
    return 2.0 * (1.0 - np.abs(np.mean(np.exp(1j * phase_rad), axis=axis)))


def load_rotation_dataset_channel(name: str) -> int:
    """WiFi channel (1-4) of a rotation dataset, read from its first batch file."""
    import json
    path = ROTATION_DATASETS[name]
    with open(path / "metadata.json") as f:
        info = _batch_info(json.load(f)["data_points"][0])
    with open(path / info["file"]) as f:
        meas = _parse_measurements(json.load(f)["measurements"])
    return int(meas[0].channel)


def antenna_phase_variance(name: str):
    """Mean per-batch angular variance of every antenna (32,), and the dataset channel."""
    _, _, _, _, raw_ph, raw_pos = load_phase_tracks(name, list(range(N_ANT)))
    channel = load_rotation_dataset_channel(name)
    batch = np.floor(raw_pos).astype(int)
    ph = np.radians(raw_ph)
    var = np.array([angular_variance(ph[batch == b], axis=0) for b in np.unique(batch)])
    return var.mean(axis=0), channel


def plot_map(var: np.ndarray, title: str, subtitle: str, reliable: List[int], out_dir: Path,
             one_indexed: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 6.2))
    norm = Normalize(0.0, 2.0)
    off = 1 if one_indexed else 0

    # corners (no CSI)
    for r, c in [(1, 1), (1, 6), (6, 1), (6, 6)]:
        ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1, fc="#D0D0D0", ec="white", lw=1.5))

    for a in range(N_ANT):
        c = _X_TO_COL[int(ordering_sets[a, 0])]
        r = _Z_TO_ROW[int(ordering_sets[a, 1])]
        rgba = CMAP(norm(var[a]))
        ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1, fc=rgba, ec="white", lw=1.5))
        lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
        tc = "white" if lum < 0.55 else "#1A1A1A"
        ax.text(c, r - 0.1, f"#{a + off}", ha="center", va="center", color=tc, fontsize=13,
                fontweight="bold")
        ax.text(c, r + 0.22, f"{var[a]:.2f}", ha="center", va="center", color=tc, fontsize=10)
        if a in reliable:
            ax.add_patch(Rectangle((c - 0.44, r - 0.44), 0.88, 0.88, fc="none", ec=RELIABLE_COLOR,
                                   lw=2.6, zorder=5))

    ax.set_xlim(0.5, 6.5)
    ax.set_ylim(6.5, 0.5)
    ax.set_aspect("equal")
    ax.set_xticks(range(1, 7))
    ax.set_yticks(range(1, 7))
    ax.set_xlabel("Column", fontsize=13)
    ax.set_ylabel("Row", fontsize=13)
    ax.tick_params(labelsize=11)
    fig.suptitle(title, fontsize=15, fontweight="bold", color=TITLE_COLOR, x=0.5, y=0.995)
    ax.set_title(subtitle, fontsize=10, color="#555555", pad=4)

    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=CMAP), ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Raw phase variance", fontsize=12)
    cb.ax.tick_params(labelsize=11)

    handles = [Patch(fc="none", ec=RELIABLE_COLOR, lw=2.5, label=f"Reliable antenna ({len(reliable)})"),
               Patch(fc="#D0D0D0", ec="none", label="No CSI (corners)")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=10,
               bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(left=0.085, right=0.80, top=0.925, bottom=0.125)
    save(fig, out_dir, "fig_phase_stability_map")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", nargs="+", default=["rotation_outdoor_20m", "rotation_outdoor_15m"],
                    choices=list(ROTATION_DATASETS))
    ap.add_argument("--extra", type=int, nargs="*", default=[],
                    help="antennas (0-31 indices) added to the reliable set")
    ap.add_argument("--reliable", choices=["pipeline", "valid"], default="valid",
                    help="valid: mikrotik_metadata.valid_antennas (19); pipeline: the 16 columns of session_data (PIPELINE_ANTENNAS)")
    ap.add_argument("--zero-indexed", dest="one_indexed", action="store_false",
                    help="label antennas 0..31 (code indexing) instead of 1..32")
    ap.set_defaults(one_indexed=bool(ANT_LABEL_OFFSET))
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    args = ap.parse_args()

    reliable = PIPELINE_ANTENNAS if args.reliable == "pipeline" else [int(a) for a in valid_antennas]
    reliable = reliable + [a for a in args.extra if a not in reliable]
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.usetex": False})
    for name in args.dataset:
        var, channel = antenna_phase_variance(name)
        title = "Phase Stability Map: 6$\\times$6 Array"
        plot_map(var, title, f"Raw CSI (no post-processing), {name}, channel {channel}", reliable, args.out / name, args.one_indexed)
        print(f"Wrote {args.out / name / 'fig_phase_stability_map.png'}")


if __name__ == "__main__":
    main()
