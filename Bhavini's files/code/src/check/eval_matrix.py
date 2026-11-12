"""Nomad - scores layouts on the 100-point NOMAD AI Floor Plan Evaluation Matrix (the team's PDF of 6 Nov 2026), independently of the engine.

Takes the same 40 shops as src/generate/eval_space.py and keeps each shop's layout with the most homes. Gates and points follow the PDF
table by table; a flat-level item only earns its points when every flat in the layout passes (the PDF's script is all-or-nothing).
Measured outside the engine with shapely. Limits: the kitchen route stops at the kitchen's threshold (no counter position in the data),
routes are straight lines from door to door, and there is no dining room in our data, so "dining" reads as the living room.
Out: results/eval/matrix.csv, results/eval/matrix.json.  Run: .venv/Scripts/python src/check/eval_matrix.py
"""
import csv, json, math, re, sys
from collections import deque
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "generate"), str(ROOT / "src" / "check")]
import eval_space as E

POINTS = {"1.1": 15, "1.2": 15, "1.3": 10, "1.4": 5, "1.5": 5, "2.1": 8, "2.2": 7, "2.3": 5, "2.4": 5, "3.1": 7, "3.2": 6, "3.3": 7, "3.4": 5}
GATES = ("1.1", "1.2", "1.3", "1.4")
PRIVATE = ("bed", "bed_main", "bath")
COMMON = ("kitchen", "living")


def poly(q):
    from shapely.geometry import Polygon
    return Polygon(q).buffer(0)


def graph(f):
    n = len(f["rooms"]); adj = [set() for _ in range(n)]
    for e in f.get("edges", []):
        if e[0] < n and e[1] < n:
            adj[e[0]].add(e[1]); adj[e[1]].add(e[0])
    return adj


def thoroughfare(f, adj):
    """A common room that can only be reached through a bedroom or bathroom."""
    start, rooms = f["entrance"]["room"], f["rooms"]
    seen, q = {start}, [start]
    while q:
        i = q.pop()
        for j in adj[i]:
            if j not in seen and rooms[j]["kind"] not in PRIVATE:
                seen.add(j); q.append(j)
    return any(r["kind"] in COMMON and i not in seen for i, r in enumerate(rooms))


def threshold(f, a, b):
    """Where you step from room a to room b: their door, else the nearest points of the two rooms."""
    import library_fit as F
    from shapely.ops import nearest_points
    A, B = f["rooms"][a], f["rooms"][b]
    ds = [p for p in F._doors_of(f, A) if p in F._doors_of(f, B)]
    if ds:
        return tuple(ds[0])
    p, q = nearest_points(poly(A["pts"]), poly(B["pts"]))
    return ((p.x + q.x) / 2.0, (p.y + q.y) / 2.0)


def walk(f, adj, goal):
    """Shortest door-to-door walk from the flat's door to the threshold of the nearest goal room, m (Dijkstra on rooms)."""
    import heapq
    start, at0 = f["entrance"]["room"], tuple(f["entrance"]["at"])
    if f["rooms"][start]["kind"] in goal:
        return 0.0
    best, h = {}, [(0.0, start, at0)]
    while h:
        d, i, at = heapq.heappop(h)
        if best.get(i, 1e9) <= d:
            continue
        best[i] = d
        for j in adj[i]:
            t = threshold(f, i, j)
            nd = d + math.hypot(t[0] - at[0], t[1] - at[1])
            if f["rooms"][j]["kind"] in goal:
                return nd
            heapq.heappush(h, (nd, j, t))
    return None


def far_door(f):
    """Flat door to its furthest inner door, m, in a straight line."""
    at = f["entrance"]["at"]
    return max([math.hypot(d["at"][0] - at[0], d["at"][1] - at[1]) for d in f.get("doors", [])] or [0.0])


