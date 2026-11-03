# -*- coding: utf-8 -*-
"""Nomad - fill a flat with a real plan: match, stretch, check, score (after Finch's adaptive plan library).

The library (src/library/build_library.py) holds real flats that pass every NOMAD rule, squared: rooms as rectilinear
polygons, windows on the front (y = 0), the door graph and the entrance. For a flat space W wide (along its façade) and
D deep:
  match    same number of bedrooms, windows only on the sides this space has, the entrance on the side its hall is
  stretch  every wall line moves along x and along y (a 1D least-change problem per axis, as Finch's Cassowary solver):
           wall thicknesses are locked, bathrooms and kitchens are stiff, living rooms and bedrooms take the change,
           and no room may become narrower than the law allows
  check    the plan graph (every room reached from the entrance hall, no bedroom only through another bedroom, a
           bathroom reached without crossing a bedroom), doors and turning circles (Decret 141/2012 Annex 1 3.4), room
           widths (3.4, 3.7.2), and the habitability targets learned from 13,444 real flats (lab book E24)
  score    100 minus how much the plan had to stretch and how far it sits from the real-flat targets; shown from 75
Plain Python (Grasshopper IronPython 2.7 and the browser): no f-strings, no shapely.
"""
import math

CITE = {
    "door_entry": "Decret 141/2012 Annex 1 3.4.1.c (entrance door and doors of practicable spaces >= 0,80 m)",
    "door_inner": "Decret 141/2012 Annex 1 3.4.2 (other inner doors >= 0,70 m)",
    "hall_width": "Decret 141/2012 Annex 1 3.4.1.d (circulation to practicable spaces >= 1 m, 1,20 m circle at their doors)",
    "turning": "Decret 141/2012 Annex 1 3.4.1.e (1,20 m circle inside each practicable space)",
    "living_circle": "Decret 141/2012 Annex 1 3.7.2 (living / dining room: 2,80 m circle)",
    "kitchen_width": "Decret 141/2012 Annex 1 3.7.3 (1,00 m free between the worktop and the rest)",
    "graph": "NOMAD habitability (lab book E24: real flats reach every room from the hall)",
    "facade_room": "Decret 141/2012 Annex 1 3.6.1 and 3.9 (living room and bedrooms lit from the façade)",
}
# smallest clear width a room may be stretched or squeezed to (the law; kitchen: 0,60 m worktop + 1,00 m free)
MIN_CLEAR = {"living": 2.80, "bed_main": 2.00, "bed": 2.00, "kitchen": 1.60, "bath": 1.20, "hall": 1.00, "storage": 0.30}
# how much each room resists stretching (Finch: locked / stretchable walls); walls between rooms are locked
STIFF = {"living": 1.0, "bed_main": 1.5, "bed": 1.5, "hall": 3.0, "kitchen": 4.0, "bath": 6.0, "storage": 2.0}
# real-flat targets (median clear width, 10th percentile) from lab book E24, for the habitability part of the score
REAL_CLEAR = {"living": (4.0, 3.5), "bed_main": (3.2, 2.5), "bed": (3.2, 2.5), "kitchen": (2.3, 1.8), "bath": (1.6, 1.1), "hall": (1.75, 1.2)}
PRACTICABLE = ("living", "kitchen", "bed_main")
WALL_GAP = 0.35
MAX_STRETCH = (0.80, 1.30)          # a plan is only stretched between 80 % and 130 % of its own size on each axis
SHOW = 75.0
GEN_STRETCH = (0.65, 1.60)          # a generated plan: a real plan's room graph re-proportioned further, only when no real plan fits
SHOW_GEN = 55.0
MIN_COVER = 0.82                    # rooms cover at least 82 % of the flat's rectangle (the rest is walls; no dead corners)


