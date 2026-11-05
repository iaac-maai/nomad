"""NOMAD's room placer: narrow street flats drawn from rules, for the street fronts where no real plan fits.
Living room and bedrooms stand on the facade (Decret 141/2012 Annex 1 3.9.1: they need natural light); bath and hall go to
the dark back (3.9.1 does not ask them for light); the kitchen is open to the living room, as in the real plans. Which rooms
connect, and how, comes from the real plans: connections() counts it in the plan library -> results/library/connections.json.
Every plan must then pass the same checks and furniture as a real plan. Out: results/library/library_placed.json, merged by
src/library/street_library.py as source "NOMAD placed"."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "generate"))
import library_fit as F   # noqa: E402
import furnish as U       # noqa: E402

T = 0.10            # partition, m (the library's gap between rooms)
HALL = 1.25         # circle of 1,20 m in front of the doors (3.4.1.d)
BATH = 1.45         # practicable bath, wide enough for the 1,20 m circle and its fittings
KITCHEN = 3.0       # kitchen depth at most, HALL_D = hall depth at most, on deep flats
HALL_D = 2.6
LIVING = 2.90       # 2,80 m circle (3.7.2) + a little
BED = 2.65          # a 2,60 m square for the main bedroom (3.8)


def connections():
    """How rooms connect in the real plans: share of plans where a pair is joined, by a door or open."""
    n = 0; pairs = collections.Counter()
    for name in ("library.json", "library_resplan.json"):
        p = ROOT / "results" / "library" / name
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
    json.dump(out, open(ROOT / "results" / "library" / "connections.json", "w", encoding="utf-8"), indent=0)
    return out


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def flat(beds, W, D, Yb, ident, street=False):
    """W x D, the facade at y = 0, the entrance at the back (street: from the street, into the living room). Yb = depth of the bedrooms."""
    rooms, doors, edges, wins = [], [], [], []
    def add(kind, pts):
        rooms.append({"kind": kind, "pts": [[round(x, 3), round(y, 3)] for x, y in pts]}); return len(rooms) - 1
    def door(i, j, x, y, w=0.8):
        doors.append({"at": [round(x, 3), round(y, 3)], "w": w}); edges.append([i, j, w])
    if beds == 0:                                         # studio: one room on the facade, kitchen + hall + bath behind
        kw = W - HALL - BATH - 2 * T
        if kw < 1.6:
            return None
        lv = add("living", rect(0, 0, W, Yb))
        ki = add("kitchen", rect(0, Yb + T, kw, D)); edges.append([lv, ki, 0.0])
        ha = add("hall", rect(kw + T, Yb + T, kw + T + HALL, D)); door(ha, lv, kw + T + HALL / 2, Yb + T / 2)
        ba = add("bath", rect(kw + 2 * T + HALL, Yb + T, W, D)); door(ha, ba, kw + 1.5 * T + HALL, Yb + 0.75)
        wins.append({"at": [W / 2, 0.0], "w": round(W * 0.6, 2), "side": "front"})
        ent = {"at": [round(kw + T + HALL / 2, 3), D], "w": 0.9, "side": "back", "room": ha}
    else:
        bw = (W - LIVING - beds * T) / float(beds)            # bedrooms take what the living room leaves
        if bw < BED - 1e-6:
            return None
        a = LIVING
        corr = beds > 1                                       # more than one bedroom: a corridor behind them
        Yh = Yb + T
        Yl = Yh + (HALL if corr else 1.0)                     # the living room reaches the hall
        if D - Yl - T < 1.7:
            return None
        lv = add("living", rect(0, 0, a, Yl))
        Yk = min(D, Yl + T + KITCHEN) if street else D         # no oversized kitchen: what is left behind it is storage
        ki = add("kitchen", rect(0, Yl + T, a, Yk)); edges.append([lv, ki, 0.0])
        if D - Yk - T >= 1.0:
            sk = add("storage", rect(0, Yk + T, a, D)); door(ki, sk, a / 2, Yk + T / 2, 0.7)
        bs = []
        for k in range(beds):
            x0 = a + T + k * (bw + T)
            bs.append((add("bed_main" if k == 0 else "bed", rect(x0, 0, x0 + bw, Yb)), x0))
            wins.append({"at": [round(x0 + bw / 2, 3), 0.0], "w": round(bw * 0.6, 2), "side": "front"})
        wins.append({"at": [round(a / 2, 3), 0.0], "w": round(a * 0.6, 2), "side": "front"})
        bx = W - BATH if W - BATH - (a + T) >= HALL + T else None
        if bx is None:
            return None
        Ye = min(D, Yh + HALL_D) if street else D             # no long hall either
        if corr and street:
            ha = add("hall", rect(a + T, Yh, W, Yh + HALL))
            Yba = min(D, Yh + HALL + T + 2.6)
            ba = add("bath", rect(bx, Yh + HALL + T, W, Yba))
            door(ha, ba, bx + BATH / 2, Yh + HALL + T / 2)
            if D - Yh - HALL - T >= 1.0:
                st = add("storage", rect(a + T, Yh + HALL + T, bx - T, D)); door(ha, st, a + 0.8, Yh + HALL + T / 2, 0.7)
        elif corr:
            ha = add("hall", [[a + T, Yh], [W, Yh], [W, Yh + HALL], [bx - T, Yh + HALL], [bx - T, D], [a + T, D], [a + T, Yh + HALL]])
            ba = add("bath", rect(bx, Yh + HALL + T, W, D))
            door(ha, ba, bx - T / 2, D - 0.9)
        else:
            ha = add("hall", rect(a + T, Yh, bx - T, Ye))
            ba = add("bath", rect(bx, Yh, W, Ye))
            door(ha, ba, bx - T / 2, Yh + 0.75)
            if D - Ye - T >= 1.0:
                st = add("storage", rect(a + T, Ye + T, W, D)); door(ha, st, a + T + HALL / 2, Ye + T / 2, 0.7)
        door(ha, lv, a + T / 2, Yh + 0.62)
        for i, x0 in bs:
            door(ha, i, x0 + min(0.6, bw / 2), Yb + T / 2)
        ent = {"at": [round((a + T + bx - T) / 2, 3), D], "w": 0.9, "side": "back", "room": ha}
    if street:
        ent = {"at": [0.65, 0.0], "w": 0.9, "side": "front", "room": 0}
    for r in rooms:
        r["area"] = round(F.poly_area(r["pts"]), 2); r["clear"] = round(F.clear_width(r["pts"]), 2)
    return {"id": ident, "bedrooms": beds, "W": W, "D": D, "rooms": rooms, "doors": doors, "windows": wins, "entrance": ent, "edges": edges,
            "lit": ["front"], "useful": round(sum(r["area"] for r in rooms), 1), "source": "NOMAD placed", "W0": W, "D0": D}


DOOR_GRID = {0: (5.0, 5.5, 6.0, 7.0, 8.0), 1: (6.0, 6.5, 7.0, 8.0, 9.0), 2: (8.5, 9.0, 10.0, 11.0)}
GRID = {0: (4.6, 5.0, 5.5), 1: (5.75, 6.0, 6.5, 7.0), 2: (8.5, 9.0, 9.5, 10.0), 3: (11.25, 11.75, 12.25)}


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
    json.dump(keep, open(ROOT / "results" / "library" / "library_placed.json", "w", encoding="utf-8"), separators=(",", ":"))
    return n, keep, fails


if __name__ == "__main__":
    c = connections()
    print("connections from", c["plans"], "plans:", [(a, b, k, s) for a, b, k, s in c["pairs"][:10]])
    n, keep, fails = build()
    print(n, "drawn,", len(keep), "pass every check;", collections.Counter(f["bedrooms"] for f in keep), "min W", {b: min([f["W"] for f in keep if f["bedrooms"] == b] or [0]) for b in GRID})
    print("failures:", fails.most_common(10))
