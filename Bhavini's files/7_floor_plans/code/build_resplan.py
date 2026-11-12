"""Nomad - ResPlan's 17,000 residential plans (CC BY 4.0, github.com/m-agour/ResPlan) added to the plan library.

Each plan comes in pixels; it is scaled so its median inner door is 0,80 m (DOOR_M, an assumption). Rooms: living, bedrooms,
kitchen, bathrooms, "inner" (halls and corridors) -> NOMAD kinds; doors, windows and the front door as openings.
They are squared exactly as the Swiss flats (7_floor_plans/code/build_library.py: square_flat), so the same plan graph, checks
and stretch apply. ResPlan flats were not tested against NOMAD's rules beforehand: every one is checked when it is fitted.
Out: 7_floor_plans/output/library/library_resplan.json, 7_floor_plans/output/library/summary_resplan.json
Run: .venv/Scripts/python 7_floor_plans/code/build_resplan.py [limit]
"""
import json, math, pickle, sys, time
from collections import Counter
from pathlib import Path
from shapely import affinity

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import build_library as BL  # noqa: E402

ROOMS = {"living": "living", "bedroom": "bed", "kitchen": "kitchen", "bathroom": "bath", "inner": "hall"}
DOOR_M = 0.80       # assumption: ResPlan's net area does not match its drawn rooms (doors came out 0,6 m, bedrooms 8 m²),
                    # so each plan is scaled by its doors: the median inner door = 0,80 m (bedrooms then ~14 m², as real flats)


def parts(g):
    if g is None or g.is_empty:
        return []
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.area > 0]


def main(limit=None):
    t = time.time()
    plans = pickle.load(open(ROOT / "7_floor_plans/input/datasets/resplan/ResPlan.pkl", "rb"))
    if limit:
        plans = plans[:limit]
    out, skipped = [], Counter()
    for p in plans:
        rooms = [(ROOMS[k], g) for k in ROOMS for g in parts(p.get(k))]
        px = sum(g.area for _, g in rooms)
        if not rooms or not p.get("net_area") or px <= 0:
            skipped["no rooms"] += 1; continue
        dw = sorted(max(BL.H.width_of(d)[1], 1e-6) for d in parts(p.get("door")))
        if not dw:
            skipped["no doors"] += 1; continue
        s = DOOR_M / dw[len(dw) // 2]                         # metres per pixel: the median inner door is 0,80 m wide
        sc = lambda g: affinity.scale(g, s, s, origin=(0, 0))
        rooms = [(k, sc(g)) for k, g in rooms]
        try:
            sq = BL.square_flat(rooms, [sc(g) for g in parts(p.get("window"))], [sc(g) for g in parts(p.get("front_door"))],
                                [sc(g) for g in parts(p.get("door"))])
        except Exception:
            sq = None
        if not sq:
            skipped["not rectilinear"] += 1; continue
        beds = [r for r in sq["rooms"] if r["kind"] == "bed"]
        if beds:
            max(beds, key=lambda r: r["area"])["kind"] = "bed_main"
        sides = Counter()
        for w in sq["windows"]:
            sides[w["side"]] += w["w"]
        sq.update(id="R%d" % p["id"], source="ResPlan", bedrooms=len(beds), useful=round(sum(r["area"] for r in sq["rooms"]), 1),
                  ground=False, lit=sorted(k for k, v in sides.items() if k != "inside" and v >= 0.6))
        if sq["bedrooms"] <= 3:
            out.append(sq)
        else:
            skipped["4+ bedrooms"] += 1
    json.dump(out, open(ROOT / "7_floor_plans/output/library/library_resplan.json", "w"), separators=(",", ":"))
    s = {"plans_in": len(plans), "in_library": len(out), "skipped": dict(skipped),
         "by_bedrooms": dict(Counter(f["bedrooms"] for f in out)), "lit": dict(Counter("+".join(f["lit"]) for f in out).most_common(8)),
         "entrance": dict(Counter((f["entrance"] or {}).get("side") for f in out)), "minutes": round((time.time() - t) / 60, 1)}
    json.dump(s, open(ROOT / "7_floor_plans/output/library/summary_resplan.json", "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
