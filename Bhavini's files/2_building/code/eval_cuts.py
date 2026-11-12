"""Nomad - how accurate are the assumed shop shapes (rules A and B, cut_shells.py)?
Truth = the premises' own unit in the Catastro floor plans (same choice as unit_shells.py: nearest shop unit to the
census door, within 8 m). Both compared in UTM metres.
  IoU      overlap / union (1 = same shape)
  covered  share of the true shop inside our shape
  area     our m2 / true m2
Also the old shape (the whole ground floor) for the same premises, as the baseline.
Out: 2_building/output/real_shops/cut_accuracy.json
Run: .venv/Scripts/python 2_building/code/eval_cuts.py
"""
import json, statistics as st, sys
from pathlib import Path
from shapely.geometry import Point, Polygon
from shapely import affinity

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "2_building/code"))
from catastro_shops import ground_units, NOT_SHOP, DOOR_MAX, FLOORS  # noqa: E402


def m(g, t):
    i = g.intersection(t).area
    return {"iou": i / g.union(t).area, "covered": i / t.area, "area": g.area / t.area}


def summ(v):
    if not v:
        return {"n": 0}
    return {"n": len(v), "iou_median": round(st.median(x["iou"] for x in v), 2),
            "iou_over_0.5_pct": round(100 * sum(x["iou"] >= 0.5 for x in v) / len(v)),
            "covered_median": round(st.median(x["covered"] for x in v), 2),
            "area_within_20pct_pct": round(100 * sum(0.8 <= x["area"] <= 1.2 for x in v) / len(v)),
            "area_ratio_median": round(st.median(x["area"] for x in v), 2)}


def main():
    S = json.load(open(ROOT / "2_building/output/real_shops/shells.json", encoding="utf-8"))
    C = json.load(open(ROOT / "app/data/cut_shells.json", encoding="utf-8"))
    P = json.load(open(ROOT / "app/data/premises.json", encoding="utf-8"))
    c = P["cols"].index
    res = {"A": [], "B": [], "footprint_same_A": [], "footprint_same_B": [], "footprint_all": []}
    for r in P["rows"]:
        ref = (r[c("ref")] or "")[:14]
        if ref not in S or not (FLOORS / (ref + ".json")).exists():
            continue
        units = [u for u in ground_units(ref) if not any(u["code"] == k or u["code"].startswith(k + ".") for k in NOT_SHOP)]
        door = Point(r[c("x")], r[c("y")])
        if not units:
            continue
        u = min(units, key=lambda u: u["poly"].distance(door))
        if u["poly"].distance(door) > DOOR_MAX:
            continue
        t = u["poly"]
        x0, y0 = S[ref]["origin_utm"]
        foot = affinity.translate(Polygon(S[ref]["outline"]).buffer(0), x0, y0)
        fm = m(foot, t)
        res["footprint_all"].append(fm)
        k = "%s|%s|%s" % (ref, r[c("x")], r[c("y")])
        if k in C:
            g = affinity.translate(Polygon(C[k]["outline"]).buffer(0), x0, y0)
            res[C[k]["rule"]].append(m(g, t))
            res["footprint_same_" + C[k]["rule"]].append(fm)
    out = {k: summ(v) for k, v in res.items()}
    json.dump(out, open(ROOT / "2_building/output/real_shops/cut_accuracy.json", "w", encoding="utf-8"), indent=1)
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