# ---------- small geometry (rectilinear polygons) ----------
def poly_area(pts):
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def inside(x, y, pts):
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def clear_width(pts, holes=()):
    """Clear width of a rectilinear room: the largest square that fits, from the biggest full rectangle of its grid.
    holes: rectangles (x0, y0, x1, y1) that do not count (the sweep of the doors)."""
    xs = sorted(set([p[0] for p in pts] + [h[0] for h in holes] + [h[2] for h in holes]))
    ys = sorted(set([p[1] for p in pts] + [h[1] for h in holes] + [h[3] for h in holes]))
    free = lambda x, y: inside(x, y, pts) and not any(h[0] < x < h[2] and h[1] < y < h[3] for h in holes)
    full = [[free((xs[i] + xs[i + 1]) / 2.0, (ys[j] + ys[j + 1]) / 2.0) for j in range(len(ys) - 1)] for i in range(len(xs) - 1)]
    best, nx, ny = 0.0, len(xs) - 1, len(ys) - 1
    top = [[-1] * ny for _ in range(nx)]           # top[i][j]: last row of the free run going up from cell (i, j)
    for i in range(nx):
        for j in range(ny - 1, -1, -1):
            if full[i][j]:
                top[i][j] = top[i][j + 1] if (j + 1 < ny and full[i][j + 1]) else j
    for i0 in range(nx):
        for j0 in range(ny):
            if not full[i0][j0]:
                continue
            t = ny
            for i1 in range(i0, nx):               # widen to the right; the free height can only shrink
                if not full[i1][j0]:
                    break
                t = min(t, top[i1][j0])
                w, h = xs[i1 + 1] - xs[i0], ys[t + 1] - ys[j0]
                best = max(best, min(w, h))
                if w >= h:
                    break
    return best


# ---------- the stretch solver ----------
def stretch_axis(lines, spans, total):
    """lines: sorted wall-line coordinates; spans: [(i0, i1, stiffness, min_len)] = a room covering intervals i0..i1-1.
    Returns new line coordinates (first 0, last = total) that change each interval as little as possible, weighted by
    stiffness; intervals no room covers (walls) are locked; each room keeps its minimum length. None if impossible."""
    n = len(lines) - 1
    L = [lines[i + 1] - lines[i] for i in range(n)]
    w = [0.0] * n                                  # 0 = locked (a wall)
    for i0, i1, k, _ in spans:
        for i in range(i0, i1):
            w[i] = max(w[i], 1.0 / k)              # the softest room over an interval sets how much it may move
    free = [i for i in range(n) if w[i] > 0 and L[i] > 1e-6]
    if not free:
        return None
    x = list(L)
    for _ in range(60):
        gap = total - sum(x)                       # 1. hit the total, moving free intervals by their softness
        if abs(gap) > 1e-4:
            ws = sum(w[i] * L[i] for i in free)
            for i in free:
                x[i] = max(0.05, x[i] + gap * w[i] * L[i] / ws)
        bad = False
        for i0, i1, k, m in spans:                 # 2. no room under its minimum
            s = sum(x[i] for i in range(i0, i1))
            if s < m - 1e-4:
                bad = True
                own = [i for i in range(i0, i1) if w[i] > 0]
                if not own:
                    return None
                d = (m - s) / len(own)
                for i in own:
                    x[i] += d
        if not bad and abs(total - sum(x)) <= 1e-3:
            break
    if abs(total - sum(x)) > 0.02 or any(sum(x[i] for i in range(i0, i1)) < m - 0.02 for i0, i1, _, m in spans):
        return None
    out = [0.0]
    for v in x:
        out.append(out[-1] + v)
    return out


def _axis(flat, k):
    lines = sorted(set(round(p[k], 2) for r in flat["rooms"] for p in r["pts"]))
    spans = []
    for r in flat["rooms"]:
        a = lines.index(round(min(p[k] for p in r["pts"]), 2))
        b = lines.index(round(max(p[k] for p in r["pts"]), 2))
        if b > a:
            spans.append((a, b, STIFF.get(r["kind"], 2.0), min(MIN_CLEAR.get(r["kind"], 0.3), lines[b] - lines[a])
                          if r["kind"] in ("storage",) else MIN_CLEAR.get(r["kind"], 0.3)))
    return lines, spans


def _mapper(old, new):
    def f(v):
        if v <= old[0]:
            return new[0] + (v - old[0])
        for i in range(len(old) - 1):
            if v <= old[i + 1] + 1e-9:
                t = (v - old[i]) / (old[i + 1] - old[i]) if old[i + 1] > old[i] else 0.0
                return new[i] + t * (new[i + 1] - new[i])
        return new[-1] + (v - old[-1])
    return f