def flat_items(f, u):
    import library_fit as F
    rooms, adj = f["rooms"], graph(f)
    c = {x["rule"]: x["ok"] for x in f.get("checks_lib", [])}
    start = f["entrance"]["room"]
    hall = rooms[start]["kind"] == "hall"
    area_foyer = rooms[start]["area"] if hall else 0.0
    halls = [r["clear"] for r in rooms if r["kind"] == "hall"]
    entry_clear = rooms[start]["clear"] if hall else 0.0
    other = [r["clear"] for i, r in enumerate(rooms) if r["kind"] == "hall" and i != start]
    sw = [(tuple(x["sweep"])) for x in f.get("swings", []) if x.get("sweep")]
    box = lambda s: poly([(s[0], s[1]), (s[2], s[1]), (s[2], s[3]), (s[0], s[3])])
    clash = sum(1 for i in range(len(sw)) for j in range(i + 1, len(sw)) if box(sw[i]).intersection(box(sw[j])).area > 0.02)
    furn = [poly([(x["rect"][0], x["rect"][1]), (x["rect"][2], x["rect"][1]), (x["rect"][2], x["rect"][3]), (x["rect"][0], x["rect"][3])]) for x in f.get("furniture", []) if x.get("rect")]
    hit = sum(1 for s in sw for g in furn if box(s).intersection(g).area > 0.02)
    lv = [i for i, r in enumerate(rooms) if r["kind"] == "living"]
    ki = [i for i, r in enumerate(rooms) if r["kind"] == "kitchen"]
    bd = [i for i, r in enumerate(rooms) if r["kind"] in ("bed", "bed_main")]
    ba = [i for i, r in enumerate(rooms) if r["kind"] == "bath"]
    dist = [min([abs(p[0] - q[0]) + abs(p[1] - q[1]) for j in ba for p in F._doors_of(f, rooms[i]) for q in F._doors_of(f, rooms[j])] or [0.0]) for i in bd]
    gro = F.walk(f, adj)
    noisy = any(F._shared_wall(rooms[i], rooms[j]) >= 0.5 for i in bd for j in lv)
    by_kitchen = any(F._shared_wall(rooms[i], rooms[j]) >= 0.5 for i in bd for j in ki)
    return {
        "source": f.get("source", ""), "type": u["type"], "foyer_is_hall": hall, "foyer_m2": round(area_foyer, 1), "sightline_ok": c.get("sightline", True),
        "thoroughfare": thoroughfare(f, adj), "entry_clear": entry_clear, "second_clear": min(other) if other else None,
        "door_circle_ok": c.get("door_circle", True) and c.get("turning", True), "swing_clash": clash, "swing_furniture": hit,
        "grocery_m": None if gro is None else round(gro, 1), "bed_living_wall": noisy, "bed_kitchen_wall": by_kitchen,
        "kitchen_living": bool(ki and lv and any(adj[i] & set(lv) for i in ki)), "bed_bath_max": round(max(dist or [0.0]), 1),
        "openings_ok": c.get("openings", True), "far_door": round(far_door(f), 1), "comfort": F.comfort(f)}


