"""
Publication-quality (IEEE) evaluation figures for the mmWave CSI dataset.

Figures
-------
  phase    : raw vs post-processed CSI phase over time        (rotation table data)
  af       : theoretical array factor vs measured pattern      (rotation table data)
  time     : measurement-timestamp stability                   (rotation table data)
  height   : per-antenna phase sensitivity to TX height        (height-sweep data)

Usage
-----
    python paper_figures.py --fig all
    python paper_figures.py --fig phase af --dataset rotation_outdoor_15m
    python paper_figures.py --fig af --align-boresight

Outputs (vector PDF + 300 dpi PNG) go to  <datasets>/paper_figures/<dataset>/.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from antenna_array import AntennaArray
from mikrotik_metadata import legacy_valid_antennas, ordering_sets, valid_antennas
from paper_style import (BLUE, COLORS, DARK, DOUBLE_COL, GRAY, LIGHTBLUE, LIGHTRED, MIDBLUE,
                         MIDRED, RED, SINGLE_COL, apply_style, arrow_axes, callout,
                         new_figure, panel_label, save)
from session_data import FREQ_CHANNELS, RouterMeasurement
from scipy.signal import savgol_filter
from utils import process_csi_data

# ---------------------------------------------------------------------------
# Paths / dataset registry
# ---------------------------------------------------------------------------
DATASETS_ROOT = Path("/home/kanishka/mmWave-datasets")
RAW_ROOT = DATASETS_ROOT / "raw"
OUT_ROOT = DATASETS_ROOT / "paper_figures"

ROTATION_DATASETS = {
    "rotation_outdoor_15m": RAW_ROOT / "rotation_table_data" / "rotation_outdoor_15m",
    "rotation_outdoor_20m": RAW_ROOT / "rotation_table_data" / "rotation_outdoor_20m",
    "rotation_indoor_80_direct": RAW_ROOT / "rotation_table_data" / "rotation_indoor_80_direct",
    "rotation_indoor_80_tx_high": RAW_ROOT / "rotation_table_data" / "rotation_indoor_80_tx_high",
}
MAIN_ROTATION_DATASET = "rotation_outdoor_15m"
# NOTE: data_catalog.yaml lists this as "2025-11-05/session_1519278" (typo).
HEIGHT_SESSION = RAW_ROOT / "2025-11-05" / "session_151928"

# Columns of the CSI matrix used for every figure -> physical antenna index: the 19 reliable
# (S / A+ / A tier) antennas, mikrotik_metadata.valid_antennas.
CSI_ANTENNAS = [int(a) for a in valid_antennas]
N_CSI = len(CSI_ANTENNAS)
# Outlier detection (utils.process_csi_data) is tuned to the 16-column matrix of the data-loading
# pipeline (session_data.RouterBatch.from_file: antennas 0-9, 11, 13, 21, 23, 25, 27). To keep the
# packet selection identical to that pipeline it is run on those 16 columns; the packets it keeps
# are then reused for all CSI_ANTENNAS (see load_batch).
PIPELINE_ANTENNAS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27]

PHASE_LUT = np.linspace(0, 2 * np.pi, 1024)


# ---------------------------------------------------------------------------
# Data containers / loaders
# ---------------------------------------------------------------------------
@dataclass
class BatchData:
    batch_id: int
    angle_deg: float                 # table angle (rotation datasets), NaN otherwise
    wall_time: float                 # seconds since session start (from batch timestamp)
    t_meas: np.ndarray               # router `measurement_time` per valid packet [s]
    t_sys: np.ndarray                # host `system_timestamp` per valid packet [s]
    H_raw: np.ndarray                # (N, N_CSI) complex, before post-processing
    H_proc: np.ndarray               # (M, N_CSI) complex, after post-processing
    kept: np.ndarray                 # indices into H_raw of surviving packets
    channel: int

    @property
    def n_removed(self) -> int:
        return len(self.H_raw) - len(self.H_proc)


@dataclass
class RotationDataset:
    name: str
    path: Path
    channel: int
    freq_ghz: float
    batches: List[BatchData] = field(default_factory=list)
    half_range_deg: float = 60.0


def _parse_measurements(strings: List[str]):
    """Parse raw measurement strings; silently skip malformed ones."""
    meas = []
    for s in strings:
        try:
            meas.append(RouterMeasurement.from_string(s))
        except (ValueError, IndexError):
            continue
    return meas


def build_csi_all(measurements: List[RouterMeasurement]) -> np.ndarray:
    """Unit-magnitude complex CSI of all 32 antennas (N, 32)."""
    phase_idx = np.array([m.phase for m in measurements]).astype(int)
    return np.exp(1j * PHASE_LUT[phase_idx])


def build_csi(measurements: List[RouterMeasurement]) -> np.ndarray:
    """Unit-magnitude complex CSI (N, N_CSI) of the CSI_ANTENNAS."""
    return build_csi_all(measurements)[:, CSI_ANTENNAS]


def smooth_csi(H: np.ndarray, window: int = 9, order: int = 1) -> np.ndarray:
    """Savitzky-Golay smoothing of real/imag parts, as in utils.process_csi_data (needs >= window rows)."""
    if H.shape[0] < window:
        return H
    return savgol_filter(H.real, window, order, axis=0) + 1j * savgol_filter(H.imag, window, order, axis=0)


def load_batch(json_path: Path, batch_id: int, angle_deg: float, wall_time: float) -> Optional[BatchData]:
    with open(json_path) as f:
        data = json.load(f)
    meas = _parse_measurements(data["measurements"])
    if not meas:
        return None
    H_all = build_csi_all(meas)
    H_raw = H_all[:, CSI_ANTENNAS]
    # packets kept by the pipeline's outlier removal (process_csi_data can clip in place -> copy)
    _, kept = process_csi_data(H_all[:, PIPELINE_ANTENNAS].copy(), return_kept_indices=True)
    H_proc = smooth_csi(H_raw[kept])
    return BatchData(
        batch_id=batch_id,
        angle_deg=angle_deg,
        wall_time=wall_time,
        t_meas=np.array([m.measurement_time for m in meas]),
        t_sys=np.array([m.system_timestamp for m in meas]),
        H_raw=H_raw,
        H_proc=H_proc,
        kept=kept,
        channel=int(meas[0].channel),
    )


def _batch_info(dp: dict) -> dict:
    return dp.get("csi_batch") or dp.get("router_batch")


def load_rotation_dataset(name: str) -> RotationDataset:
    """Load a rotation-table dataset, recovering the true table angle of each batch.

    The table sweeps -H..+H deg in 1 deg steps, one batch per angle, and
    batch_id == (original angle index). metadata.json may have been cleaned
    (bad batches removed, indices renumbered), but batch_id is preserved. The
    sweep size is taken from the metadata_backup_*.json if one exists.
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
    batches: List[BatchData] = []
    for dp in dps:
        info = _batch_info(dp)
        wall = float((np.datetime64(dp["timestamp"]) - t0) / np.timedelta64(1, "s"))
        b = load_batch(path / info["file"], info["batch_id"],
                       angle_deg=info["batch_id"] - half, wall_time=wall)
        if b is not None:
            batches.append(b)
    batches.sort(key=lambda b: b.batch_id)

    channel = batches[0].channel
    return RotationDataset(name=name, path=path, channel=channel,
                           freq_ghz=FREQ_CHANNELS[channel], batches=batches,
                           half_range_deg=half)


