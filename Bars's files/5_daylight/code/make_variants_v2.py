"""Nomad - Experiment 1, extra shop variants for what the first 50 did not cover:
narrow streets (Ciutat Vella, Gracia) and deep shops (real Barcelona shops are 25-40 m deep).

Run from the nomad repo root (ai-methods environment):
    python "Bars's files/5_daylight/code/make_variants_v2.py"            # 30 variants, ids 50-79
Output: Bars's files/5_daylight/output/variants_v2.csv  (same columns as variants.csv)

In Grasshopper: point csv_path to variants_v2.csv, keep out_path = results.csv (the new ids
50-79 are added to the 50 old rows, nothing is overwritten), slider id from 50 to 79.
Then run predict_shops.py again: it trains on all 80 simulations.
"""
import argparse
import csv
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).resolve().parents[1] / "output"

# name: (low, high). Narrow streets and deep shops on purpose.
RANGES = {
    "depth_m": (8.0, 40.0),
    "width_m": (4.0, 20.0),
    "floor_height_m": (3.5, 5.0),
    "wwr": (0.3, 0.8),
    "win_height_target_m": (2.4, 3.2),
    "obs_dist_m": (3.0, 12.0),       # Ciutat Vella streets are 3-8 m wide
    "obs_height_m": (8.0, 30.0),
}


def latin_hypercube(n, d, rng):
    cut = (np.arange(n)[:, None] + rng.random((n, d))) / n
    for j in range(d):
        cut[:, j] = cut[rng.permutation(n), j]
    return cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--start-id", type=int, default=50, help="first id; keep it after the old ids")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    names = list(RANGES)
    u = latin_hypercube(args.n, len(names) + 1, rng)
    rows = []
    for i in range(args.n):
        r = {"id": args.start_id + i}
        for j, name in enumerate(names):
            lo, hi = RANGES[name]
            r[name] = round(lo + u[i, j] * (hi - lo), 2)
        r["lit_facades"] = 1 if u[i, -1] < 0.7 else 2   # most shops have only the street facade
        h = r["floor_height_m"]
        win_h = max(r["win_height_target_m"], r["wwr"] * h * 1.05)
        win_h = min(win_h, h - 0.3)
        sill = min(0.9, h - win_h - 0.1)
        r["win_height_m"] = round(win_h, 2)
        r["sill_m"] = round(max(sill, 0.1), 2)
        r["head_m"] = round(r["sill_m"] + r["win_height_m"], 2)
        rows.append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "variants_v2.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Wrote %d variants (ids %d-%d) to %s" % (len(rows), rows[0]["id"], rows[-1]["id"], out))
    print("streets %.1f-%.1f m, depths %.1f-%.1f m" % (
        min(r["obs_dist_m"] for r in rows), max(r["obs_dist_m"] for r in rows),
        min(r["depth_m"] for r in rows), max(r["depth_m"] for r in rows)))


if __name__ == "__main__":
    main()