def score(p, s, fl):
    """The layout on the PDF's matrix."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    units = [u for u in p["units"] if u.get("ok")]
    o = poly(s["outline"])
    fronts = [LineString(q) for q in (s.get("street") or []) + (s.get("facade") or [])]
    lit = unary_union(fronts)
    R = [(i, r["kind"], poly(r["pts"])) for i, u in enumerate(units) for r in u["rooms"]]
    worst = max([x[2].centroid.distance(lit) for x in R if x[1] in ("living", "bed", "bed_main")] or [0.0])
    over = [R[i][2].intersection(R[j][2]).area for i in range(len(R)) for j in range(i + 1, len(R))]
    over_max, over_sum = max(over or [0.0]), sum(over or [0.0])
    outside = sum(x[2].difference(o).area for x in R)
    evac = [float(m.group(1)) for u in units for c in u.get("checks", []) if c.get("rule") == "evac" for m in [re.search(r"([\d.]+) m from", c.get("text", ""))] if m]
    egress = 0.0
    for u, x in zip(units, fl):
        e = [float(m.group(1)) for c in u.get("checks", []) if c.get("rule") == "evac" for m in [re.search(r"([\d.]+) m from", c.get("text", ""))] if m]
        egress = max(egress, e[0] if e else x["far_door"])       # the engine's route already runs to the furthest room door
    deep = o.difference(lit.buffer(E.REACH))
    named = [poly(m["pts"]) for m in p.get("shared_spaces", [])]
    used = unary_union([x[2] for x in R] + named + [poly(c["pts"]) for c in p.get("corridors", [])] + [poly(c if isinstance(c, list) else c["pts"]) for c in p.get("cores", []) + p.get("patios", [])])
    deep_pct = 100.0 if deep.area < 0.5 else 100.0 * deep.intersection(used).area / deep.area
    # named rooms somebody can get to: touching a shared corridor, or another named room that does
    C = [poly(c["pts"]) for c in p.get("corridors", [])]
    street_line = unary_union([LineString(q) for q in (s.get("street") or s.get("facade") or [])])
    reach, q = set(), deque(i for i, n in enumerate(named) if n.distance(street_line) <= 0.3 or any(n.distance(c) <= 0.3 for c in C))
    while q:
        i = q.popleft()
        if i not in reach:
            reach.add(i); q.extend(j for j, n in enumerate(named) if j not in reach and n.distance(named[i]) <= 0.3)
    na = sum(n.area for n in named)
    access = 100.0 if na < 0.5 else 100.0 * sum(named[i].area for i in reach) / na
    ok = {"1.1": worst <= 9.0, "1.2": over_max <= 0.001, "1.3": all(x["openings_ok"] for x in fl), "1.4": True,
          "2.1": all(x["foyer_is_hall"] and x["foyer_m2"] >= 3.0 and x["sightline_ok"] for x in fl), "2.2": not any(x["thoroughfare"] for x in fl),
          "2.3": all(x["entry_clear"] >= 1.10 and (x["second_clear"] is None or x["second_clear"] >= 0.90) for x in fl),
          "2.4": all(x["door_circle_ok"] and not x["swing_clash"] and not x["swing_furniture"] for x in fl),
          "3.1": all(x["grocery_m"] is not None and x["grocery_m"] <= 6.0 for x in fl), "3.2": not any(x["bed_living_wall"] for x in fl),
          "3.3": deep_pct >= 99.5, "3.4": all(x["kitchen_living"] and x["bed_bath_max"] <= 5.0 for x in fl)}
    pts = {k: POINTS[k] if ok[k] else 0 for k in ok}
    if ok["3.2"] and any(x["bed_kitchen_wall"] for x in fl):
        pts["3.2"] = POINTS["3.2"] - 4                              # the PDF's 4-point penalty for an unbuffered kitchen wall
    pts["1.5"] = max(0.0, 5.0 - max(0.0, egress - 25.0))
    gate = all(ok[k] for k in GATES)
    raw = sum(pts.values())
    total = raw if gate else 0.0
    tier = "Rejected" if total < 60 else "Bronze" if total < 75 else "Silver" if total < 90 else "Gold"
    return dict(homes=len(units), gate=gate, raw=round(raw, 1), total=round(total, 1), tier=tier, ok=ok, pts=pts, room_centroid_max=round(worst, 1), overlap_sum=round(over_sum, 3),
                overlap_max=round(over_max, 3), outside_m2=round(outside, 2), egress_max=round(egress, 1), deep_m2=round(deep.area, 1), deep_pct=round(deep_pct, 1), named_access_pct=round(access, 1),
                named_m2=round(na, 1), floor=p.get("floor"), comfort=p.get("comfort"))


def run(a):
    ref, s, lit = a
    import plan3
    keep = plan3._unit
    def spy(fr, u0, f, t, height, kind, back, alts=None):
        u = keep(fr, u0, f, t, height, kind, back, alts)
        if u:
            u["_f"] = f
        return u
    plan3._unit = spy
    try:
        _, its, _ = plan3.iterations(s["outline"], s["facade"], s["height"], E.MIX, street=s.get("street"), existing=s.get("existing"), lit_depth=lit or 5.5, lit_source="bars" if lit else None)
    finally:
        plan3._unit = keep
    best = max(its, key=lambda it: (len([u for u in it[1]["units"] if u.get("ok")]), sum(u.get("area_m2", 0) for u in it[1]["units"] if u.get("ok"))))
    p = best[1]
    units = [u for u in p["units"] if u.get("ok")]
    if not units:
        return dict(ref=ref, strategy="none", homes=0, flats=[], gate=False, total=0.0, raw=0.0, tier="No layout", floor_m2=round(poly(s["outline"]).area))
    fl = [flat_items(u["_f"], u) for u in units if u.get("_f")]
    if len(fl) != len(units):
        return dict(ref=ref, strategy=best[0], homes=len(units), flats=[], gate=False, total=0.0, raw=0.0, tier="Not read", floor_m2=round(poly(s["outline"]).area))
    r = score(p, s, fl)
    r.update(ref=ref, strategy=best[0], flats=fl, floor_m2=round(poly(s["outline"]).area))
    return r


if __name__ == "__main__":
    with Pool(6) as P:
        R = P.map(run, E.shops(), 1)
    out = ROOT / "results" / "eval"; out.mkdir(exist_ok=True)
    json.dump(R, open(out / "matrix.json", "w", encoding="utf-8"), indent=0)
    with open(out / "matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["ref", "strategy", "homes", "gate", "raw", "total", "tier"] + list(POINTS))
        for r in R:
            w.writerow([r["ref"], r["strategy"], r["homes"], r["gate"], r["raw"], r["total"], r["tier"]] + [r.get("pts", {}).get(k, "") for k in POINTS])
    L = [r for r in R if r["homes"] and "pts" in r]
    print("layouts", len(L), "of", len(R), "tiers", {t: sum(1 for r in R if r["tier"] == t) for t in ("Gold", "Silver", "Bronze", "Rejected", "No layout", "Not read")})
    print("mean total", round(sum(r["total"] for r in L) / max(len(L), 1), 1), "mean raw (gates ignored)", round(sum(r["raw"] for r in L) / max(len(L), 1), 1))
    for k in POINTS:
        n = sum(1 for r in L if (r["pts"].get(k, 0) >= POINTS[k]))
        m = sum(r["pts"].get(k, 0) for r in L) / max(len(L), 1)
        print(k, "full marks", n, "of", len(L), "mean", round(m, 1), "/", POINTS[k])
    F = [x for r in L for x in r["flats"]]
    n = len(F)
    print("flats", n, "| foyer hall", sum(x["foyer_is_hall"] for x in F), "foyer>=3", sum(x["foyer_m2"] >= 3 for x in F), "sight", sum(x["sightline_ok"] for x in F),
          "| clear>=1.10", sum(x["entry_clear"] >= 1.10 for x in F), "| circle", sum(x["door_circle_ok"] for x in F), "swing clash flats", sum(x["swing_clash"] > 0 for x in F), "swing/furn flats", sum(x["swing_furniture"] > 0 for x in F),
          "| grocery<=6", sum((x["grocery_m"] or 99) <= 6 for x in F), "max", max((x["grocery_m"] or 0) for x in F), "| bed-kitchen wall", sum(x["bed_kitchen_wall"] for x in F),
          "| bed-bath<=5", sum(x["bed_bath_max"] <= 5 for x in F), "| comfort100", sum(x["comfort"] == 100 for x in F))
    print("overlap sum", round(sum(r["overlap_sum"] for r in L), 2), "layouts with overlap>0.001", sum(r["overlap_max"] > 0.001 for r in L), "outside m2", round(sum(r["outside_m2"] for r in L), 2),
          "centroid max", max(r["room_centroid_max"] for r in L), "egress max", max(r["egress_max"] for r in L))
    print("deep m2", round(sum(r["deep_m2"] for r in L)), "deep % mean", round(sum(r["deep_pct"] for r in L) / len(L), 1), "named m2", round(sum(r["named_m2"] for r in L)), "named reachable %", round(sum(r["named_access_pct"] * r["named_m2"] for r in L) / max(sum(r["named_m2"] for r in L), 1), 1))
