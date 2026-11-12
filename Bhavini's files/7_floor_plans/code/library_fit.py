# -*- coding: utf-8 -*-
"""Nomad - fill a flat with a real plan: match, stretch, check, score (after Finch's adaptive plan library).

The library (7_floor_plans/code/build_library.py) holds real flats that pass every NOMAD rule, squared: rooms as rectilinear
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
    "circulation": "NOMAD circulation rule, not law: the door opens into a hall, living room and bedrooms come off the hall, nobody walks through a private room",
    "openings": "NOMAD rule, not law: at least 0,30 m of wall between the entrance door and a window",
    "neighbours": "NOMAD comfort rule, not law: kitchen joined to the living room and within 6 m of the door, no bedroom wall shared with the living room or kitchen, bathroom within 5 m of each bedroom",
    "wet": "v5.0 brief, not law: kitchens and bathrooms against a 60 x 60 cm duct chase on a party wall or hall; doors 15 cm clear of corners",
    "sightline": "NOMAD comfort rule, not law: from the entrance door or the living room you do not look straight at a bedroom or bathroom door",
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
GAP_KS = (0.7, 0.8, 0.9, 1.1, 1.25, 1.4)   # widths tried in the gaps real plans leave (plan3._row), as shares of the real widths
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
    out += circulation(f, rooms, adj, start)
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
                centres = [(p[0] + s_, a[1] + d_) for s_ in (0.0, -0.3, 0.3) for d_ in (0.6, -0.6)]      # either side: an L hall's middle is no guide
            else:
                centres = [(a[0] + d_, p[1] + s_) for s_ in (0.0, -0.3, 0.3) for d_ in (0.6, -0.6)]
            ring = [(0.58 * math.cos(k * math.pi / 8), 0.58 * math.sin(k * math.pi / 8)) for k in range(16)]
            ok = any(all(inside(c0[0] + dx, c0[1] + dy, hall) for dx, dy in ring + [(0.0, 0.0)]) for c0 in centres)
            out.append(("door_circle", ok, "1,20 m circle in the hall at the %s door: %s" % (r["kind"], "yes" if ok else "no"), "hall_width"))
    return out


def jamb_doors(f):
    """A real plan keeps its rooms and connections; a door too near a corner slides along its wall until it has its 15 cm jamb."""
    for d in f.get("doors", []):
        for _ in range(2):
            for r in f["rooms"]:
                if r["kind"] == "storage":
                    continue
                es = list(zip(r["pts"], r["pts"][1:] + r["pts"][:1]))
                a, b = min(es, key=lambda e: _seg_dist(d["at"], e[0], e[1]))
                if _seg_dist(d["at"], a, b) > 0.3:
                    continue
                ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
                t = (d["at"][0] - a[0]) * ux + (d["at"][1] - a[1]) * uy
                m = d["w"] / 2.0 + DOOR_JAMB
                if ln >= 2 * m and (t < m or t > ln - m):
                    n = max(m, min(ln - m, t)) - t
                    d["at"] = [round(d["at"][0] + ux * n, 3), round(d["at"][1] + uy * n, 3)]
    return f


def checks(f, zones=True):
    """Legal and habitability checks of a fitted flat -> [{rule, ok, text, cite}]. zones=False skips the door-sweep and
    turning-circle geometry (slow): best_fits runs it only on the best candidates."""
    jamb_doors(f)
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
_CAND = {}
TABLE = [None]                       # 7_floor_plans/code/fit_table.py: which plans can pass at each size, worked out once; None: try them all


def _listed(bedrooms, lit, entry_sides, W, D, generate):
    """The plans the table lists for this size, or None when there is no table."""
    if TABLE[0] is None:
        return None
    k = "%d|%s|%s|%d" % (bedrooms, ",".join(lit), ",".join(entry_sides), bool(generate))
    return set(TABLE[0]["ids"][i] for i in TABLE[0]["fits"].get(k, {}).get("%d,%d" % (round(W * 4), round(D * 4)), ()))


def candidates(lib, bedrooms, lit, entry_sides, W=None, D=None, lim=MAX_STRETCH):
    """Library flats with this many bedrooms, lit only on the sides in `lit`, entered from one of `entry_sides`
    (both the plan and its mirror)."""
    key = (id(lib), len(lib), bedrooms, tuple(lit), tuple(entry_sides))
    if key not in _CAND:                           # the library does not change during a run: filter and mirror it once
        _CAND[key] = [g for f in lib if f["bedrooms"] == bedrooms and f["lit"] and not any(s not in lit for s in f["lit"])
                      for g in (f, mirror(f)) if (g.get("entrance") or {}).get("side") in entry_sides]
    return [g for g in _CAND[key] if (D is None or lim[0] <= D / g["D"] <= lim[1]) and (W is None or lim[0] <= W / g["W"] <= lim[1])]


def iter_fits(lib, bedrooms, W, D, lit=("front",), entry_sides=("back",), target_m2=None, generate=False):
    """The best real plans for a W x D flat space, best first, each one checked only when it is asked for: the score costs
    nothing and the legal checks are slow, so the plans are ranked first and the search stops as soon as the caller has enough.
    Only those scoring >= 75 (55 for generate) and passing every legal check. generate=True (when no real plan fits): real plans
    whose own size is too far from the space are re-proportioned up to GEN_STRETCH, keep their room graph, and are marked generated."""
    res = []
    lim = GEN_STRETCH if generate else MAX_STRETCH
    listed = _listed(bedrooms, lit, entry_sides, W, D, generate)
    for g in candidates(lib, bedrooms, lit, entry_sides, W, D, lim):
        if listed is not None and str(g["id"]) not in listed and not str(g["id"]).startswith("own:"):
            continue                               # the table says this plan cannot pass at this size
        if generate and MAX_STRETCH[0] <= W / g["W"] <= MAX_STRETCH[1] and MAX_STRETCH[0] <= D / g["D"] <= MAX_STRETCH[1]:
            continue                               # already tried as a real plan
        f = stretch(g, W, D, lim)
        if f is None:
            continue
        if generate:
            f["generated"] = True
        sc = score(f, target_m2)
        if sc >= (SHOW_GEN if generate else SHOW) and coverage(f) >= MIN_COVER:
            f["score"] = sc
            res.append(f)
    res.sort(key=lambda f: (-f["score"], not str(f["id"]).startswith("own:")))   # your own plan first on a tie
    seen = set()
    for f in res:
        same = (f.get("W0"), f.get("D0"), tuple(sorted((r["kind"], round(r["area"])) for r in f["rooms"])))
        if f["id"] in seen or same in seen:         # a plan, its mirror and identical flats of one building are one option
            continue
        f = widen_doors(f)
        cs = checks(f)
        if all(c["ok"] for c in cs):
            seen.add(f["id"])
            seen.add(same)
            f["checks_lib"], f["swings"] = cs, swings(f)
            yield f


def best_fits(lib, bedrooms, W, D, lit=("front",), entry_sides=("back",), target_m2=None, top=5, generate=False):
    """The first `top` of iter_fits."""
    out = []
    for f in iter_fits(lib, bedrooms, W, D, lit, entry_sides, target_m2, generate):
        out.append(f)
        if len(out) >= top:
            break
    return out


def natural_widths(lib, bedrooms, D, lit=("front",), entry_sides=("back",)):
    """The widths real plans of this type want at depth D (their own width, after the depth stretch), narrowest first."""
    ws = sorted(set(round(g["W"] * 4) / 4.0 for g in candidates(lib, bedrooms, lit, entry_sides, None, D)))
    return ws


# ---------- the room placer: rooms from rules + how real plans join them (connection table: 15,545 real plans, 7_floor_plans/code/placed_plans.py) ----------
T = 0.10            # partition, m (the library's gap between rooms)
HALL = 1.50         # the entry hall: 1,10 m clear beside a 35 cm coat and shoe drop zone (evaluation matrix 2.1, 2.3)
BRANCH = 1.25       # the second corridor: circle of 1,20 m in front of the doors (3.4.1.d)
BATH = 1.60         # practicable bath, wide enough for the 1,20 m circle and its fittings
KITCHEN = 3.0       # kitchen depth at most, HALL_D = hall depth at most, on deep flats
HALL_D = 2.6
LIVING = 2.90       # 2,80 m circle (3.7.2) + a little
BED = 2.65          # a 2,60 m square for the main bedroom (3.8)


CONN = {"bath|bed_main|door": 0.381, "bath|bed|door": 0.231, "bath|hall|door": 0.513, "bath|hall|open": 0.447, "bath|living|door": 0.422, "bed_main|hall|door": 0.627, "bed_main|hall|open": 0.46, "bed_main|kitchen|door": 0.036, "bed_main|living|door": 0.536, "bed|bed_main|door": 0.032, "bed|hall|door": 0.594, "bed|hall|open": 0.429, "bed|living|door": 0.506, "hall|hall|door": 0.03, "hall|kitchen|door": 0.279, "hall|kitchen|open": 0.497, "hall|living|door": 0.44, "hall|living|open": 0.656, "hall|storage|door": 0.138, "kitchen|living|door": 0.273, "kitchen|living|open": 0.527}


def joined(a, b):
    """How real plans join these two kinds of room: "open" or "door", whichever is more common. Bedrooms and baths always get a door."""
    a, b = sorted((a, b))
    if a in ("bath", "bed", "bed_main") or b in ("bath", "bed", "bed_main"):
        return "door"
    return "open" if CONN.get("%s|%s|open" % (a, b), 0) > CONN.get("%s|%s|door" % (a, b), 0) else "door"


FOYER_M2 = 3.0                   # evaluation matrix 2.1 (not law)
SPINE_W = 1.10                   # evaluation matrix 2.3, primary corridor (not law); the other halls keep the law's 1,00 m
GROCERY = 6.0                    # evaluation matrix 3.1: door to kitchen, m (not law)
BED_BATH = 5.0                   # evaluation matrix 3.4: bedroom to bathroom, m (not law)
DOOR_JAMB = 0.15                 # a door stands 15 cm clear of any wall corner (v5.0 brief, not law)
DUCT = 0.60                      # service duct chase, 60 x 60 cm, boxed into the corner of a wet room (v5.0 brief)
DROP_D = 0.35                    # evaluation matrix 2.1 asks for a drop zone; its size is our design choice
TURNS = 2                        # evaluation matrix 3.1: no tight route to the kitchen; at most two right-angle turns (design choice)


def drop_zone(f):
    """A strip for coats and shoes beside the entrance that leaves the entry hall wide enough: 1,00 m long, 35 cm deep. None if it does not fit."""
    e, rooms = f.get("entrance") or {}, f["rooms"]
    at, i = e.get("at"), e.get("room")
    if not at or i is None or rooms[i]["kind"] != "hall" or rooms[i].get("clear", 0) < SPINE_W + DROP_D - 1e-6:
        return None
    n = {"front": (0, 1), "back": (0, -1), "left": (1, 0), "right": (-1, 0)}.get(e.get("side"))
    if not n:
        return None
    k = 0 if n[0] == 0 else 1                             # k runs across the hall, 1 - k along it
    ks = [c[k] for c in rooms[i]["pts"]]
    sweeps = [x["sweep"] for x in swings(f) if x.get("sweep")]
    for wall, sign in ((max(ks), -1), (min(ks), 1)):
        c = at[1 - k] + n[1 - k] * 1.0
        lo, hi = sorted((wall, wall + sign * DROP_D))
        r = [lo, c - 0.5, hi, c + 0.5] if k == 0 else [c - 0.5, lo, c + 0.5, hi]
        clear_of = lambda w: min(r[2], w[2]) - max(r[0], w[0]) <= 0.01 or min(r[3], w[3]) - max(r[1], w[1]) <= 0.01
        if all(inside(x, y, rooms[i]["pts"]) or min(_seg_dist((x, y), p, q) for p, q in zip(rooms[i]["pts"], rooms[i]["pts"][1:] + rooms[i]["pts"][:1])) < 0.02
               for x, y in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]))) and all(clear_of(w) for w in sweeps) and                 not any(r[0] - 0.2 < d["at"][0] < r[2] + 0.2 and r[1] - 0.2 < d["at"][1] < r[3] + 0.2 for d in f.get("doors", [])):
            return [round(v, 2) for v in r]
    return None


def circulation(f, rooms, adj, start):
    """The human circulation filter. From the door a person walks: into a hall (never straight into a room), along the halls,
    and from them into the living room, each bedroom and a bathroom; the kitchen comes off a hall or the living room.
    The 30 cm of wall between the entrance door and a window is checked here too."""
    bad, spine, q = [], set(), [start]
    if rooms[start]["kind"] != "hall":
        bad.append("the door opens into the " + rooms[start]["kind"])
    else:
        if rooms[start].get("area", 0) < FOYER_M2:
            bad.append("the foyer is under %.1f m2" % FOYER_M2)
        if rooms[start].get("clear", 0) < SPINE_W - 1e-6:
            bad.append("the entry hall is under %.2f m wide" % SPINE_W)
        if not drop_zone(f) and not any(rooms[j]["kind"] == "storage" for j in adj[start]):
            bad.append("no place for coats and shoes at the door")
        while q:
            i = q.pop()
            if i not in spine:
                spine.add(i)
                q += [j for j in adj[i] if rooms[j]["kind"] == "hall"]
        off = lambda i, ok: bool(adj[i] & ok)
        living = {i for i, r in enumerate(rooms) if r["kind"] == "living"}
        for i, r in enumerate(rooms):
            if r["kind"] in ("living", "bed", "bed_main") and not off(i, spine):
                bad.append("the %s is not off a hall" % r["kind"])
            if r["kind"] == "kitchen" and not off(i, spine | living):
                bad.append("the kitchen is not off a hall or the living room")
        baths = [i for i, r in enumerate(rooms) if r["kind"] == "bath"]
        if baths and not any(off(i, spine) for i in baths):
            bad.append("no bathroom off a hall")
    out = [("circulation", not bad, "; ".join(bad) or "door into a hall, every room off it", "circulation")]
    e, gap = f.get("entrance") or {}, None
    along = 0 if e.get("side") in ("front", "back") else 1
    for w in f.get("windows", []):
        if w.get("side") == e.get("side") and e.get("at"):
            g = abs(w["at"][along] - e["at"][along]) - (w.get("w", 0) + e.get("w", 0)) / 2.0
            gap = g if gap is None else min(gap, g)
    if gap is not None:
        out.append(("openings", gap >= 0.30 - 1e-6, "%.2f m of wall between the door and the window" % gap, "openings"))
    return out + comfort_checks(f, rooms, adj)


def _shared_wall(a, b, gap=0.3, step=0.25):
    """Length of a's walls that run within gap of room b, m (sampled every 25 cm)."""
    n, pts, qs = 0.0, a["pts"], list(zip(b["pts"], b["pts"][1:] + b["pts"][:1]))
    for p, q in zip(pts, pts[1:] + pts[:1]):
        ln = math.hypot(q[0] - p[0], q[1] - p[1])
        k = max(int(ln / step), 1)
        for i in range(k):
            x = (p[0] + (q[0] - p[0]) * (i + 0.5) / k, p[1] + (q[1] - p[1]) * (i + 0.5) / k)
            if any(_seg_dist(x, c, d) <= gap for c, d in qs):
                n += ln / k
    return n


