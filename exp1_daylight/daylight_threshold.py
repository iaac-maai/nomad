"""Nomad - daylight-factor thresholds for Barcelona, following the EN 17037 method.

EN 17037 (daylight provision, vertical/inclined openings) asks for a target illuminance of
300 lx over 50 % of the room and a minimum of 100 lx over 95 %, for at least half of the
daylight hours. It turns lux into a daylight factor with the median outdoor diffuse
illuminance of the site:  D = E / Ev,d,med x 100.  This script takes Ev,d,med from a
Barcelona EPW weather file, so the thresholds are for Barcelona, not a guess.

Run in the "ai-methods" environment, from the nomad repo root:
    python exp1_daylight/daylight_threshold.py --epw path/to/ESP_CT_Barcelona....epw
Writes: exp1_daylight/daylight_thresholds.json  (read by predict_shops.py)
"""
import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TARGET_LX, MINIMUM_LX = 300.0, 100.0   # EN 17037, minimum level of daylight provision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epw", required=True, help="Barcelona EPW weather file")
    args = ap.parse_args()

    diffuse = []
    with open(args.epw, encoding="latin-1") as f:
        for k, line in enumerate(f):
            if k < 8:                   # 8 header lines
                continue
            v = line.strip().split(",")
            if len(v) > 18:
                diffuse.append(float(v[18]))   # field 19: diffuse horizontal illuminance (lux)
    diffuse = np.array(diffuse)
    day = diffuse[(diffuse > 0) & (diffuse < 999000)]   # daylight hours only; 999900/999999 = missing
    if len(day) < 1000:
        raise SystemExit("Too few daylight hours with illuminance data (%d). This EPW has no "
                         "illuminance values - use a TMYx file instead." % len(day))
    ev_med = float(np.median(day))
    d_target = 100 * TARGET_LX / ev_med
    d_min = 100 * MINIMUM_LX / ev_med

    out = {"source": Path(args.epw).name, "daylight_hours": int(len(day)),
           "Ev_d_med_lux": round(ev_med), "D_target_pct": round(d_target, 2),
           "D_minimum_pct": round(d_min, 2),
           "classes": {"livable": ">= D_target", "needs_change": "D_minimum to D_target", "not_livable": "< D_minimum"}}
    (HERE / "daylight_thresholds.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("daylight hours read: %d" % len(day))
    print("median outdoor diffuse illuminance Ev,d,med: %.0f lux" % ev_med)
    print("D for 300 lx (target):  %.2f %%   -> livable at or above" % d_target)
    print("D for 100 lx (minimum): %.2f %%   -> not livable below" % d_min)
    print("saved exp1_daylight/daylight_thresholds.json")


if __name__ == "__main__":
    main()
