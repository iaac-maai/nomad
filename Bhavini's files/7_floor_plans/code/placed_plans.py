"""NOMAD's room placer: narrow street flats drawn from rules, for the street fronts where no real plan fits.
Living room and bedrooms stand on the facade (Decret 141/2012 Annex 1 3.9.1: they need natural light); bath and hall go to
the dark back (3.9.1 does not ask them for light); the kitchen is open to the living room, as in the real plans. Which rooms
connect, and how, comes from the real plans: connections() counts it in the plan library -> 7_floor_plans/output/library/connections.json.
Every plan must then pass the same checks and furniture as a real plan. Out: 7_floor_plans/output/library/library_placed.json, merged by
7_floor_plans/code/street_library.py as source "NOMAD placed"."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import library_fit as F   # noqa: E402
import furnish as U       # noqa: E402

def connections():
    """How rooms connect in the real plans: share of plans where a pair is joined, by a door or open."""
    n = 0; pairs = collections.Counter()
    for name in ("library.json", "library_resplan.json"):
        p = ROOT / "7_floor_plans/output/library" / name
        if not p.exists():
            continue
        for f in json.load(open(p, encoding="utf-8")):
            n += 1; seen = set()
            for e in f.get("edges", []):
                if e[0] < len(f["rooms"]) and e[1] < len(f["rooms"]):
                    a, b = sorted((f["rooms"][e[0]]["kind"], f["rooms"][e[1]]["kind"]))
                    seen.add((a, b, "door" if e[2] > 0 else "open"))
            pairs.update(seen)
    out = {"plans": n, "pairs": sorted(([a, b, k, round(c / float(n), 3)] for (a, b, k), c in pairs.items()), key=lambda r: -r[3])}
    json.dump(out, open(ROOT / "7_floor_plans/output/library/connections.json", "w", encoding="utf-8"), indent=0)
    return out


flat = F.place_flat


DOOR_GRID = {0: (5.0, 5.5, 6.0, 7.0), 1: (7.25, 7.75, 8.25, 9.0), 2: (10.0, 10.5, 11.0, 12.0), 3: (12.75, 13.25, 14.0)}
GRID = {0: (5.0, 5.5, 6.0, 6.5), 1: (7.25, 7.75, 8.25, 8.75), 2: (10.0, 10.5, 11.0, 11.5), 3: (12.75, 13.25, 13.75)}


def build():
    keep, fails, n = [], collections.Counter(), 0
    for beds, ws in GRID.items():
        for W in ws:
            for D in (6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0):
                for Yb in (2.8, 3.2, 3.6, 4.0, 4.4, 4.8, 5.2):
                    if W * D * 0.9 < 40 or W < D / 9.0 * 0:
                        continue
                    f = flat(beds, W, D, Yb, "placed-%d-%g-%g-%g" % (beds, W, D, Yb))
                    if f is None:
                        continue
                    n += 1
                    if f["useful"] < 40:
                        fails["under 40 m2"] += 1; continue
                    bad = [c["rule"] for c in F.checks(f) if not c["ok"]]
                    if not bad:
                        bad = [c["rule"] for c in U.furnish(f)[1] if not c["ok"]]
                    if bad:
                        fails.update(bad); continue
                    keep.append(f)
    for beds, ws in DOOR_GRID.items():                    # own street door: shallower and wider flats, no shared hall behind them
        for W in ws:
            for D in (5.75, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0):
                for Yb in (2.8, 3.2, 3.6, 4.2):
                    f = flat(beds, W, D, Yb, "placed-door-%d-%g-%g-%g" % (beds, W, D, Yb), street=True)
                    if f is None:
                        continue
                    n += 1
                    if f["useful"] < 40:
                        fails["under 40 m2"] += 1; continue
                    bad = [c["rule"] for c in F.checks(f) if not c["ok"]]
                    if not bad:
                        bad = [c["rule"] for c in U.furnish(f)[1] if not c["ok"]]
                    if bad:
                        fails.update(bad); continue
                    keep.append(f)
    json.dump(keep, open(ROOT / "7_floor_plans/output/library/library_placed.json", "w", encoding="utf-8"), separators=(",", ":"))
    return n, keep, fails


if __name__ == "__main__":
    c = connections()
    print("connections from", c["plans"], "plans:", [(a, b, k, s) for a, b, k, s in c["pairs"][:10]])
    n, keep, fails = build()
    print(n, "drawn,", len(keep), "pass every check;", collections.Counter(f["bedrooms"] for f in keep), "min W", {b: min([f["W"] for f in keep if f["bedrooms"] == b] or [0]) for b in GRID})
    print("failures:", fails.most_common(10))