def _step(f, a, b, at):
    """Where you step from room a to room b: their door, else the point of their shared wall nearest to you."""
    A, B = f["rooms"][a], f["rooms"][b]
    db = _doors_of(f, B)
    ds = [p for p in _doors_of(f, A) if p in db]
    if ds:
        return min(ds, key=lambda p: math.hypot(p[0] - at[0], p[1] - at[1]))
    best, qs = None, list(zip(B["pts"], B["pts"][1:] + B["pts"][:1]))
    for p, q in zip(A["pts"], A["pts"][1:] + A["pts"][:1]):
        ln = math.hypot(q[0] - p[0], q[1] - p[1])
        k = max(int(ln / 0.25), 1)
        for i in range(k):
            x = (p[0] + (q[0] - p[0]) * (i + 0.5) / k, p[1] + (q[1] - p[1]) * (i + 0.5) / k)
            g = min(_seg_dist(x, c, d) for c, d in qs)
            v = (max(g, 0.3), math.hypot(x[0] - at[0], x[1] - at[1]))
            if best is None or v < best[0]:
                best = (v, x)
    return best[1]


def _adj(f):
    n = len(f["rooms"])
    adj = [set() for _ in range(n)]
    for e in f.get("edges", []):
        if e[0] < n and e[1] < n:
            adj[e[0]].add(e[1]); adj[e[1]].add(e[0])
    return adj


