"""Nomad - the street-flat library: the real flats NOMAD can put along a shop's façade.

From 7_floor_plans/output/library/library.json (7_floor_plans/code/build_library.py): flats lit only from their front, entered from the
back, left or right, and through flats lit front and back entered from a side (the Eixample "pis passant"), that pass every check (7_floor_plans/code/library_fit.py: plan graph, doors widened to the legal width,
turning circles, room widths) and can be furnished as the law asks (7_floor_plans/code/furnish.py). Their own size is kept (W0, D0) to report how much each was stretched.
Out: 7_floor_plans/output/library/library_street.json (plan3.py, Grasshopper and the website all read this one file)
Run: .venv/Scripts/python 7_floor_plans/code/street_library.py
"""
import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import furnish as U  # noqa: E402
import library_fit as F  # noqa: E402


def main():
    lib = json.load(open(ROOT / "7_floor_plans/output/library/library.json"))                 # Swiss Dwellings
    rp = ROOT / "7_floor_plans/output/library/library_resplan.json"                        # ResPlan (7_floor_plans/code/build_resplan.py)
    if rp.exists():
        lib += json.load(open(rp))
    own = ROOT / "7_floor_plans/output/library/library_own.json"                          # your own plans (7_floor_plans/code/own_plans.py)
    if own.exists():
        lib += json.load(open(own))
    pl = ROOT / "7_floor_plans/output/library/library_placed.json"                        # NOMAD's room placer (7_floor_plans/code/placed_plans.py)
    if pl.exists() and "--no-placed" not in sys.argv:
        lib += json.load(open(pl, encoding="utf-8"))
    ai = ROOT / "7_floor_plans/output/library/library_ai.json"                            # NOMAD's plan AI (7_floor_plans/code/generate_plans.py)
    if ai.exists() and "--no-ai" not in sys.argv:
        lib += json.load(open(ai))
    out = []
    for f in lib:
        side = (f.get("entrance") or {}).get("side")
        one = f["lit"] == ["front"] and side in ("back", "left", "right", "front")   # lit from the street, door behind (front: own street door)
        through = sorted(f["lit"]) == ["back", "front"] and side in ("left", "right")  # street + block interior, door at the side
        if not (one or through):
            continue
        g = F.widen_doors(f)
        if all(c["ok"] for c in F.checks(g)) and U.passes(U.furnish(g)[1]):           # and it can be furnished (furnish.py)
            g = {k: g[k] for k in ("id", "bedrooms", "W", "D", "rooms", "doors", "windows", "entrance", "edges", "lit", "useful")}
            g["source"] = f.get("source", "Swiss Dwellings")
            g["W0"], g["D0"] = g["W"], g["D"]
            g["doors"] = [{"at": d["at"], "w": d["w"]} for d in g["doors"]]
            out.append(g)
    p = ROOT / "7_floor_plans/output/library/library_street.json"
    json.dump(out, open(p, "w"), separators=(",", ":"))
    by = {}
    for f in out:
        by[f["bedrooms"]] = by.get(f["bedrooms"], 0) + 1
    src = {}
    for f in out:
        src[f["source"]] = src.get(f["source"], 0) + 1
    print("street library: %d flats %s %s, %.1f MB" % (len(out), dict(sorted(by.items())), src, p.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