def mirror(flat):
    W = flat["W"]
    m = dict(flat)
    m["rooms"] = [dict(r, pts=[[round(W - p[0], 2), p[1]] for p in r["pts"]][::-1]) for r in flat["rooms"]]
    m["doors"] = [dict(d, at=[round(W - d["at"][0], 2), d["at"][1]]) for d in flat.get("doors", [])]
    m["windows"] = [dict(d, at=[round(W - d["at"][0], 2), d["at"][1]]) for d in flat.get("windows", [])]
    if flat.get("entrance"):
        e = dict(flat["entrance"])
        e["at"] = [round(W - e["at"][0], 2), e["at"][1]]
        e["side"] = {"left": "right", "right": "left"}.get(e["side"], e["side"])
        m["entrance"] = e
    m["mirrored"] = not flat.get("mirrored", False)
    return m


def stretch(flat, W, D, lim=MAX_STRETCH):
    """The flat stretched to W x D, or None. Rooms keep their kind; doors and the entrance move with their walls."""
    sx, sy = W / flat["W"], D / flat["D"]
    if not (lim[0] <= sx <= lim[1] and lim[0] <= sy <= lim[1]):
        return None
    lx, spx = _axis(flat, 0)
    ly, spy = _axis(flat, 1)
    nx, ny = stretch_axis(lx, spx, W), stretch_axis(ly, spy, D)
    if nx is None or ny is None:
        return None
    fx, fy = _mapper(lx, nx), _mapper(ly, ny)
    rooms = []
    for r in flat["rooms"]:
        pts = [[round(fx(p[0]), 2), round(fy(p[1]), 2)] for p in r["pts"]]
        rooms.append({"kind": r["kind"], "pts": pts, "area": round(poly_area(pts), 2), "clear": round(clear_width(pts), 2)})
    move = lambda d: dict(d, at=[round(fx(d["at"][0]), 2), round(fy(d["at"][1]), 2)])
    # how much each room had to change (Finch's "adaptivity"): mean relative change of its two sides
    change = []
    for r0, r1 in zip(flat["rooms"], rooms):
        for k in (0, 1):
            a0 = max(p[k] for p in r0["pts"]) - min(p[k] for p in r0["pts"])
            a1 = max(p[k] for p in r1["pts"]) - min(p[k] for p in r1["pts"])
            if a0 > 0.3:
                change.append(abs(a1 / a0 - 1.0))
    out = dict(flat, W=round(W, 2), D=round(D, 2), rooms=rooms, doors=[move(d) for d in flat.get("doors", [])],
               windows=[move(d) for d in flat.get("windows", [])], adaptivity=round(sum(change) / max(len(change), 1), 3))
    if flat.get("entrance"):
        out["entrance"] = move(flat["entrance"])
    return out


# ---------- the plan graph and its checks ----------
def widen_doors(f):
    """Doors narrower than the law are widened (a door is a small change; Finch's agent does the same in bulk): 0,80 m into
    the practicable spaces and at the entrance (3.4.1.c), 0,70 m elsewhere (3.4.2), when the room is wide enough."""
    rooms, n = f["rooms"], len(f["rooms"])
    baths = [i for i in range(n) if rooms[i]["kind"] == "bath"]
    big = max(baths, key=lambda i: rooms[i]["area"]) if baths else None
    prac = set(i for i in range(n) if rooms[i]["kind"] in PRACTICABLE) | (set([big]) if big is not None else set())
    edges, changed = [], 0
    for e in f.get("edges", []):
        i, j, w = e[0], e[1], e[2]
        need = 0.80 if (i in prac or j in prac) else 0.70
        if 0 < w < need and min(rooms[i]["clear"], rooms[j]["clear"]) >= need + 0.10:
            w, changed = need, changed + 1
        edges.append([i, j, w])
    out = dict(f, edges=edges)
    if f.get("entrance") and f["entrance"]["w"] < 0.80:
        out["entrance"] = dict(f["entrance"], w=0.80)
        changed += 1
    out["doors_widened"] = changed
    return out