# ---------------------------------------------------------------------------
# Array geometry
# ---------------------------------------------------------------------------
def array_geometry(freq_ghz: float) -> np.ndarray:
    """Element positions (x, z) in wavelengths for the CSI columns -> (N_CSI, 2)."""
    spacing = 0.58 * freq_ghz / 60.48
    o = ordering_sets[CSI_ANTENNAS].astype(float)
    return o * spacing - np.sign(o) * spacing / 2


def theoretical_array_factor(freq_ghz: float, az_rad: np.ndarray, el_rad: float = 0.0) -> np.ndarray:
    """Complex array factor of the ideal boresight-steered (unit weight) array."""
    xz = array_geometry(freq_ghz)
    arr = AntennaArray()
    for x, z in xz:
        arr.add_element(x, 0.0, z)
    arr.set_weights(arr.get_conjugate_beamformer(0.0, 0.0))
    a = arr.get_array_response(az_rad, el_rad)       # (16, N)
    return arr.weights @ a


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
def circ_std_deg(phase_rad: np.ndarray, axis: int = 0) -> np.ndarray:
    """Circular standard deviation in degrees (sqrt(-2 ln R))."""
    R = np.abs(np.mean(np.exp(1j * phase_rad), axis=axis))
    return np.degrees(np.sqrt(-2.0 * np.log(np.clip(R, 1e-12, 1.0))))


def wrap_deg(phase_rad: np.ndarray) -> np.ndarray:
    return np.degrees(np.angle(np.exp(1j * phase_rad)))


def dataset_phase_stats(ds: RotationDataset) -> Dict[str, float]:
    """Aggregate raw-vs-processed phase statistics over every batch/antenna."""
    raw_std, proc_std, n_raw, n_removed = [], [], 0, 0
    for b in ds.batches:
        raw_std.append(circ_std_deg(np.angle(b.H_raw), axis=0))
        if len(b.H_proc) > 1:
            proc_std.append(circ_std_deg(np.angle(b.H_proc), axis=0))
        n_raw += len(b.H_raw)
        n_removed += b.n_removed
    return {
        "raw_std_deg": float(np.mean(raw_std)),
        "proc_std_deg": float(np.mean(proc_std)),
        "removed_frac": n_removed / n_raw,
        "n_packets": n_raw,
        "n_batches": len(ds.batches),
    }


