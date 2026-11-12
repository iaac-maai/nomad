"""Nomad - grade the plan reader on the test plans with known answers (7_floor_plans/input/datasets/test_plans).

For every plan: read it twice, once with the true scale given (like a user typing the façade length)
and once with the scale estimated from the drawing. Compare with the truth:
  outline overlap (IoU, 1 = perfect), area error, façade length error, scale error.
Run with the floorplan-to-3d environment (needs torch) + shapely:
  tools/borrowed_code/floorplan-to-3d/.venv/Scripts/python 2_building/code/eval_read_plan.py [limit]
Outputs: 2_building/output/plan_reading/eval.csv, 2_building/output/plan_reading/eval_summary.json
Comparing wall readers / plan sets (2_building/output/plan_reading/compare/<tag>.csv + <tag>.json):
  ... eval_read_plan.py --plans test_plans_messy --walls mitunet --given-only [--limit 60]
"""
import argparse, json, sys
from pathlib import Path
import pandas as pd
from shapely.geometry import Polygon
from shapely import affinity

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "2_building/code"))
import read_plan  # noqa: E402

TP = ROOT / "7_floor_plans/input/datasets/test_plans"
OUT = ROOT / "2_building/output/plan_reading"


def norm(poly):
    minx, miny, _, _ = poly.bounds
    return affinity.translate(poly, -minx, -miny)


def main(limit=None, plans="test_plans", walls="f3d", given_only=False):
    tp = ROOT / "7_floor_plans/input/datasets" / plans
    truth = json.load(open(tp / "truth.json"))
    rows = []
    for i, (sid, t) in enumerate(list(truth.items())[:limit]):
        T = norm(Polygon(t["outline_m"]).buffer(0))
        img = next(tp.glob(f"{sid}.*g"))
        for mode in (("scale given",) if given_only else ("scale given", "scale estimated")):
            r = read_plan.read(img, px_per_m=t["px_per_m"] if mode == "scale given" else None, walls=walls)
            row = {"shell_id": sid, "mode": mode, "true_area": t["area_m2"], "true_facade": t["facade_m"], "ok": r.get("ok")}
            if r.get("ok"):
                R = norm(Polygon(r["outline"]).buffer(0))
                inter = R.intersection(T).area
                row.update(read_area=r["area_m2"], read_facade=r["facade_m"], scale=r["scale_px_per_m"],
                           iou=round(inter / max(R.union(T).area, 1e-9), 3),
                           area_err=round(abs(r["area_m2"] - t["area_m2"]) / t["area_m2"], 3),
                           facade_err=round(abs(r["facade_m"] - t["facade_m"]) / max(t["facade_m"], 1), 3),
                           scale_err=round(abs(r["scale_px_per_m"] - t["px_per_m"]) / t["px_per_m"], 3),
                           rotation=r["rotation_deg"])
            rows.append(row)
        if i % 20 == 0:
            print(f"  {i + 1}/{len(truth)}", flush=True)
    df = pd.DataFrame(rows)
    default = plans == "test_plans" and walls == "f3d" and not given_only and limit is None
    out = OUT if default else OUT / "compare"
    tag = "eval" if default else f"{plans}__{walls}"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"{tag}.csv", index=False)
    summ = {}
    for mode, g in df.groupby("mode"):
        summ[mode] = {"plans": len(g), "read_ok": int(g.ok.sum()),
                      "median_iou": round(float(g.iou.median()), 3), "iou_over_0.8": round(float((g.iou > 0.8).mean()), 3),
                      "median_area_error": round(float(g.area_err.median()), 3),
                      "area_within_10pct": round(float((g.area_err < 0.10).mean()), 3),
                      "median_facade_error": round(float(g.facade_err.median()), 3),
                      "median_scale_error": round(float(g.scale_err.median()), 3)}
    json.dump(summ, open(out / ("eval_summary.json" if default else f"{tag}.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("limit", nargs="?", type=int)
    ap.add_argument("--limit", dest="limit2", type=int)
    ap.add_argument("--plans", default="test_plans")
    ap.add_argument("--walls", default="f3d", choices=["f3d", "f3d_only", "mitunet", "dark", "scans", "scans_only"])
    ap.add_argument("--given-only", action="store_true")
    a = ap.parse_args()
    main(a.limit or a.limit2, a.plans, a.walls, a.given_only)
