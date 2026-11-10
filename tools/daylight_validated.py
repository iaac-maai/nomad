"""NOMAD - the 5 shops whose daylight was simulated in Radiance (Ladybug/Honeybee), for the website's
"validated examples". No prediction model is used: every number comes from the Radiance sensor grid.

Reads : exp1_daylight/results_shops.csv        the 5 real shops simulated in Grasshopper (one row each)
        exp1_daylight/daylight_thresholds.json  EN 17037 target / minimum daylight factor for Barcelona (TMYx)
Writes: Bhavini_NOMAD Files/04_Website/data/daylight_validated.json

Lit depth = how far from the window the row-average daylight factor stays at or above the EN 17037 target.
Run from the repo root:  python tools/daylight_validated.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "exp1_daylight"
OUT = ROOT / "Bhavini_NOMAD Files" / "04_Website" / "data" / "daylight_validated.json"


def lit_depth(df, ys, target):
    rows = defaultdict(list)                      # depth from the window -> every sensor at that depth
    for d, y in zip(df, ys):
        rows[round(y, 2)].append(d)
    depth = 0.0
    for y in sorted(rows):
        if sum(rows[y]) / len(rows[y]) < target:
            break
        depth = y
    return round(depth, 2)


def main():
    th = json.loads((EXP / "daylight_thresholds.json").read_text(encoding="utf-8"))
    target = th["D_target_pct"]
    shops = []
    with open(EXP / "results_shops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            df, ys = json.loads(r["df_values"]), json.loads(r["ys"])
            shops.append({"address": r["address"], "depth_m": float(r["depth_m"]), "width_m": float(r["width_m"]),
                          "mean_df_pct": float(r["mean_df"]), "sensors": int(r["n_sensors"]),
                          "lit_depth_m": lit_depth(df, ys, target)})
    out = {"about": "5 empty shops simulated in Radiance (Ladybug/Honeybee) by Bars, exp1_daylight/results_shops.csv. "
                    "Built by tools/daylight_validated.py. No prediction model.",
           "method": "EN 17037", "weather": th["source"], "target_pct": target, "minimum_pct": th["D_minimum_pct"],
           "assumed": "floor height 4,0 m, window-to-wall ratio 0,6, window head 3,9 m (exp1_daylight)",
           "shops": shops}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in shops:
        print(f"{s['address']:<20} mean DF {s['mean_df_pct']:.2f} %  lit depth {s['lit_depth_m']} m of {s['depth_m']} m")


if __name__ == "__main__":
    main()
