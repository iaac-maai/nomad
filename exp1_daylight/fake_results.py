"""TEST ONLY: make FAKE results so you can try train_daylight.py before Rhino is ready.

The numbers come from a made-up formula, not from Ladybug. Never present them.

Run from the repo root:
    python exp1_daylight/make_variants.py
    python exp1_daylight/fake_results.py
    python exp1_daylight/train_daylight.py --results exp1_daylight/results_FAKE.csv
"""
import csv
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
random.seed(1)

with open(HERE / "variants.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

for r in rows:
    depth, head = float(r["depth_m"]), float(r["head_m"])
    wwr, lit = float(r["wwr"]), int(r["lit_facades"])
    angle = math.atan2(float(r["obs_height_m"]), float(r["obs_dist_m"]))
    sky = max(0.15, math.cos(angle) ** 2)                      # less sky behind a tall neighbour
    reach = min(1.0, lit * 2.5 * head / depth)                 # how much of the floor is near a window
    mean_df = 9.0 * wwr * sky * (0.35 + 0.65 * reach) * random.uniform(0.85, 1.15)
    r["mean_df"] = round(mean_df, 3)
    r["share_df2"] = round(min(1.0, reach * min(1.0, mean_df / 2.0)), 3)
    r["n_sensors"] = int(float(r["width_m"]) * depth)

out = HERE / "results_FAKE.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("Wrote FAKE results to %s (test only, do not present)" % out)
