"""
Per-antenna CSI phase over time for a rotation-table dataset.

Plots the reliable antennas (mikrotik_metadata.valid_antennas, S/A+/A tier). One panel per antenna:

  * pink  : raw per-packet phase (occupancy image)
  * blue  : post-processed, batch-averaged phase (one point per batch)

Post-processing follows paper_figures.py: the packets kept for the 16 CSI columns
(paper_figures.PIPELINE_ANTENNAS) are reused for every antenna, followed by the same
Savitzky-Golay smoothing before averaging.

Usage
-----
    python plot_phase_over_time.py
    python plot_phase_over_time.py --dataset rotation_outdoor_15m --antennas 0 1 2 3
    python plot_phase_over_time.py --time-axis angle

Output (PDF + PNG): <datasets>/paper_figures/<dataset>/fig_phase_time.{pdf,png}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter
from scipy.signal import savgol_filter

from mikrotik_metadata import valid_antennas
from paper_figures import (PIPELINE_ANTENNAS, OUT_ROOT, PHASE_LUT, ROTATION_DATASETS, _batch_info,
                           _parse_measurements)
from paper_style import BLUE, DARK, DOUBLE_COL, MIDRED, RED, apply_style, save
from utils import process_csi_data



def load_phase_tracks(name: str, antennas: List[int]):
    """Return (t_min, angle_deg, avg_phase_deg (B, A), raw_t_min (P,), raw_phase_deg (P, A),
    raw_batch_pos (P,) = batch index + fractional position inside the batch).

    Antenna columns are physical indices into the 32-column phase vector.
    """
    path = ROTATION_DATASETS[name]
    with open(path / "metadata.json") as f:
        meta = json.load(f)
    dps = meta["data_points"]
    n_orig = max(_batch_info(dp)["batch_id"] for dp in dps) + 1
    for bk in sorted(path.glob("metadata_backup_*.json")):
        with open(bk) as f:
            n_orig = max(n_orig, len(json.load(f)["data_points"]))
    half = (n_orig - 1) / 2.0
    t0 = np.datetime64(meta["start_time"])

    t_batch, ang, avg, raw_t, raw_ph, raw_frac = [], [], [], [], [], []
    for dp in sorted(dps, key=lambda d: _batch_info(d)["batch_id"]):
        info = _batch_info(dp)
        with open(path / info["file"]) as f:
            meas = _parse_measurements(json.load(f)["measurements"])
        if not meas:
            continue
        t_wall = float((np.datetime64(dp["timestamp"]) - t0) / np.timedelta64(1, "s"))
        idx = np.array([m.phase for m in meas]).astype(int)
        H_all = np.exp(1j * PHASE_LUT[idx])                      # (N, 32), unit magnitude

        # packets kept by the pipeline's outlier removal, exactly like paper_figures.load_batch
        _, kept = process_csi_data(H_all[:, PIPELINE_ANTENNAS].copy(), return_kept_indices=True)
        Hk = H_all[kept][:, antennas]
        if len(Hk) >= 9:
            Hk = savgol_filter(Hk.real, 9, 1, axis=0) + 1j * savgol_filter(Hk.imag, 9, 1, axis=0)

        t_batch.append(t_wall / 60.0)
        ang.append(info["batch_id"] - half)
        avg.append(np.degrees(np.angle(Hk.mean(axis=0))))

        # raw packets spread over the batch's wall-clock interval via measurement_time
        tm = np.array([m.measurement_time for m in meas], dtype=float)
        tm = (tm - tm[0]) / 60.0
        raw_t.append(t_wall / 60.0 + tm)
        raw_ph.append(np.degrees(np.angle(H_all[:, antennas])))
        raw_frac.append(len(t_batch) - 1 + (np.arange(len(meas)) + 0.5) / len(meas))  # batch pos

    return (np.array(t_batch), np.array(ang), np.array(avg),
            np.concatenate(raw_t), np.concatenate(raw_ph), np.concatenate(raw_frac))


def plot_phase_over_time(name: str, antennas: List[int], out_dir: Path, time_axis: str = "time"):
    t_min, ang, avg, raw_t, raw_ph, raw_pos = load_phase_tracks(name, antennas)

    if time_axis == "angle":
        x, xlabel = ang, "Table angle (deg)"
        # raw packets: spread over the 1 deg slot of their batch
        bi = np.floor(raw_pos).astype(int)
        raw_x = ang[bi] - 0.5 + (raw_pos - bi)
    else:
        x, xlabel, raw_x = t_min, "Time since start (min)", raw_t

    x_edges = np.linspace(x.min() - 0.1, x.max() + 0.1, 361)
    y_edges = np.linspace(-180, 180, 211)
    pink = LinearSegmentedColormap.from_list("pink_ramp", ["white", "#EFA3A9"], N=256)

    ncols = 5
    nrows = int(np.ceil(len(antennas) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(DOUBLE_COL * 1.25, 1.25 * nrows + 0.5),
                             sharex=True, sharey=True)
    axes = np.atleast_2d(axes)
    for c, ant in enumerate(antennas):
        ax = axes[c // ncols, c % ncols]
        occ, _, _ = np.histogram2d(raw_x, raw_ph[:, c], bins=[x_edges, y_edges])
        img = np.clip(gaussian_filter((occ.T > 0).astype(float), 0.6) / 0.45, 0, 1)
        ax.imshow(np.ascontiguousarray(img), cmap=pink, vmin=0, vmax=1, origin="lower",
                  extent=(x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]), aspect="auto",
                  interpolation="nearest", zorder=1)
        y = avg[:, c]
        xs, ys = [x[0]], [y[0]]
        for i in range(1, len(y)):          # break the line at +-180 deg wraps
            if abs(y[i] - y[i - 1]) > 180:
                xs.append(np.nan)
                ys.append(np.nan)
            xs.append(x[i])
            ys.append(y[i])
        color = BLUE
        ax.plot(xs, ys, "-", color=color, lw=0.9, zorder=3)
        ax.plot(x, y, ".", color=color, ms=1.8, mew=0, zorder=4)
        ax.set_ylim(-190, 190)
        ax.set_yticks([-180, 0, 180])
        ax.set_xlim(x_edges[0], x_edges[-1])
        ax.text(0.04, 0.95, f"Ant. {ant}", transform=ax.transAxes,
                ha="left", va="top", fontsize=6.5, fontweight="bold",
                color=DARK, bbox=dict(fc="white", ec="none", pad=0.5))
    for k in range(len(antennas), nrows * ncols):
        axes[k // ncols, k % ncols].set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel(xlabel)
    for ax in axes[:, 0]:
        ax.set_ylabel("Phase (deg)")

    fig.subplots_adjust(left=0.06, right=0.995, top=0.93, bottom=0.08, wspace=0.12, hspace=0.16)
    fig.text(0.06, 0.965, r"$\bullet$", color=MIDRED, fontsize=8, ha="left", va="center")
    fig.text(0.072, 0.965, "Raw CSI", color=RED, fontsize=8, fontweight="bold", ha="left", va="center")
    fig.text(0.13, 0.965, r"$\bullet$", color=BLUE, fontsize=8, ha="left", va="center")
    fig.text(0.142, 0.965, "Post-processed, batch-averaged", color=BLUE, fontsize=8,
             fontweight="bold", ha="left", va="center")
    save(fig, out_dir, "fig_phase_time")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="rotation_outdoor_20m", choices=list(ROTATION_DATASETS))
    ap.add_argument("--antennas", type=int, nargs="*", default=[int(a) for a in valid_antennas],
                    help="physical antenna indices (0-31) to plot (default: mikrotik_metadata.valid_antennas)")
    ap.add_argument("--time-axis", choices=["time", "angle"], default="time")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--no-latex", dest="latex", action="store_false")
    ap.set_defaults(latex=True)
    args = ap.parse_args()

    apply_style(use_latex=args.latex)
    plot_phase_over_time(args.dataset, args.antennas, args.out / args.dataset, args.time_axis)
    print(f"Wrote {args.out / args.dataset / 'fig_phase_time.png'}")


if __name__ == "__main__":
    main()
