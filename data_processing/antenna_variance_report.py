"""
Cross-dataset consistency of the raw per-antenna phase variance (all 32 antennas).

For every dataset used in paper_figures (4 rotation-table sets + the height session), the raw
(unprocessed) phase variance of each antenna is computed per batch as the angular variance
2 (1 - R), R = |mean(exp(j phi))| over the packets of the batch (see plot_phase_stability_map.py),
then averaged over batches.

Because 2 (1 - R) is biased low for small packet counts (indoor sets have 10 packets, the height session 5, per
batch, outdoor sets 100-250), a size-matched variant is also computed: each batch is cut into
non-overlapping chunks of `--chunk` packets (default 5 = the height session batch size) and the variance is averaged over chunks.
Cross-dataset comparison and tiers use the size-matched values.

Output: <datasets>/paper_figures/antenna_variance_summary.json  (+ printed tables)

Usage
-----
    python antenna_variance_report.py
    python antenna_variance_report.py --chunk 10   # skips nothing but needs >=10 packets/batch
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import numpy as np
from scipy.stats import spearmanr

from paper_figures import HEIGHT_SESSION, OUT_ROOT, PHASE_LUT, ROTATION_DATASETS, _batch_info, _parse_measurements

N_ANT = 32


def ang_var(phase: np.ndarray) -> np.ndarray:
    """Angular variance 2 (1 - R) along axis 0 -> (n_ant,)."""
    return 2.0 * (1.0 - np.abs(np.mean(np.exp(1j * phase), axis=0)))


def dataset_paths() -> Dict[str, Path]:
    d = {k: v for k, v in ROTATION_DATASETS.items()}
    d["height_session_151928"] = HEIGHT_SESSION
    return d


def dataset_variance(path: Path, chunk: int) -> Dict:
    with open(path / "metadata.json") as f:
        dps = json.load(f)["data_points"]
    full, chunked, n_pk, channel = [], [], [], None
    for dp in dps:
        info = _batch_info(dp)
        with open(path / info["file"]) as f:
            meas = _parse_measurements(json.load(f)["measurements"])
        if len(meas) < 2:
            continue
        channel = int(meas[0].channel)
        ph = PHASE_LUT[np.array([m.phase for m in meas]).astype(int)]        # (N, 32) raw phase
        full.append(ang_var(ph))
        n_pk.append(len(ph))
        n_chunks = len(ph) // chunk
        if n_chunks:
            chunked.append(np.mean([ang_var(ph[i * chunk:(i + 1) * chunk]) for i in range(n_chunks)], axis=0))
    full, chunked = np.array(full), np.array(chunked)
    return dict(channel=channel, n_batches=len(full), packets_per_batch=float(np.median(n_pk)),
                var_full=full.mean(axis=0), var_chunk=chunked.mean(axis=0),
                var_chunk_batch_std=chunked.std(axis=0))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunk", type=int, default=5, help="packets per chunk for the size-matched variance")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    args = ap.parse_args()

    res = {}
    for name, path in dataset_paths().items():
        print(f"[{name}] ...")
        res[name] = dataset_variance(path, args.chunk)
        r = res[name]
        print(f"   channel {r['channel']}, {r['n_batches']} batches, ~{r['packets_per_batch']:.0f} packets/batch")

    names = list(res)
    V = np.array([res[n]["var_chunk"] for n in names])          # (D, 32), size-matched
    print(f"\nSize-matched ({args.chunk}-packet chunks) raw phase variance, rows = antenna")
    print("ant  " + " ".join(f"{n[-12:]:>12}" for n in names) + "   mean   min   max   CV")
    for a in range(N_ANT):
        m, cv = V[:, a].mean(), V[:, a].std() / max(V[:, a].mean(), 1e-9)
        print(f"{a:>3}  " + " ".join(f"{V[d, a]:12.3f}" for d in range(len(names)))
              + f"  {m:5.2f} {V[:, a].min():5.2f} {V[:, a].max():5.2f} {cv:4.2f}")

    print("\nSpearman rank correlation between datasets (size-matched variance):")
    for i in range(len(names)):
        print("  ".join(f"{spearmanr(V[i], V[j])[0]:5.2f}" for j in range(len(names))), "  ", names[i])

    summary = {n: {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()}
               for n, r in res.items()}
    summary["_chunk"] = args.chunk
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "antenna_variance_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {args.out / 'antenna_variance_summary.json'}")


if __name__ == "__main__":
    main()