def graph_checks(f):
    rooms, n = f["rooms"], len(f["rooms"])
    adj = dict((i, set()) for i in range(n))
    door_w = {}
    for e in f.get("edges", []):
        i, j, w = e[0], e[1], e[2]
        if i < n and j < n:
            adj[i].add(j); adj[j].add(i)
            if w > 0:
                door_w[(min(i, j), max(i, j))] = max(w, door_w.get((min(i, j), max(i, j)), 0))
    start = (f.get("entrance") or {}).get("room")
    out = []
    if start is None or start >= n:
        out.append(("graph", False, "no entrance room", "graph"))
        return out, {}
    parent, q = {start: None}, [start]
    while q:                                      # reach rooms through the hall first, as people walk
        i = q.pop(0)
        for j in sorted(adj[i], key=lambda j: rooms[j]["kind"] != "hall"):
            if j not in parent:
                parent[j] = i
                q.append(j)
    lost = [rooms[i]["kind"] for i in range(n) if i not in parent]
    out.append(("graph", not lost, "every room reached from the entrance" if not lost else "not reached: " + ", ".join(lost), "graph"))
    via_bed = [i for i in parent if rooms[i]["kind"] in ("bed", "bed_main") and parent[i] is not None
               and rooms[parent[i]]["kind"] in ("bed", "bed_main")]
    out.append(("graph", not via_bed, "no bedroom only through another bedroom" if not via_bed else "a bedroom only through another", "graph"))
    baths = [i for i in range(n) if rooms[i]["kind"] == "bath"]
    free_bath = [i for i in baths if i in parent and (parent[i] is None or rooms[parent[i]]["kind"] not in ("bed", "bed_main"))]
    out.append(("graph", bool(free_bath) or not baths, "a bathroom reached without crossing a bedroom" if free_bath else
                "every bathroom only through a bedroom", "graph"))
    ent_w = (f.get("entrance") or {}).get("w", 0)
    out.append(("door_entry", ent_w >= 0.80 - 1e-6, "entrance door %.2f m" % ent_w, "door_entry"))
    big_bath = max(baths, key=lambda i: rooms[i]["area"]) if baths else None
    practicable = set(i for i in range(n) if rooms[i]["kind"] in PRACTICABLE) | (set([big_bath]) if big_bath is not None else set())
    for i in sorted(practicable):
        ws = [door_w[k] for k in door_w if i in k]
        if ws:
            out.append(("door_entry", max(ws) >= 0.80 - 1e-6, "%s door %.2f m" % (rooms[i]["kind"], max(ws)), "door_entry"))
    small = [w for k, w in door_w.items() if w < 0.70 - 1e-6]
    out.append(("door_inner", not small, "every inner door >= 0,70 m" if not small else "%d doors under 0,70 m" % len(small), "door_inner"))
    return out, {"parent": parent, "practicable": practicable}


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1.0)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _nearest_edge(p, pts):
    best = None
    for a, b in zip(pts, pts[1:] + pts[:1]):
        d = _seg_dist(p, a, b)
        if best is None or d < best[0]:
            best = (d, a, b)
    return best


def swings(f):
    """Every door with the two rooms it joins and the square its leaf sweeps (w x w on the side it opens to): into the
    room from the hall, into the flat at the entrance (the usual way in Spain), else into the larger room."""
    rooms, out = f["rooms"], []
    ent = (f.get("entrance") or {}).get("at")
    for d in f.get("doors", []) + ([dict(f["entrance"], entrance=True)] if f.get("entrance") else []):
        p, w = d["at"], max(d["w"], 0.70)
        near = sorted((_nearest_edge(p, r["pts"]) + (i,)) for i, r in enumerate(rooms))
        near = [n for n in near if n[0] < 0.45][:2]
        if not near or (len(near) < 2 and not d.get("entrance")):
            continue
        if d.get("entrance"):
            into = near[0][3]
        else:
            i, j = near[0][3], near[1][3]
            ki, kj = rooms[i]["kind"], rooms[j]["kind"]
            into = j if ki == "hall" and kj != "hall" else i if kj == "hall" and ki != "hall" else (i if rooms[i]["area"] >= rooms[j]["area"] else j)
        _, a, b = _nearest_edge(p, rooms[into]["pts"])
        if abs(a[1] - b[1]) < 1e-6:                      # a horizontal wall: the leaf sweeps up or down into the room
            cy = sum(q[1] for q in rooms[into]["pts"]) / len(rooms[into]["pts"])
            y0 = a[1]
            sq = (p[0] - w / 2.0, y0, p[0] + w / 2.0, y0 + w) if cy > y0 else (p[0] - w / 2.0, y0 - w, p[0] + w / 2.0, y0)
        else:                                            # a vertical wall
            cx = sum(q[0] for q in rooms[into]["pts"]) / len(rooms[into]["pts"])
            x0 = a[0]
            sq = (x0, p[1] - w / 2.0, x0 + w, p[1] + w / 2.0) if cx > x0 else (x0 - w, p[1] - w / 2.0, x0, p[1] + w / 2.0)
        other = [n[3] for n in near if n[3] != into]
        out.append({"at": p, "w": w, "into": into, "from": other[0] if other else None, "sweep": [round(v, 2) for v in sq],
                    "entrance": bool(d.get("entrance"))})
    return out


