"""Nomad - light wells (patis de llums) in the shop shapes, from the Catastro building parts.

  patios       holes in the ground floor (union of the parts with >= 1 floor): open to the sky at ground level.
               No flat may be built over them.
  wells_above  holes in a part with >= 2 floors that the ground floor roofs over: the shop's floor runs under them
               (a roof could be opened). Kept as information; not blocked.
Both in the shell's local metres (same origin as the outline). Adds the two keys to results/real_shops/shells.json and
site/data/shells.json; nothing else changes.
Run: .venv/Scripts/python src/building/light_wells.py
"""
import gzip, json, sys
from pathlib import Path
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "building"))
from real_shops import poly  # noqa: E402

MIN_M2 = 2.0


def wells(b):
    ground = poly([r for p in b["parts"] if (p["up"] or 0) >= 1 for r in p["poly"]]) or poly(b["foot"])
    if ground is None or ground.is_empty:
        return None, [], []
    if ground.geom_type == "MultiPolygon":
        ground = max(ground.geoms, key=lambda g: g.area)
    ground = ground.simplify(0.15, preserve_topology=True)        # as real_shops.py, so the origin matches
    open_ = [Polygon(h) for h in ground.interiors if Polygon(h).area >= MIN_M2]
    tall = [Polygon(r[0], r[1:]).buffer(0) for p in b["parts"] if (p["up"] or 0) >= 2 for r in p["poly"] if len(r) > 1]
    above = [Polygon(h) for g in tall for h in getattr(g, "interiors", []) if Polygon(h).area >= MIN_M2]
    covered = [w for w in above if ground.buffer(-0.05).intersection(w).area > 0.5 * w.area]
    return ground, open_, covered


def main():
    B = json.load(gzip.open(ROOT / "data/barcelona/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    R = ROOT / "results/real_shops/shells.json"
    S = json.load(open(R, encoding="utf-8"))
    n = {"shops": 0, "with patios": 0, "patios": 0, "with wells above": 0}
    add = {}
    for ref, s in S.items():
        ground, op, cov = wells(B[ref])
        if ground is None:
            continue
        x0, y0 = s["origin_utm"]
        loc = lambda g: [[round(x - x0, 2), round(y - y0, 2)] for x, y in list(g.exterior.coords)[:-1]]
        add[ref] = {"patios": [loc(g) for g in op], "wells_above": [loc(g) for g in cov]}
        n["shops"] += 1; n["with patios"] += bool(op); n["patios"] += len(op); n["with wells above"] += bool(cov)
    for path in (R, ROOT / "site/data/shells.json"):
        D = json.load(open(path, encoding="utf-8"))
        for ref, v in D.items():
            if ref in add:
                v.update(add[ref])
        json.dump(D, open(path, "w", encoding="utf-8"), separators=(",", ":"))
    print(n)


if __name__ == "__main__":
    main()