# ---------------------------------------------------------------------------
# Figure 1: raw vs post-processed phase (4x4 antenna grid, as in visualize.plot_csi_phase_data)
# ---------------------------------------------------------------------------
def fig_phase_cleanup(ds: RotationDataset, out_dir: Path) -> Dict:
    stats = dataset_phase_stats(ds)

    # As in visualize.plot_csi_phase_data: one panel per antenna, phase over the whole
    # session (one averaged post-processed CSI per batch). Here the batch index is
    # shown as the table angle, and the raw packets of every batch are overlaid.
    h = ds.half_range_deg
    ang = np.array([b.angle_deg for b in ds.batches])
    avg_phase = np.degrees(np.angle(np.array([b.H_proc.mean(axis=0) for b in ds.batches])))  # (B, N_CSI)

    # raw packets: spread over the 1 deg slot of their batch in acquisition order
    raw_x = np.concatenate([
        b.angle_deg - 0.5 + (np.arange(len(b.H_raw)) + 0.5) / len(b.H_raw) for b in ds.batches])
    raw_phase = np.degrees(np.angle(np.concatenate([b.H_raw for b in ds.batches])))          # (P, N_CSI)

    # break the averaged line where the phase wraps around +-180 deg
    line_x, line_y = ang.astype(float), avg_phase.copy()
    wrap = np.abs(np.diff(avg_phase, axis=0)) > 180

    # Raw packets (~26k per antenna) are drawn as a small occupancy image instead of
    # individual markers: sharp at any zoom, and the PDF stays light / fast to render.
    from matplotlib.colors import LinearSegmentedColormap
    from scipy.ndimage import gaussian_filter
    x_edges = np.linspace(-h - 0.5, h + 0.5, 361)
    y_edges = np.linspace(-180, 180, 211)
    # opaque white -> pink ramp (no alpha: avoids soft-mask artifacts in PDF viewers; a smooth
    # ramp also keeps matplotlib from writing a <=4-bit indexed image, which some viewers misread)
    pink = LinearSegmentedColormap.from_list("pink_ramp", ["white", "#EFA3A9"], N=256)

    ncols = 5
    nrows = -(-N_CSI // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(DOUBLE_COL, 1.28 * nrows), sharex=True, sharey=True)
    for c in range(N_CSI):
        ax = axes[c // ncols, c % ncols]
        occ, _, _ = np.histogram2d(raw_x, raw_phase[:, c], bins=[x_edges, y_edges])
        img = np.clip(gaussian_filter((occ.T > 0).astype(float), 0.6) / 0.45, 0, 1)
        ax.imshow(np.ascontiguousarray(img), cmap=pink, vmin=0, vmax=1, origin="lower",
                  extent=(x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]), aspect="auto",
                  interpolation="nearest", zorder=1)
        y = line_y[:, c].copy()
        xs, ys = [line_x[0]], [y[0]]
        for i in range(1, len(y)):
            if wrap[i - 1, c]:
                xs.append(np.nan)
                ys.append(np.nan)
            xs.append(line_x[i])
            ys.append(y[i])
        ax.plot(xs, ys, "-", color=BLUE, lw=1.0, zorder=3)
        ax.plot(ang, y, ".", color=BLUE, ms=2.0, mew=0, zorder=4)
        ax.set_ylim(-190, 190)
        ax.set_yticks([-180, 0, 180])
        ax.set_xlim(-h, h)
        ax.set_xticks(np.arange(-int(h), int(h) + 1, 30 if h <= 60 else 40))
        ax.text(0.04, 0.95, f"Ant. {CSI_ANTENNAS[c]}", transform=ax.transAxes, ha="left", va="top",
                fontsize=6.5, fontweight="bold", color=DARK,
                bbox=dict(fc="white", ec="none", pad=0.5))
    for k in range(N_CSI, nrows * ncols):
        axes[k // ncols, k % ncols].set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel(r"Table angle (deg)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Phase (deg)")

    fig.subplots_adjust(left=0.07, right=0.995, top=0.915, bottom=0.085, wspace=0.12, hspace=0.16)
    # direct, colored labels instead of a legend
    fig.text(0.07, 0.955, r"$\bullet$", color=MIDRED, fontsize=8, ha="left", va="center")
    fig.text(0.085, 0.955, "Raw CSI", color=RED, fontsize=8, fontweight="bold", ha="left", va="center")
    fig.text(0.16, 0.955, r"$\bullet$", color=BLUE, fontsize=8, ha="left", va="center")
    fig.text(0.175, 0.955, "Post-processed, batch-averaged", color=BLUE, fontsize=8, fontweight="bold",
             ha="left", va="center")
    fig.text(0.995, 0.955,
             rf"Mean phase spread $\bar\sigma_\phi$: {stats['raw_std_deg']:.1f}$^\circ$ $\rightarrow$ "
             rf"{stats['proc_std_deg']:.1f}$^\circ$   |   {100 * stats['removed_frac']:.0f}\% of packets removed",
             color=GRAY, fontsize=7, ha="right", va="center")
    save(fig, out_dir, "fig_phase_cleanup")
    plt.close(fig)
    return stats


# ---------------------------------------------------------------------------
# Figure 2: element factor / beam direction (method of extract_element_factor.py)
# ---------------------------------------------------------------------------
def build_antenna_array(freq_ghz: float) -> AntennaArray:
    """Array built exactly as in extract_element_factor.py::extract_peak_theta."""
    spacing = 0.58 * freq_ghz / 60.48
    arr = AntennaArray()
    for ant in CSI_ANTENNAS:
        arr.add_element(ordering_sets[ant, 0] * spacing - np.sign(ordering_sets[ant, 0]) * spacing / 2,
                        0,
                        ordering_sets[ant, 1] * spacing - np.sign(ordering_sets[ant, 1]) * spacing / 2)
    return arr


def element_factor_analysis(ds: RotationDataset, el_deg: float = 3.0, align_boresight: bool = False):
    """Per table angle: measured/ideal array response toward the TX, and the beamformer peak.

    Follows extract_element_factor.py: weights = conj(averaged processed CSI);
      * peak direction : argmax of get_array_pattern_azimuth (extract_peak_theta);
      * element factor : |w_real . a(theta)| / |w_ideal . a(theta)| with
                         w_ideal = get_conjugate_beamformer(theta, el), i.e. /N.
    The table angle is mapped to azimuth with an auto-detected sign (the table
    rotates opposite to the array's azimuth axis).
    """
    el = np.deg2rad(el_deg)
    arr = build_antenna_array(ds.freq_ghz)
    N = arr.num_antennas
    table = np.array([b.angle_deg for b in ds.batches])
    csi_avg = np.array([b.H_proc.mean(axis=0) for b in ds.batches])

    def ef_for(sign, offset=0.0):
        out = []
        for h, a in zip(csi_avg, table):
            arr.set_weights(np.conjugate(h))
            out.append(np.abs(arr.get_array_gain(np.deg2rad(sign * a + offset), el)) / N)
        return np.array(out)

    # auto-detect the table <-> azimuth sign convention
    sign = 1 if ef_for(1).mean() >= ef_for(-1).mean() else -1
    offset = 0.0
    if align_boresight:
        cand = np.arange(-8, 8.01, 0.5)
        score = [np.mean(20 * np.log10(ef_for(sign, o)[np.abs(table) <= 30])) for o in cand]
        offset = float(cand[int(np.argmax(score))])
    theta = sign * table + offset                     # steering azimuth (deg)

    ef_line, ef_lo, ef_hi, peak = [], [], [], []
    az_scan = np.linspace(-np.pi, np.pi, 1024, endpoint=False)
    front = np.abs(az_scan) <= np.pi / 2              # array is planar: restrict to the front half
    for b, h, th in zip(ds.batches, csi_avg, theta):
        a = arr.get_array_response(np.deg2rad(th), el)                       # (N,)
        arr.set_weights(np.conjugate(h))
        ef_line.append(np.abs(arr.get_array_gain(np.deg2rad(th), el)) / N)
        per_pkt = np.abs(np.conjugate(b.H_proc) @ a) / N
        ef_lo.append(np.percentile(per_pkt, 16))
        ef_hi.append(np.percentile(per_pkt, 84))
        resp, _, _ = arr.get_array_pattern_azimuth(el, 1024, full=True)
        peak.append(np.degrees(az_scan[front][np.argmax(np.abs(resp[front]))]))
    order = np.argsort(theta)
    return dict(theta=theta[order], ef=np.array(ef_line)[order], ef_lo=np.array(ef_lo)[order],
                ef_hi=np.array(ef_hi)[order], peak=np.array(peak)[order], sign=sign, offset=offset)


def _db(a):
    return 20 * np.log10(np.maximum(a, 1e-4))


def sum_beam_curves(ds: RotationDataset, theta_deg: np.ndarray, az_deg: np.ndarray):
    """Boresight 'sum of channel data' vs true azimuth, as in extract_ef.ipynb (cell 4).

    Per batch: |sum over antennas of the CSI| (== response of the boresight-steered
    conjugate beamformer), for raw packets (10/50/90th percentile) and for the
    averaged post-processed CSI; plus the ideal array factor. All curves are
    normalised to the peak of the averaged curve (the ideal one to its own peak).
    """
    raw = [np.abs(b.H_raw.sum(axis=1)) for b in ds.batches]
    r_lo, r_md, r_hi = (np.array([np.percentile(x, q) for x in raw]) for q in (10, 50, 90))
    avg = np.array([np.abs(b.H_proc.mean(axis=0).sum()) for b in ds.batches])
    o = np.argsort(theta_deg)
    th, k = theta_deg[o], avg[o].max()
    af = np.abs(theoretical_array_factor(ds.freq_ghz, np.deg2rad(az_deg), 0.0))
    return dict(theta=th, raw_lo=r_lo[o] / k, raw_med=r_md[o] / k, raw_hi=r_hi[o] / k,
                avg=avg[o] / k, af=af / af.max())


def fig_array_factor(ds: RotationDataset, out_dir: Path, el_deg: float = 3.0,
                     align_boresight: bool = False) -> Dict:
    r = element_factor_analysis(ds, el_deg, align_boresight)
    th, peak = r["theta"], r["peak"]
    ef_db = _db(r["ef"])
    # table angle -> true azimuth for every batch (ordered like ds.batches)
    theta_batches = r["sign"] * np.array([b.angle_deg for b in ds.batches]) + r["offset"]
    az_grid = np.linspace(-ds.half_range_deg, ds.half_range_deg, 721)
    bc = sum_beam_curves(ds, theta_batches, az_grid)

    # Range over which the estimated beam direction can be trusted (first two consecutive
    # estimates, ordered by |theta|, that are more than 20 deg off)
    err = peak - th
    o = np.argsort(np.abs(th))
    bad = np.abs(err[o]) > 20
    first_bad = next((i for i in range(len(bad) - 1) if bad[i] and bad[i + 1]), None)
    valid_deg = float(np.abs(th[o][first_bad])) if first_bad is not None else float(np.abs(th).max())
    ok = np.abs(th) < valid_deg
    mae_valid = float(np.median(np.abs(err[ok]))) if ok.any() else float("nan")   # robust to isolated outliers
    slope = float(np.polyfit(th[ok], peak[ok], 1)[0]) if ok.sum() > 2 else float("nan")

    h = int(ds.half_range_deg)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(SINGLE_COL, 4.1), sharex=True,
                                   gridspec_kw=dict(hspace=0.2, height_ratios=[1, 1.1]))

    # (a) received beam: sum of channel data vs azimuth, measured vs theoretical array factor
    ax1.fill_between(bc["theta"], bc["raw_lo"], bc["raw_hi"], color=LIGHTBLUE, lw=0, zorder=1)
    ax1.plot(az_grid, bc["af"], color=RED, ls="--", lw=1.3, zorder=2)
    ax1.plot(bc["theta"], bc["avg"], color=BLUE, lw=1.6, zorder=3)
    ax1.set_ylim(0, 1.12)
    ax1.set_yticks([0, 0.5, 1.0])
    ax1.set_ylabel("Normalized beam\nmagnitude", color=BLUE)
    ax1.tick_params(labelbottom=False)
    th_c = bc["theta"]
    i_av = int(np.argmin(np.abs(th_c - 17)))
    i_rw = int(np.argmin(np.abs(th_c + 36)))
    callout(ax1, "Averaged CSI", xy=(th_c[i_av], bc["avg"][i_av] + 0.01),
            xytext=(th_c[i_av] + 17, 0.88), color=BLUE)
    callout(ax1, "Raw (10\u201390%)", xy=(th_c[i_rw], 0.5 * (bc["raw_lo"][i_rw] + bc["raw_hi"][i_rw])),
            xytext=(th_c[i_rw] + 4, 0.62), color=MIDBLUE)
    callout(ax1, "Array factor\n(ideal)", xy=(-8, float(np.interp(-8, az_grid, bc["af"]))),
            xytext=(-38, 0.93), color=RED)
    arrow_axes(ax1, x=False)
    panel_label(ax1, "(a)", x=-0.25, y=1.0, ha="left", va="top")

    # (b) beam direction
    ax2.axvspan(valid_deg, h + 5, color="#FAE6E8", lw=0, zorder=0)
    ax2.axvspan(-h - 5, -valid_deg, color="#FAE6E8", lw=0, zorder=0)
    ax2.plot([-h, h], [-h, h], color=RED, ls="--", lw=1.0, zorder=2)
    ax2.plot(th, peak, "o", color=BLUE, ms=2.2, mew=0, zorder=3)
    ax2.plot(th, np.where(np.abs(err) <= 20, peak, np.nan), "-", color=BLUE, lw=1.4, zorder=3)
    ax2.set_ylim(-95, 95)
    ax2.set_yticks([-90, -45, 0, 45, 90])
    ax2.set_xlim(-h, h)
    ax2.set_xticks(np.arange(-h, h + 1, 20))
    ax2.set_xlabel(r"True azimuth $\theta$ (deg)")
    ax2.set_ylabel(r"Beamformer peak $\hat{\theta}$ (deg)", color=BLUE)
    ax2.text(-0.62 * valid_deg, 0.45 * valid_deg + 14, r"Ideal ($\hat{\theta}=\theta$)", color=RED,
             fontsize=6.5, fontweight="bold", ha="center")
    if valid_deg < h:
        ax2.text(0.5 * (valid_deg + h), -80, "spurious\npeaks", color=RED, fontsize=6, ha="center",
                 va="center", style="italic")
        ax2.text(-0.5 * (valid_deg + h), -80, "spurious\npeaks", color=RED, fontsize=6, ha="center",
                 va="center", style="italic")
    arrow_axes(ax2)
    panel_label(ax2, "(b)", x=-0.25, y=1.0, ha="left", va="top")

    save(fig, out_dir, "fig_array_factor")
    plt.close(fig)
    return dict(azimuth_sign=r["sign"], offset_deg=r["offset"], el_deg=el_deg,
                beam_peak_deg=float(bc["theta"][np.argmax(bc["avg"])]),
                ef_mean_db=float(ef_db.mean()),
                ef_boresight_db=float(ef_db[np.argmin(np.abs(th))]),
                ef_min_db=float(ef_db.min()),
                peak_valid_range_deg=valid_deg, peak_median_abs_err_valid_deg=mae_valid,
                peak_slope_valid=slope, freq_ghz=ds.freq_ghz)


def fig_element_factor(ds: RotationDataset, out_dir: Path, el_deg: float = 3.0,
                       align_boresight: bool = False) -> Dict:
    """Element factor (measured / ideal beamformer response toward the TX) vs azimuth."""
    r = element_factor_analysis(ds, el_deg, align_boresight)
    th = r["theta"]
    ef_db, lo_db, hi_db = _db(r["ef"]), _db(r["ef_lo"]), _db(r["ef_hi"])
    h = int(ds.half_range_deg)
    fig, ax1 = plt.subplots(figsize=(SINGLE_COL, 2.0))
    lo_plot = min(-12, np.floor(ef_db.min() - 2))
    ax1.axhline(0, color=RED, ls="--", lw=1.0, zorder=2)
    ax1.fill_between(th, lo_db, hi_db, color=LIGHTBLUE, lw=0, zorder=1)
    ax1.plot(th, ef_db, color=BLUE, lw=1.6, zorder=3)
    ax1.set_ylim(lo_plot, 3)
    ax1.set_xlim(-h, h)
    ax1.set_xticks(np.arange(-h, h + 1, 20))
    ax1.set_xlabel(r"True azimuth $\theta$ (deg)")
    ax1.set_ylabel("Element factor (dB)", color=BLUE)
    ax1.text(0.99, 0.05, "Ideal beamformer (0 dB)", transform=ax1.get_yaxis_transform(),
             color=RED, fontsize=6.5, fontweight="bold", ha="right", va="bottom")
    ax1.set_yticks(np.arange(5 * np.ceil(lo_plot / 5), 1, 5))
    mid = int(np.argmin(np.abs(th - (-0.45 * h))))
    callout(ax1, "Measured (mean, \u00b11 std)", xy=(th[mid], ef_db[mid] + 0.4),
            xytext=(th[mid] + 0.12 * h, -2.6), color=BLUE)
    arrow_axes(ax1)
    save(fig, out_dir, "fig_element_factor")
    plt.close(fig)
    return dict(ef_mean_db=float(ef_db.mean()), ef_min_db=float(ef_db.min()))


# ---------------------------------------------------------------------------
# Figure 3: measurement-timestamp stability
# ---------------------------------------------------------------------------
def fig_timestamp_stability(ds: RotationDataset, out_dir: Path) -> Dict:
    t0 = ds.batches[0].t_meas[0]
    t_all, dt_all, batch_mean_t, batch_mean_dt, gaps, starts = [], [], [], [], [], []
    for i, b in enumerate(ds.batches):
        dt = np.diff(b.t_meas) * 1e3                       # ms, within a batch
        t_all.append((b.t_meas[1:] - t0) / 60.0)           # min
        dt_all.append(dt)
        batch_mean_t.append((b.t_meas.mean() - t0) / 60.0)
        batch_mean_dt.append(dt.mean())
        starts.append(b.t_meas[0])
        if i > 0:
            gaps.append(b.t_meas[0] - ds.batches[i - 1].t_meas[-1])
    t_all, dt_all = np.concatenate(t_all), np.concatenate(dt_all)

    # Router clock vs host clock: constant offset => both clocks agree
    clk = np.concatenate([(b.t_sys - b.t_meas) for b in ds.batches]) * 1e3   # ms
    clk_dev = clk - np.median(clk)

    mu, sd, med = dt_all.mean(), dt_all.std(), np.median(dt_all)
    p1, p99 = np.percentile(dt_all, [1, 99])

    # interval between consecutive batches (start of one batch to start of the next)
    bint = np.diff(starts)
    b_mu, b_sd = bint.mean(), bint.std()
    b_p1, b_p99 = np.percentile(bint, [1, 99])

    y_lo, y_hi = 20, 60
    fig, ax_a = plt.subplots(figsize=(DOUBLE_COL, 2.25))
    ax_a.plot(t_all, dt_all, ".", color="#9CC3E6", ms=1.2, mew=0)
    ax_a.plot(batch_mean_t, batch_mean_dt, "-", color=BLUE, lw=1.6, zorder=4)
    ax_a.axhline(mu, color=RED, ls="--", lw=1.0, zorder=3)
    ax_a.set_xlabel("Elapsed time (min)")
    ax_a.set_ylabel("Inter-measurement\ninterval (ms)")
    ax_a.set_xlim(0, t_all.max())
    ax_a.set_ylim(y_lo, y_hi)
    x_end = t_all.max()
    callout(ax_a, rf"Overall mean = {mu:.1f} ms", xy=(0.86 * x_end, mu + 0.3),
            xytext=(0.86 * x_end, 41.5), color=RED)
    callout(ax_a, "Individual packets", xy=(0.26 * x_end, 36.5), xytext=(0.26 * x_end, 47.5), color=MIDBLUE,
            fontweight="bold")
    callout(ax_a, "Per-batch mean", xy=(0.58 * x_end, mu + 0.2), xytext=(0.58 * x_end, 24.0), color=BLUE,
            fontweight="bold")
    arrow_axes(ax_a)
    ax_a.set_title(rf"Between packets:   $\mu$ = {mu:.1f} ms,   $\sigma$ = {sd:.1f} ms,   "
                   rf"1–99% range: [{p1:.0f}, {p99:.0f}] ms" "\n"
                   rf"Between batches:   $\mu$ = {b_mu:.2f} s,   $\sigma$ = {b_sd:.2f} s,   "
                   rf"1–99% range: [{b_p1:.2f}, {b_p99:.2f}] s",
                   fontsize=7.5, color=BLUE, fontweight="bold", pad=4, linespacing=1.4)

    fig.subplots_adjust(left=0.085, right=0.985, top=0.85, bottom=0.2)
    save(fig, out_dir, "fig_timestamp_stability")
    plt.close(fig)
    return dict(n_intervals=len(dt_all), mean_ms=float(mu), std_ms=float(sd),
                median_ms=float(med), p1_ms=float(p1), p99_ms=float(p99),
                max_ms=float(dt_all.max()),
                inter_batch_gap_median_s=float(np.median(gaps)),
                batch_interval_mean_s=float(b_mu), batch_interval_std_s=float(b_sd),
                batch_interval_p1_s=float(b_p1), batch_interval_p99_s=float(b_p99),
                clock_offset_dev_max_ms=float(np.abs(clk_dev).max()),
                clock_offset_dev_std_ms=float(clk_dev.std()))


# ---------------------------------------------------------------------------
# Figure 4: which antennas react to TX height changes
# ---------------------------------------------------------------------------
def load_height_session(path: Path = HEIGHT_SESSION):
    """Per-batch packet-averaged, post-processed CSI (T, N_CSI) of the height-sweep session."""
    with open(path / "metadata.json") as f:
        meta = json.load(f)
    A, ids = [], []
    for dp in meta["data_points"]:
        info = _batch_info(dp)
        b = load_batch(path / info["file"], info["batch_id"], np.nan, 0.0)
        if b is None or len(b.H_proc) == 0:
            continue
        A.append(b.H_proc.mean(axis=0))
        ids.append(info["batch_id"])
        freq = FREQ_CHANNELS[b.channel]
    return np.array(A), np.array(ids), freq


def fig_height_sensitivity(out_dir: Path, ref_col: int = 0, n_show: int = 2,
                           path: Path = HEIGHT_SESSION) -> Dict:
    from scipy.stats import spearmanr
    from matplotlib.colors import LinearSegmentedColormap

    A, ids, freq = load_height_session(path)
    xz = array_geometry(freq)                       # wavelengths
    rel = np.angle(A * np.conj(A[:, [ref_col]]))    # phase relative to reference antenna (T, N_CSI)
    sigma = circ_std_deg(rel, axis=0)               # per-antenna sensitivity [deg]

    dz = np.abs(xz[:, 1] - xz[ref_col, 1])
    others = np.array([c for c in range(N_CSI) if c != ref_col])
    rho = float(spearmanr(sigma[others], dz[others])[0])
    stagnant = others[np.argsort(sigma[others])[:n_show]]
    varying = others[np.argsort(sigma[others])[::-1][:n_show]]

    fig = plt.figure(figsize=(DOUBLE_COL, 2.7))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.6], wspace=0.34,
                          left=0.065, right=0.975, top=0.93, bottom=0.17)
    ax_map, ax_ph = (fig.add_subplot(gs[0, i]) for i in range(2))

    # (a) array layout colored by phase variability (blue = stagnant, red = height-sensitive)
    cmap = LinearSegmentedColormap.from_list("br", [LIGHTBLUE, MIDBLUE, "#F4D6D9", MIDRED, RED])
    vmax = max(120, sigma.max())
    sc = ax_map.scatter(xz[:, 0], xz[:, 1], c=sigma, cmap=cmap, vmin=0, vmax=vmax, s=235,
                        edgecolor=DARK, linewidth=0.6, zorder=3)
    for c in range(N_CSI):
        ax_map.text(xz[c, 0], xz[c, 1], str(CSI_ANTENNAS[c]), ha="center", va="center",
                    fontsize=6, color=DARK, zorder=4)
    ax_map.scatter(*xz[ref_col], s=400, facecolor="none", edgecolor=RED, linewidth=1.2, zorder=5,
                   linestyle="--")
    ax_map.set_xlabel(r"$x$ ($\lambda$)")
    ax_map.set_ylabel(r"$z$ ($\lambda$)")
    ax_map.set_aspect("equal")
    ax_map.set_xlim(xz[:, 0].min() - 0.6, xz[:, 0].max() + 0.6)
    ax_map.set_ylim(xz[:, 1].min() - 0.6, xz[:, 1].max() + 0.75)
    arrow_axes(ax_map)
    callout(ax_map, "reference", xy=(xz[ref_col, 0] - 0.18, xz[ref_col, 1] + 0.12),
            xytext=(xz[ref_col, 0] - 1.2, xz[ref_col, 1] + 0.5), color=RED, fontweight="bold")
    cb = fig.colorbar(sc, ax=ax_map, fraction=0.05, pad=0.04, aspect=22)
    cb.set_label(r"Phase variability $\sigma_\phi$ (deg)")
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=2)
    ax_map.text(0.99, 0.02, rf"$\rho(\sigma_\phi,|\Delta z|)$ = {rho:.2f}", transform=ax_map.transAxes,
                ha="right", va="bottom", fontsize=6.5, color=GRAY, fontweight="bold")
    panel_label(ax_map, "(a)", x=-0.02, y=1.04, ha="right", va="bottom")

    # (b) relative phase over the sweep: stagnant (blue) vs height-sensitive (red)
    k = np.arange(len(rel))
    unw = np.degrees(np.unwrap(rel, axis=0) - np.unwrap(rel, axis=0)[0])
    shades = {"stag": [BLUE, MIDBLUE], "var": [RED, MIDRED]}
    ymax_plot = unw[:, np.r_[stagnant, varying]].max()
    ymin_plot = unw[:, np.r_[stagnant, varying]].min()
    ax_ph.axhline(0, color=GRAY, lw=0.5, zorder=0)
    labels = []
    for kind, cols in (("stag", stagnant), ("var", varying)):
        for j, c in enumerate(cols):
            col = shades[kind][j]
            ax_ph.plot(k, unw[:, c], "-o", color=col, lw=1.5, ms=2.6, mew=0, zorder=3)
            labels.append((unw[-1, c], f"Ant. {CSI_ANTENNAS[c]}", col, sigma[c]))
    # direct end-of-line labels (de-overlapped vertically)
    labels.sort(key=lambda t: t[0])
    min_gap = 0.065 * (ymax_plot - ymin_plot + 40)
    ys = [t[0] for t in labels]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + min_gap)
    for (y0, name, col, sg), y in zip(labels, ys):
        ax_ph.text(len(rel) - 0.4, y, f"{name}", color=col, fontsize=6.5, fontweight="bold",
                   va="center", ha="left")
    ax_ph.set_xlim(-0.3, len(rel) + 1.6)
    ax_ph.set_ylim(ymin_plot - 25, ymax_plot + 40)
    ax_ph.set_xticks(k[::2])
    ax_ph.set_xlabel("Measurement batch (chronological; TX height varying)")
    ax_ph.set_ylabel(f"Phase change vs. ant. {CSI_ANTENNAS[ref_col]} (deg)")
    arrow_axes(ax_ph)
    callout(ax_ph, rf"Stagnant: $\sigma_\phi$ = {sigma[stagnant].min():.0f}–{sigma[stagnant].max():.0f}$^\circ$",
            xy=(2.2, unw[2, stagnant[0]] + 4), xytext=(4.2, ymax_plot + 22), color=BLUE,
            fontweight="bold", ha="left")
    callout(ax_ph, rf"Height-sensitive: $\sigma_\phi$ = {sigma[varying].min():.0f}–{sigma[varying].max():.0f}$^\circ$",
            xy=(8.0, unw[8, varying[0]] - 4), xytext=(2.2, ymin_plot - 10), color=RED,
            fontweight="bold", ha="left")
    panel_label(ax_ph, "(b)", x=-0.02, y=1.04, ha="right", va="bottom")

    save(fig, out_dir, "fig_height_sensitivity")
    plt.close(fig)
    return dict(n_batches=len(rel), ref_antenna=CSI_ANTENNAS[ref_col], spearman_sigma_vs_dz=rho,
                sigma_deg={CSI_ANTENNAS[c]: float(sigma[c]) for c in range(N_CSI)},
                stagnant=[CSI_ANTENNAS[c] for c in stagnant], varying=[CSI_ANTENNAS[c] for c in varying],
                same_row_mean_sigma=float(sigma[(dz < 1e-6) & (np.arange(N_CSI) != ref_col)].mean()),
                other_row_mean_sigma=float(sigma[dz > 1e-6].mean()))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fig", nargs="+", default=["all"],
                    choices=["all", "phase", "af", "time", "height"])
    ap.add_argument("--dataset", nargs="+", default=["all"],
                    choices=["all"] + list(ROTATION_DATASETS),
                    help="rotation dataset(s) for phase/af/time figures")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--el-deg", type=float, default=3.0,
                    help="elevation used for the element-factor analysis (extract_element_factor.py uses 3)")
    ap.add_argument("--align-boresight", action="store_true",
                    help="remove a constant table-angle offset (chosen to maximise the element factor)")
    ap.add_argument("--no-latex", dest="latex", action="store_false",
                    help="disable LaTeX text rendering (LaTeX is used by default if installed)")
    ap.set_defaults(latex=True)
    args = ap.parse_args()

    apply_style(use_latex=args.latex)
    figs = {"phase", "af", "time", "height"} if "all" in args.fig else set(args.fig)
    names = list(ROTATION_DATASETS) if "all" in args.dataset else args.dataset

    summary: Dict[str, Dict] = {}
    for name in names:
        if not figs & {"phase", "af", "time"}:
            break
        print(f"[{name}] loading ...")
        ds = load_rotation_dataset(name)
        out = args.out / name
        summary[name] = {"channel": ds.channel, "freq_ghz": ds.freq_ghz, "n_batches": len(ds.batches),
                         "sweep_deg": [-ds.half_range_deg, ds.half_range_deg]}
        if "phase" in figs:
            summary[name]["phase"] = fig_phase_cleanup(ds, out)
        if "af" in figs:
            summary[name]["af"] = fig_array_factor(ds, out, el_deg=args.el_deg,
                                                   align_boresight=args.align_boresight)
            fig_element_factor(ds, out, el_deg=args.el_deg, align_boresight=args.align_boresight)
        if "time" in figs:
            summary[name]["time"] = fig_timestamp_stability(ds, out)
    if "height" in figs:
        print("[height] session_151928 ...")
        summary["height_session_151928"] = fig_height_sensitivity(args.out / "height_session_151928")

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "figure_stats.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print(json.dumps(summary, indent=2, default=float))
    print(f"\nFigures written to {args.out}")


if __name__ == "__main__":
    main()
