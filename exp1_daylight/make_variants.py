"""Experiment 1, step 1: make the list of factory-floor variants to simulate.

Latin hypercube sampling: every parameter range is cut into N equal slices and each slice is
used exactly once, so 50 variants cover the whole range evenly (better than pure random).

Run from the repo root:
    python exp1_daylight/make_variants.py            # 50 variants
    python exp1_daylight/make_variants.py --n 300    # later, more data
Output: exp1_daylight/variants.csv  (Grasshopper reads this file)
"""
import argparse
import csv
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

# name: (low, high) in metres or as a ratio
RANGES = {
    "depth_m": (10.0, 30.0),         # distance from the window facade to the back
    "width_m": (12.0, 40.0),         # facade length
    "floor_height_m": (3.0, 6.0),    # floor to ceiling (old factories are tall)
    "wwr": (0.15, 0.60),             # window-to-wall ratio of each lit facade
    "win_height_target_m": (1.2, 2.6),
    "obs_dist_m": (6.0, 30.0),       # distance to the building opposite
    "obs_height_m": (0.0, 25.0),     # height of the building opposite (0 = open)
}


def latin_hypercube(n, d, rng):
    cut = (np.arange(n)[:, None] + rng.random((n, d))) / n
    for j in range(d):
        cut[:, j] = cut[rng.permutation(n), j]
    return cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    names = list(RANGES)
    u = latin_hypercube(args.n, len(names) + 1, rng)   # +1 column for the number of lit facades
    rows = []
    for i in range(args.n):
        r = {"id": i}
        for j, name in enumerate(names):
            lo, hi = RANGES[name]
            r[name] = round(lo + u[i, j] * (hi - lo), 2)
        r["lit_facades"] = 1 if u[i, -1] < 0.5 else 2   # 1 = street side only, 2 = street + back
        h = r["floor_height_m"]
        # Honeybee keeps the ratio: if the ratio needs taller windows, they get taller.
        win_h = max(r["win_height_target_m"], r["wwr"] * h * 1.05)
        win_h = min(win_h, h - 0.3)
        sill = min(0.9, h - win_h - 0.1)
        r["win_height_m"] = round(win_h, 2)
        r["sill_m"] = round(max(sill, 0.1), 2)
        r["head_m"] = round(r["sill_m"] + r["win_height_m"], 2)
        rows.append(r)

    out = HERE / "variants.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Wrote %d variants to %s" % (len(rows), out))
    print("Next: open Grasshopper and follow the guide (gh_read_variant.py / gh_record_result.py).")


if __name__ == "__main__":
    main()
