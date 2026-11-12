"""Nomad - the premises' own Catastro unit as its design shape, for every empty premises in a parcel with a Catastro floor plan.
Same unit and facade logic as catastro_shops.py (nearest non-residential, non-common ground-floor unit, at most 8 m from the door).
Out: app/data/unit_shells.json {"ref|x|y": {"outline", "facade", "street", "m2", "use", "floors"}}
Run: .venv/Scripts/python 2_building/code/unit_shells.py
"""
import gzip, json, math, sys
from collections import Counter
from pathlib import Path
from shapely.geometry import Point
from shapely.strtree import STRtree
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "2_building/code"))
from catastro_shops import ground_units, poly, FLOORS, NOT_SHOP, DOOR_MAX  # noqa: E402


def main():
    P = json.load(open(ROOT / "app/data/premises.json", encoding="utf-8"))
    c = P["cols"].index
    rows = [r for r in P["rows"] if (FLOORS / ((r[c("ref")] or "")[:14] + ".json")).exists()]
    print("premises in parcels with a plan:", len(rows), flush=True)
    B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    foots = [g for g in (poly(b["foot"]) for b in B.values()) if g is not None and not g.is_empty]
    btree = STRtree(foots)
    Z = json.load(open(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson", encoding="utf-8"))["features"]
    streets = [shape(f["geometry"]).buffer(0) for f in Z if (f["properties"]["C_QUAL_MUC"] or "").startswith("SX")]
    stree = STRtree(streets)
    out, st, skip = {}, Counter(), {}
    for r in rows:
        ref = r[c("ref")][:14]
        units = ground_units(ref)
        door = Point(r[c("x")], r[c("y")])
        cand = [u for u in units if not any(u["code"] == k or u["code"].startswith(k + ".") for k in NOT_SHOP)]
        key = "%s|%s|%s" % (ref, r[c("x")], r[c("y")])
        if not cand:
            st["no shop unit"] += 1; skip[key] = "no shop unit"; continue
        u = min(cand, key=lambda u: u["poly"].distance(door))
        if u["poly"].distance(door) > DOOR_MAX:
            st["door far from any unit"] += 1; skip[key] = "door %d m from the nearest unit" % round(u["poly"].distance(door)); continue
        g = u["poly"].simplify(0.15, preserve_topology=True)
        ext = list(g.exterior.coords)
        if g.exterior.is_ccw:
            ext = ext[::-1]
        others = [v["poly"] for v in units if v is not u]
        inside = lambda p: g.contains(p) or any(o.contains(p) for o in others) or any(foots[int(i)].contains(p) for i in btree.query(p))
        street, opened = [], []
        for a, b in zip(ext[:-1], ext[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 0.8:
                continue
            nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            q, far = Point(mx + 1.5 * nx, my + 1.5 * ny), Point(mx + 6.0 * nx, my + 6.0 * ny)
            if any(streets[int(i)].contains(q) for i in stree.query(q)):
                street.append((a, b))
            elif not inside(q) and not inside(far):
                opened.append((a, b))
        x0, y0 = g.bounds[0], g.bounds[1]
        loc = lambda p: [round(p[0] - x0, 2), round(p[1] - y0, 2)]
        gj = json.load(open(FLOORS / (ref + ".json"), encoding="utf-8"))
        floors = sum(1 for v in set(f["properties"].get("Planta") for f in gj["features"]) if v is not None and v >= 0)
        key = "%s|%s|%s" % (ref, r[c("x")], r[c("y")])
        out[key] = {"outline": [loc(p) for p in ext], "facade": [[loc(a), loc(b)] for a, b in street + opened],
                    "street": [[loc(a), loc(b)] for a, b in street], "m2": round(g.area), "use": u["use"], "floors": floors}
        st["ok"] += 1
        st["no street edge"] += not street
        st["under 40 m2"] += g.area < 40
    json.dump(out, open(ROOT / "app/data/unit_shells.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(skip, open(ROOT / "app/data/unit_skips.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))   # why no own unit
    print(dict(st))


if __name__ == "__main__":
    main()
