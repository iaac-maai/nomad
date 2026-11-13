"""Experiment 1, step 1: make the list of factory-floor variants to simulate.

Latin hypercube sampling: every parameter range is cut into N equal slices and each slice is
used exactly once, so 50 variants cover the whole range evenly (better than pure random).

Run from the repo root:
    python "Bars's files/5_daylight/code/make_variants.py"            # 50 variants
    python "Bars's files/5_daylight/code/make_variants.py" --n 300    # later, more data
Output: Bars's files/5_daylight/output/variants.csv  (Grasshopper reads this file)
"""
import argparse
import csv
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).resolve().parents[1] / "output"

RANGES = {
    "depth_m": (8.0, 25.0),           # shop depth
    "width_m": (4.0, 12.0),           # street frontage
    "floor_height_m": (3.0, 4.5),     # ground-floor height
    "wwr": (0.20, 0.80),              # shop windows are large
    "win_height_target_m": (2.0, 3.5),
    "obs_dist_m": (8.0, 20.0),        # street width (Eixample is about 20 m)
    "obs_height_m": (12.0, 25.0),     # apartment block across the street
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
        r["lit_facades"] = 2 if u[i, -1] < 0.2 else 1   # 80 % street only, 20 % also a back patio
        h = r["floor_height_m"]
        # Honeybee keeps the ratio: if the ratio needs taller windows, they get taller.
        win_h = max(r["win_height_target_m"], r["wwr"] * h * 1.05)
        win_h = min(win_h, h - 0.3)
        sill = min(0.9, h - win_h - 0.1)
        r["win_height_m"] = round(win_h, 2)
        r["sill_m"] = round(max(sill, 0.1), 2)
        r["head_m"] = round(r["sill_m"] + r["win_height_m"], 2)
        rows.append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "variants.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Wrote %d variants to %s" % (len(rows), out))
    print("Next: open Grasshopper and follow the guide (gh_read_variant.py / gh_record_result.py).")


if __name__ == "__main__":
    main()