def clear_zones(f, sw, practicable):
    """3.4.1.e: a 1,20 m circle in each practicable space, free of the doors' sweep; 3.4.1.d: a 1,20 m circle in the
    hall in front of the door of each practicable space (the door may be open)."""
    out = []
    for i in sorted(practicable):
        r = f["rooms"][i]
        holes = [tuple(x["sweep"]) for x in sw if x["into"] == i]
        c = clear_width(r["pts"], holes)
        out.append(("turning", c >= 1.20 - 1e-6, "%s: %.2f m circle clear of the doors" % (r["kind"], c), "turning"))
        for x in sw:
            if i not in (x["into"], x["from"]) or x["entrance"]:
                continue
            h = x["from"] if x["into"] == i else x["into"]
            if h is None or f["rooms"][h]["kind"] != "hall":
                continue
            hall = f["rooms"][h]["pts"]
            _, a, b = _nearest_edge(x["at"], hall)
            p = x["at"]
            if abs(a[1] - b[1]) < 1e-6:                  # circle centre 0,60 m into the hall, sliding up to 0,30 m along the wall
                cy = sum(q[1] for q in hall) / len(hall)
                centres = [(p[0] + s_, a[1] + (0.6 if cy > a[1] else -0.6)) for s_ in (0.0, -0.3, 0.3)]
            else:
                cx = sum(q[0] for q in hall) / len(hall)
                centres = [(a[0] + (0.6 if cx > a[0] else -0.6), p[1] + s_) for s_ in (0.0, -0.3, 0.3)]
            ring = [(0.58 * math.cos(k * math.pi / 8), 0.58 * math.sin(k * math.pi / 8)) for k in range(16)]
            ok = any(all(inside(c0[0] + dx, c0[1] + dy, hall) for dx, dy in ring + [(0.0, 0.0)]) for c0 in centres)
            out.append(("door_circle", ok, "1,20 m circle in the hall at the %s door: %s" % (r["kind"], "yes" if ok else "no"), "hall_width"))
    return out


def checks(f, zones=True):
    """Legal and habitability checks of a fitted flat -> [{rule, ok, text, cite}]. zones=False skips the door-sweep and
    turning-circle geometry (slow): best_fits runs it only on the best candidates."""
    out, g = graph_checks(f)
    if zones:
        out += clear_zones(f, swings(f), g.get("practicable", ()))
    D = max(p[1] for r in f["rooms"] for p in r["pts"])
    lit_y = lambda r: min(p[1] for p in r["pts"]) <= 0.3 or ("back" in f.get("lit", ()) and max(p[1] for p in r["pts"]) >= D - 0.3)
    has_living = any(r["kind"] == "living" and lit_y(r) for r in f["rooms"])
    out.append(("facade_room", has_living, "a living room on the façade" if has_living else "no living room on the façade", "facade_room"))
    for i, r in enumerate(f["rooms"]):
        k = r["kind"]
        if k in ("living", "bed_main", "bed"):              # lit rooms on a façade (no loggia or balcony in front)
            on = lit_y(r)
            out.append(("facade_room", on, "%s %s a façade" % (k, "on" if on else "not on"), "facade_room"))
        if k == "hall":
            out.append(("hall_width", r["clear"] >= 1.00 - 1e-6, "hall %.2f m wide" % r["clear"], "hall_width"))
        if k == "living":
            out.append(("living_circle", r["clear"] >= 2.80 - 1e-6, "living %.2f m circle" % r["clear"], "living_circle"))
        if k == "kitchen":
            out.append(("kitchen_width", r["clear"] >= 1.60 - 1e-6, "kitchen %.2f m wide" % r["clear"], "kitchen_width"))
    return [{"rule": a, "ok": bool(ok), "text": t, "cite": CITE[c]} for a, ok, t, c in out]


def room_scores(f):
    """Each room against real flats (lab book E24): 100 at the real median clear width or more, 60 at the 10th
    percentile, lower below it."""
    out = []
    for r in f["rooms"]:
        med, p10 = REAL_CLEAR.get(r["kind"], (0, 0))
        if not med:
            sc = 100.0
        elif r["clear"] >= med:
            sc = 100.0
        elif r["clear"] >= p10:
            sc = 60.0 + 40.0 * (r["clear"] - p10) / (med - p10)
        else:
            sc = max(0.0, 60.0 * r["clear"] / p10)
        out.append({"kind": r["kind"], "area": r["area"], "clear": r["clear"], "score": round(sc)})
    return out