def route(f, adj=None, goal=("kitchen",)):
    """The shortest walk from the flat's door to the threshold of the kitchen: [points], door to door. None: not reached."""
    import heapq
    adj = adj or _adj(f)
    e = f.get("entrance") or {}
    start = e.get("room")
    if start is None or not e.get("at"):
        return None
    if f["rooms"][start]["kind"] in goal:
        return [tuple(e["at"])]
    done, n, h = set(), 0, [(0.0, 0, start, [tuple(e["at"])])]
    while h:
        d, _, i, path = heapq.heappop(h)
        if i in done:
            continue
        done.add(i)
        at = path[-1]
        for j in adj[i]:
            if j in done or f["rooms"][j]["kind"] in ("bed", "bed_main", "bath"):
                continue
            t = tuple(_step(f, i, j, at))
            nd = d + math.hypot(t[0] - at[0], t[1] - at[1])
            if f["rooms"][j]["kind"] in goal:
                return path + [t]
            n += 1
            heapq.heappush(h, (nd, n, j, path + [t]))
    return None


def path_length(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def path_turns(path):
    """Bends sharper than 60 degrees along a route."""
    n = 0
    for a, b, c in zip(path, path[1:], path[2:]):
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu > 0.05 and lv > 0.05 and (u[0] * v[0] + u[1] * v[1]) / (lu * lv) < 0.5:
            n += 1
    return n


def walk(f, adj, goal=("kitchen",)):
    p = route(f, adj, goal)
    return None if p is None else path_length(p)


def _doors_of(f, r):
    return [d["at"] for d in f.get("doors", []) if any(_seg_dist(d["at"], c, e) <= 0.3 for c, e in zip(r["pts"], r["pts"][1:] + r["pts"][:1]))]


def ducts(f):
    """Each wet room gets a duct chase in its corner on a party wall, or else on a hall. A neighbour's chase may serve it too.
    The flat's sides, x = 0 and x = W, are its party walls; the same plan repeats floor by floor, so the chases stack."""
    W, out = f["W"], []
    halls = [r["pts"] for r in f["rooms"] if r["kind"] == "hall"]
    for i, r in enumerate(f["rooms"]):
        if r["kind"] not in ("kitchen", "bath"):
            continue
        xs, ys = [p[0] for p in r["pts"]], [p[1] for p in r["pts"]]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        corners = [(x, y) for x in (x0, x1) for y in (y0, y1)]
        party = [c for c in corners if c[0] <= 0.3 or c[0] >= W - 0.3]
        wall = [c for c in corners if any(_seg_dist(c, a, b) <= 0.3 for h in halls for a, b in zip(h, h[1:] + h[:1]))]
        pick = party or wall
        if not pick:
            continue
        c = max(pick, key=lambda q: q[1])                 # the corner furthest from the facade: the windows stay clear
        dx, dy = (DUCT if c[0] == x0 else -DUCT), (DUCT if c[1] == y0 else -DUCT)
        d = [round(v, 3) for v in (min(c[0], c[0] + dx), min(c[1], c[1] + dy), max(c[0], c[0] + dx), max(c[1], c[1] + dy))]
        if not any(abs(d[0] - e["rect"][0]) < 0.4 and abs(d[1] - e["rect"][1]) < 0.4 for e in out):
            out.append({"rect": d, "room": i, "party": bool(party)})
    return out


def comfort_checks(f, rooms, adj):
    """Rooms next to each other as people live in them, and what you see from the door."""
    bad = []
    kinds = lambda *k: [i for i, r in enumerate(rooms) if r["kind"] in k]
    lv, kt, bd, ba = kinds("living"), kinds("kitchen"), kinds("bed", "bed_main"), kinds("bath")
    if kt and lv and not any(adj[i] & set(lv) for i in kt):
        bad.append("the kitchen is not joined to the living room")
    if any(_shared_wall(rooms[i], rooms[j]) >= 0.5 for i in bd for j in lv):
        bad.append("a bedroom shares a wall with the living room")
    if any(_shared_wall(rooms[i], rooms[j]) >= 0.5 for i in bd for j in kt):
        bad.append("a bedroom shares a wall with the kitchen")
    for i in bd:
        dist = [abs(p[0] - q[0]) + abs(p[1] - q[1]) for j in ba for p in _doors_of(f, rooms[i]) for q in _doors_of(f, rooms[j])]
        if dist and min(dist) > BED_BATH:
            bad.append("the bathroom is %.1f m from a bedroom" % min(dist))
    door_to_kitchen = walk(f, adj)
    if kt and (door_to_kitchen is None or door_to_kitchen > GROCERY):
        bad.append("the kitchen is %s from the door" % ("not reached" if door_to_kitchen is None else "%.1f m" % door_to_kitchen))
    path = route(f, adj)
    if path and path_turns(path) > TURNS:
        bad.append("the way to the kitchen has %d tight turns" % path_turns(path))
    full = swings(f)
    sw = [x["sweep"] for x in full if x.get("sweep")]
    over = lambda a, b: max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    if any(over(sw[i], sw[j]) > 0.02 for i in range(len(sw)) for j in range(i + 1, len(sw))):
        bad.append("two door swings cross")
    for x in full:
        w, into = x.get("sweep"), x.get("into")
        if w and into is not None and into < len(rooms):
            es = list(zip(rooms[into]["pts"], rooms[into]["pts"][1:] + rooms[into]["pts"][:1]))
            if any(not inside(c[0], c[1], rooms[into]["pts"]) and min(_seg_dist(c, a, b) for a, b in es) > 0.15 for c in ((w[0], w[1]), (w[2], w[1]), (w[2], w[3]), (w[0], w[3]))):
                bad.append("a door swings into a wall")
                break
        if x.get("entrance") and (f.get("entrance") or {}).get("room") != into:
            bad.append("the entrance door does not open into the flat")
    for d in f.get("doors", []):                         # jambs: no door flush against a corner (wardrobe and closet fronts excepted)
        for r in rooms:
            if r["kind"] == "storage":
                continue
            es = list(zip(r["pts"], r["pts"][1:] + r["pts"][:1]))
            a, b = min(es, key=lambda e: _seg_dist(d["at"], e[0], e[1]))
            if _seg_dist(d["at"], a, b) <= 0.3:
                ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                t = ((d["at"][0] - a[0]) * (b[0] - a[0]) + (d["at"][1] - a[1]) * (b[1] - a[1])) / ln
                if min(t, ln - t) < d["w"] / 2.0 + DOOR_JAMB - 0.02:
                    bad.append("a door has no 15 cm jamb")
                    break
        else:
            continue
        break
    wet = [i for i, r in enumerate(rooms) if r["kind"] in ("kitchen", "bath")]
    fed = set(x["room"] for x in ducts(f))
    if any(i not in fed and not any(any(_seg_dist(c, a, b) <= 0.9 for c in ((x["rect"][0], x["rect"][1]), (x["rect"][2], x["rect"][3])) for a, b in zip(rooms[i]["pts"], rooms[i]["pts"][1:] + rooms[i]["pts"][:1])) for x in ducts(f)) for i in wet):
        bad.append("a wet room has no service duct")
    out = [("neighbours", not bad, "; ".join(bad) or "kitchen by the living room, bedrooms apart from it, bathroom close", "neighbours")]
    e = f.get("entrance") or {}
    seen = False
    if e.get("at") and e.get("side") in ("front", "back", "left", "right"):
        k = 0 if e["side"] in ("front", "back") else 1              # the door looks along the other axis; k is across the view
        for i in bd + ba:
            for c, d in zip(rooms[i]["pts"], rooms[i]["pts"][1:] + rooms[i]["pts"][:1]):
                facing = abs(c[1 - k] - d[1 - k]) < 0.05
                for p in _doors_of(f, rooms[i]):
                    if facing and _seg_dist(p, c, d) <= 0.3 and abs(p[k] - e["at"][k]) <= 0.6:
                        seen = True
    for j in lv:                                         # nor from the living room straight into a bedroom
        for i in bd:
            for p in _doors_of(f, rooms[j]):
                for q in _doors_of(f, rooms[i]):
                    if p != q and (abs(p[0] - q[0]) < 0.6 or abs(p[1] - q[1]) < 0.6) and math.hypot(p[0] - q[0], p[1] - q[1]) < 2.0:
                        seen = True
    out.append(("sightline", not seen, "a bedroom or bathroom door faces the entrance or living room" if seen else "no bedroom or bathroom door faces the entrance", "sightline"))
    return out


def matrix_items(f):
    """What the evaluation matrix asks of one flat. Everything a flat needs is also a check, so a passing flat earns all of it."""
    rooms = f["rooms"]
    c = {}
    for x in f.get("checks_lib", []):
        c[x["rule"]] = c.get(x["rule"], True) and x["ok"]
    every = lambda *k: all(c.get(i, True) for i in k)
    return {"openings": every("openings"), "foyer": every("circulation", "sightline"), "no_thoroughfare": every("circulation", "graph"), "widths": every("circulation", "hall_width"),
            "doors": every("turning", "door_circle", "neighbours"), "grocery": every("neighbours"), "quiet": every("neighbours"), "affinity": every("neighbours")}


def comfort(f):
    """The Human Comfort Scale, 0-100: 25 each for a clear entry, an efficient way to the kitchen, bedrooms kept quiet, door arcs unblocked."""
    rooms, n, e = f["rooms"], len(f["rooms"]), f.get("entrance") or {}
    adj = _adj(f)
    start = e.get("room")
    entry = start is not None and start < n and rooms[start]["kind"] == "hall" and rooms[start].get("area", 0) >= FOYER_M2
    way = walk(f, adj)
    grocery = way is not None and way <= GROCERY
    lv = [i for i, r in enumerate(rooms) if r["kind"] in ("living", "kitchen")]
    quiet = not any(_shared_wall(rooms[i], rooms[j]) >= 0.5 for i, r in enumerate(rooms) if r["kind"] in ("bed", "bed_main") for j in lv)
    sw = [x["sweep"] for x in swings(f) if x.get("sweep")]
    over = lambda a, b: min(a[2], b[2]) - max(a[0], b[0]) > 0.05 and min(a[3], b[3]) - max(a[1], b[1]) > 0.05
    arcs = not any(over(sw[i], sw[j]) for i in range(len(sw)) for j in range(i + 1, len(sw)))
    arcs = arcs and not any(c.get("rule") == "door_swing" and not c.get("ok") for c in f.get("checks_furn", []))
    return 25 * (entry + grocery + quiet + arcs)


def graph_score(f):
    """How common this flat's connections are in real plans, 0-1."""
    rs, v = f["rooms"], []
    for e in f.get("edges", []):
        x, y = sorted((rs[e[0]]["kind"], rs[e[1]]["kind"]))
        v.append(CONN.get("%s|%s|%s" % (x, y, "door" if e[2] > 0 else "open"), 0.0))
    return sum(v) / max(len(v), 1)


SPARE = 2.5                      # a wider cut makes two flats, not one with giant rooms (design choice)


def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _planned_flat(beds, W, D, Yb, ident, back=False, fit=False):
    """A flat planned from its door. Across the facade: living room | hall | bedrooms, so the hall (or a closet at its front end)
    keeps the bedrooms off the living room. The door is on the facade, or at the back when the flat is entered from a shared hall.
    With two or more bedrooms the hall branches behind them as a second corridor. Behind: kitchen open to the living room,
    bathroom off the side of the hall (out of the door's line of sight), storage."""
    rooms, doors, edges, wins = [], [], [], []
    def add(kind, pts):
        rooms.append({"kind": kind, "pts": [[round(x, 3), round(y, 3)] for x, y in pts]}); return len(rooms) - 1
    def door(i, j, x, y, w=0.8):
        doors.append({"at": [round(x, 3), round(y, 3)], "w": w}); edges.append([i, j, w])
    spare = W - LIVING - T - HALL - (T + beds * BED + (beds - 1) * T if beds else 0.0)
    if spare < -1e-6 or (spare > SPARE and not fit) or D - Yb - T < 1.7:
        return None
    flex = LIVING + spare + beds * BED                    # the width living room and bedrooms share, split 35 : 40 as in the brief
    a = max(LIVING, flex * 35.0 / 75.0) if beds else flex
    bw = BED if not beds else max(BED, (flex - a) / beds)
    a = flex - beds * bw
    hx, Yh, corr, bx = a + T, Yb + T, beds > 1, W - BATH
    x_h = hx + HALL
    Yr = Yh + BRANCH + T if corr else Yh                    # where the back rooms start
    if D - Yr < 1.7:
        return None
    Ye = D if back else max(min(D, Yh + KITCHEN), min(D, Yr + 2.6))    # kitchen and bathroom end on one line
    if D - Ye - T < 1.0:
        Ye = D
    He = D if back else (Yh + BRANCH if corr else min(Ye, Yh + 1.4))     # where the hall ends: no longer than its last door needs
    if not back and not corr and Ye - He - T < 1.0:
        He = Ye
    Y0 = Yb - 1.7 if back and Yb - 1.7 - T >= 1.0 else 0.0  # entered from the back: a closet closes the front of the hall
    lv = add("living", _box(0, 0, a, Yb))
    wins.append({"at": [round(a / 2, 3), 0.0], "w": round(a * 0.6, 2), "side": "front"})
    if corr:
        ha = add("hall", [[hx, Y0], [x_h, Y0], [x_h, Yh], [W, Yh], [W, Yh + BRANCH], [x_h, Yh + BRANCH], [x_h, He], [hx, He]] if He > Yh + BRANCH else
                 [[hx, Y0], [x_h, Y0], [x_h, Yh], [W, Yh], [W, Yh + BRANCH], [hx, Yh + BRANCH]])
    else:
        ha = add("hall", _box(hx, Y0, x_h, He))
    if Y0 > 0:
        cl = add("storage", _box(hx, 0, x_h, Y0 - T)); door(ha, cl, hx + HALL / 2, Y0 - T / 2, 0.7)
    kw = a if beds else a - T - BATH
    if kw < 1.6:
        return None
    ki = add("kitchen", _box(0, Yh, kw, Ye)); edges.append([lv, ki, 0.0])
    if beds:                                              # the short way in with the shopping: from the hall straight to the kitchen
        (edges.append([ha, ki, 0.0]) if joined("hall", "kitchen") == "open" else door(ha, ki, a + T / 2, Yh + 0.6))
    if Ye < D and not back:
        sk = add("storage", _box(0, Ye + T, W, D)); door(ki, sk, kw / 2, Ye + T / 2)
    if beds == 0:
        ba = add("bath", _box(kw + T, Yr, a, Ye)); door(ha, ba, hx - T / 2, Yr + 0.7)
    elif corr:
        shift = bw + T if beds >= 3 else 0.0                # three bedrooms: the bathroom moves to the middle one, so all stay close
        b0 = x_h + T + shift if He > Yh + BRANCH or shift else hx   # the bathroom sits by the hall, so every bedroom is close to it
        b1 = x_h + T + BATH + shift
        ba = add("bath", _box(b0, Yr, b1, Ye)); door(ha, ba, b1 - 0.7, Yr - T / 2)
        if shift:
            sl = add("storage", _box(x_h + T if He > Yh + BRANCH else hx, Yr, b0 - T, Ye)); door(ha, sl, b0 - 0.6, Yr - T / 2, 0.7)
        if W - b1 - T >= 1.0:
            st = add("storage", _box(b1 + T, Yr, W, Ye)); door(ha, st, b1 + T + 0.5, Yr - T / 2, 0.7)
    else:
        bx0 = x_h + T
        ba = add("bath", _box(bx0, Yr, W, Ye)); door(ha, ba, bx0 - T / 2, Yr + 0.7)
    if not back and not corr and Ye - He - T >= 1.0:
        st = add("storage", _box(hx, He + T, x_h, Ye)); door(ha, st, hx + HALL / 2, He + T / 2, 0.7)
    (edges.append([ha, lv, 0.0]) if joined("hall", "living") == "open" else door(ha, lv, a + T / 2, Yb - 0.8))
    for k in range(beds):
        x0 = x_h + T + k * (bw + T)
        i = add("bed_main" if k == 0 else "bed", _box(x0, 0, x0 + bw, Yb))
        wins.append({"at": [round(x0 + bw / 2, 3), 0.0], "w": round(bw * 0.6, 2), "side": "front"})
        if corr:
            door(ha, i, x0 + min(1.6, bw - 0.7), Yb + T / 2)
        else:
            door(ha, i, x0 - T / 2, Yb - 0.7)
    ent = {"at": [round(hx + 0.55, 3), D if back else 0.0], "w": 0.9, "side": "back" if back else "front", "room": ha}   # off centre: the leaf opens against one wall, the drop zone stands at the other
    for r in rooms:
        r["area"] = round(poly_area(r["pts"]), 2); r["clear"] = round(clear_width(r["pts"]), 2)
    return {"id": ident, "bedrooms": beds, "W": W, "D": D, "rooms": rooms, "doors": doors, "windows": wins, "entrance": ent, "edges": edges,
            "lit": ["front"], "useful": round(sum(r["area"] for r in rooms), 1), "source": "NOMAD placed", "W0": W, "D0": D}


SHARES = {0: {"living": 0.55, "kitchen": 0.25, "bath": 0.20}, 1: {"living": 0.35, "bed": 0.40, "kitchen": 0.15, "bath": 0.10}}   # room shares of a flat, v3.5 brief


def share_gap(f):
    """How far a flat's rooms are from the brief's shares, 0 = on target. A target only: the law's minimum rooms always win."""
    goal = SHARES[0 if not f.get("bedrooms") else 1]
    got = dict((k, 0.0) for k in goal)
    for r in f["rooms"]:
        k = {"bed_main": "bed", "hall": "bath"}.get(r["kind"], r["kind"])
        if k in got:
            got[k] += r.get("area", 0.0)
    t = sum(got.values()) or 1.0
    return sum(abs(got[k] / t - goal[k]) for k in goal)


CLOSET = 0.70                    # the closet bank that keeps bedrooms off the living room in a paired flat (design choice)


WET_W = 2.0                      # the kitchen's width on the facade in a wet-core flat (design choice)


def _wet_flat(beds, W, D, Yb, ident, notch=0.0):
    """A flat of two or three bedrooms for a mirrored pair, with its wet core pinned to the party wall, on the right.
    Facade row, from the far end: bedrooms | closet bank | living room | kitchen, so the kitchen is beside the foyer and shares the
    party wall's plumbing. Behind it one straight hall runs from the foyer past every room. The main bathroom stands at the party
    wall; a second bathroom among the bedrooms keeps each of them close."""
    rooms, doors, edges, wins = [], [], [], []
    def add(kind, pts):
        rooms.append({"kind": kind, "pts": [[round(x, 3), round(y, 3)] for x, y in pts]}); return len(rooms) - 1
    def door(i, j, x, y, w=0.8):
        doors.append({"at": [round(x, 3), round(y, 3)], "w": w}); edges.append([i, j, w])
    spare = W - notch - (beds * BED + (beds - 1) * T + T + CLOSET + T + LIVING + T + WET_W)
    Yh = Yb + T
    Yr = Yh + HALL + T
    if spare < -1e-6 or D - Yr < 1.7:
        return None
    x, bs = 0.0, []
    for k in range(beds):
        i = add("bed" if k < beds - 1 else "bed_main", _box(x, 0, x + BED, Yb))
        wins.append({"at": [round(x + BED / 2, 3), 0.0], "w": round(BED * 0.6, 2), "side": "front"})
        bs.append((i, x)); x += BED + T
    zone = x - T                                          # where the bedrooms end
    cl = add("storage", _box(x, 0, x + CLOSET, Yb)); x += CLOSET + T
    a = LIVING + spare
    lv = add("living", _box(x, 0, x + a, Yb))
    wins.append({"at": [round(x + a / 2, 3), 0.0], "w": round(a * 0.6, 2), "side": "front"})
    lx = x; x += a + T
    ki = add("kitchen", _box(x, 0, x + WET_W, Yb)); edges.append([lv, ki, 0.0])
    wins.append({"at": [round(x + WET_W / 2, 3), 0.0], "w": round(WET_W * 0.6, 2), "side": "front"})
    ha = add("hall", _box(0, Yh, W, Yh + HALL))
    door(ha, ki, x + WET_W / 2, Yb + T / 2)
    (edges.append([ha, lv, 0.0]) if joined("hall", "living") == "open" else door(ha, lv, lx + a / 2, Yb + T / 2))
    door(ha, cl, zone + T + CLOSET / 2, Yb + T / 2)
    for i, x0 in bs:
        door(ha, i, x0 + 0.7, Yb + T / 2)
    b0 = W - 2.2
    ba = add("bath", _box(b0, Yr, W, D)); door(ha, ba, b0 + 0.7, Yr - T / 2)
    b2 = zone / 2.0 - 1.1
    bb = add("bath", _box(b2, Yr, b2 + 2.2, D)); door(ha, bb, b2 + 0.7, Yr - T / 2)
    if b2 - T >= 1.0:
        s1 = add("storage", _box(0, Yr, b2 - T, D)); door(ha, s1, 0.7, Yr - T / 2)
    if b0 - T - (b2 + 2.2 + T) >= 1.0:
        s2 = add("storage", _box(b2 + 2.2 + T, Yr, b0 - T, D)); door(ha, s2, b2 + 2.2 + T + 0.5, Yr - T / 2)
    ent = {"at": [round(W - 0.55, 3), Yh], "w": 0.9, "side": "front", "room": ha}
    for r in rooms:
        r["area"] = round(poly_area(r["pts"]), 2); r["clear"] = round(clear_width(r["pts"]), 2)
    return {"id": ident, "bedrooms": beds, "W": W, "D": D, "rooms": rooms, "doors": doors, "windows": wins, "entrance": ent, "edges": edges,
            "lit": ["front"], "useful": round(sum(r["area"] for r in rooms), 1), "source": "NOMAD placed", "W0": W, "D0": D, "Yb": Yb}


def _pair_flat(beds, W, D, Yb, ident, notch=0.0):
    """Half of a mirrored pair. The party wall is on the right. The shared lobby comes in from the street along that wall and stops at
    the two foyers, which touch across the party wall: notch is the lobby's half width, taken out of the facade row only.
    Facade row: living room | closet bank | bedrooms. Behind it the hall runs from the foyer door to the living room,
    with the kitchen at its far end, joined to the living room, and the bathroom and storage behind the hall."""
    rooms, doors, edges, wins = [], [], [], []
    def add(kind, pts):
        rooms.append({"kind": kind, "pts": [[round(x, 3), round(y, 3)] for x, y in pts]}); return len(rooms) - 1
    def door(i, j, x, y, w=0.8):
        doors.append({"at": [round(x, 3), round(y, 3)], "w": w}); edges.append([i, j, w])
    need = LIVING + (T + CLOSET + T + beds * BED + (beds - 1) * T if beds else 0.0)
    spare = W - notch - need
    if spare < -1e-6 or D - Yb - T < HALL + T + 1.7:
        return None
    bw, a = BED, LIVING + spare                           # what is spare goes to the living room, which keeps the kitchen near the door
    ka = max(1.8, a - (1.3 if beds else 2.4))             # the kitchen leaves part of the living room's back wall open to the hall
    Yh = Yb + T
    Yr = Yh + HALL + T
    Ye = max(min(D, Yh + KITCHEN), min(D, Yr + 2.6))
    if D - Ye - T < 1.0:
        Ye = D
    if Ye - Yr < 1.7:
        return None
    lv = add("living", _box(0, 0, a, Yb))
    wins.append({"at": [round(a / 2, 3), 0.0], "w": round(a * 0.6, 2), "side": "front"})
    ha = add("hall", _box(ka + T, Yh, W, Yh + HALL))
    ki = add("kitchen", _box(0, Yh, ka, Ye)); edges.append([lv, ki, 0.0])
    (edges.append([ha, ki, 0.0]) if joined("hall", "kitchen") == "open" else door(ha, ki, ka + T / 2, Yh + 0.6))
    (edges.append([ha, lv, 0.0]) if joined("hall", "living") == "open" else door(ha, lv, (ka + T + a) / 2, Yb + T / 2))
    b1 = min(W, ka + T + 2.2)
    ba = add("bath", _box(ka + T, Yr, b1, Ye)); door(ha, ba, b1 - 0.7, Yr - T / 2)
    if W - b1 - T >= 1.0:
        st = add("storage", _box(b1 + T, Yr, W, Ye)); door(ha, st, b1 + T + 0.5, Yr - T / 2)
    if Ye < D:
        sk = add("storage", _box(0, Ye + T, W, D)); door(ki, sk, ka / 2, Ye + T / 2)
    if beds:
        cl = add("storage", _box(a + T, 0, a + T + CLOSET, Yb)); door(ha, cl, a + T + CLOSET / 2, Yb + T / 2)
    for k in range(beds):
        x0 = a + 2 * T + CLOSET + k * (bw + T)
        i = add("bed_main" if k == 0 else "bed", _box(x0, 0, x0 + bw, Yb))
        wins.append({"at": [round(x0 + bw / 2, 3), 0.0], "w": round(bw * 0.6, 2), "side": "front"})
        door(ha, i, x0 + min(1.0, bw - 0.7), Yb + T / 2)
    ent = {"at": [round(W - 0.55, 3), Yh], "w": 0.9, "side": "front", "room": ha}                   # the foyer door, in the lobby's end wall beside the party wall
    for r in rooms:
        r["area"] = round(poly_area(r["pts"]), 2); r["clear"] = round(clear_width(r["pts"]), 2)
    return {"id": ident, "bedrooms": beds, "W": W, "D": D, "rooms": rooms, "doors": doors, "windows": wins, "entrance": ent, "edges": edges,
            "lit": ["front"], "useful": round(sum(r["area"] for r in rooms), 1), "source": "NOMAD placed", "W0": W, "D0": D, "Yb": Yb}


def place_flat(beds, W, D, Yb, ident, street=False, fit=False, pair=None):
    """W x D, the facade at y = 0: entered from the street, or (street=False) from a shared hall at the back. Yb = depth of the bedrooms."""
    if pair is not None:
        return (_wet_flat if beds >= 2 else _pair_flat)(beds, W, D, Yb, ident, pair)
    return _planned_flat(beds, W, D, Yb, ident, back=not street, fit=fit)