def coverage(f):
    """Share of the flat's rectangle W x D covered by rooms (walls take ~8-10 %; more missing = a dead corner)."""
    return sum(r["area"] for r in f["rooms"]) / max(f["W"] * f["D"], 1e-6)


def score(f, target_m2=None):
    """0-100: the fit (how little it stretched) and how close it stays to real flats (lab book E24)."""
    s = 100.0 - 120.0 * f.get("adaptivity", 0.0)
    s -= 200.0 * max(0.0, 0.90 - coverage(f))         # every m² used: rooms (walls aside) should fill the flat's space
    hall = sum(r["area"] for r in f["rooms"] if r["kind"] == "hall")
    tot = sum(r["area"] for r in f["rooms"]) or 1.0
    s -= 150.0 * max(0.0, hall / tot - 0.18)          # circulation over the real 90th percentile (18 %)
    for r in f["rooms"]:
        med, p10 = REAL_CLEAR.get(r["kind"], (0, 0))
        if p10 and r["clear"] < p10:
            s -= 8.0 * (p10 - r["clear"]) / p10 * 10.0  # narrower than 9 in 10 real rooms of its kind
    if target_m2:
        s -= 40.0 * abs(tot / target_m2 - 1.0)
    return round(max(0.0, min(100.0, s)), 1)


# ---------- matching ----------
def candidates(lib, bedrooms, lit, entry_sides, W=None, D=None, lim=MAX_STRETCH):
    """Library flats with this many bedrooms, lit only on the sides in `lit`, entered from one of `entry_sides`
    (both the plan and its mirror)."""
    out = []
    for f in lib:
        if f["bedrooms"] != bedrooms or not f["lit"] or any(s not in lit for s in f["lit"]):
            continue
        for g in (f, mirror(f)):
            if (g.get("entrance") or {}).get("side") in entry_sides:
                if D is None or lim[0] <= D / g["D"] <= lim[1]:
                    if W is None or lim[0] <= W / g["W"] <= lim[1]:
                        out.append(g)
    return out


def best_fits(lib, bedrooms, W, D, lit=("front",), entry_sides=("back",), target_m2=None, top=5, generate=False):
    """The best real plans for a W x D flat space, fitted and checked, best first; only those scoring >= 75 and
    passing every legal check. generate=True (when no real plan fits): real plans whose own size is too far from the
    space are re-proportioned up to GEN_STRETCH, keep their room graph, pass the same checks, and are marked generated."""
    res = []
    lim = GEN_STRETCH if generate else MAX_STRETCH
    for g in candidates(lib, bedrooms, lit, entry_sides, W, D, lim):
        if generate and MAX_STRETCH[0] <= W / g["W"] <= MAX_STRETCH[1] and MAX_STRETCH[0] <= D / g["D"] <= MAX_STRETCH[1]:
            continue                               # already tried as a real plan
        f = stretch(g, W, D, lim)
        if f is None:
            continue
        if generate:
            f["generated"] = True
        f = widen_doors(f)
        if not all(c["ok"] for c in checks(f, zones=False)):
            continue
        sc = score(f, target_m2)
        if sc >= (SHOW_GEN if generate else SHOW) and coverage(f) >= MIN_COVER:
            f["score"] = sc
            res.append(f)
    res.sort(key=lambda f: (-f["score"], not str(f["id"]).startswith("own:")))   # your own plan first on a tie
    seen, out = set(), []
    for f in res:                                  # best first: the door sweeps and turning circles, until `top` pass
        same = (f.get("W0"), f.get("D0"), tuple(sorted((r["kind"], round(r["area"])) for r in f["rooms"])))
        if f["id"] in seen or same in seen:         # a plan, its mirror and identical flats of one building are one option
            continue
        cs = checks(f)
        if all(c["ok"] for c in cs):
            seen.add(f["id"])
            seen.add(same)
            f["checks_lib"], f["swings"] = cs, swings(f)
            out.append(f)
            if len(out) >= top:
                break
    return out


def natural_widths(lib, bedrooms, D, lit=("front",), entry_sides=("back",)):
    """The widths real plans of this type want at depth D (their own width, after the depth stretch), narrowest first."""
    ws = sorted(set(round(g["W"] * 4) / 4.0 for g in candidates(lib, bedrooms, lit, entry_sides, None, D)))
    return ws
