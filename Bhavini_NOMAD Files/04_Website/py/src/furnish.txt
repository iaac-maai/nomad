# -*- coding: utf-8 -*-
"""Nomad - furnish a fitted flat and check it (after Finch: furniture with clearance zones, clashes flagged).

Every room gets what the law asks for, drawn so it can be checked (Decret 141/2012 Annex 1):
  bedroom   a wardrobe 0,60 m deep, 1 m long over 6 m², 1,5 m over 8 m² (3.10.1), and the 2,00 m square (2,60 m in one
            bedroom of a flat with 3 or more) still free of door swings and the wardrobe (3.8)
  kitchen   a worktop 0,60 m deep with sink and cooker (3.15.c) and 1,00 m free in front of it (3.7.3); the 1,20 m circle
            free of door swings and fixed equipment (3.4.1.e) - in the living room when the kitchen is open to it
  bathroom  WC, basin and shower (3.15.b, 3.11.1); in the practicable bathroom the 1,20 m circle free of door swings
            and the WC (3.4.1.e; the shower is flush with the floor and counts, 3.4.1.f; the basin is wall-hung)
  laundry   a place for the washing machine (3.15.d), in a bathroom or the kitchen
and what people need to live there, at typical product sizes (an assumption, not law: TYPICAL below): a bed with room
to get in, a sofa, a dining table with chairs. In practicable spaces the room to use each item is 0,80 m wide, the law's
interior route (3.4.1.e); elsewhere 0,60 m (assumption).
Nothing may sit in a door's swing or the 0,80 m in front of a door. Plain Python (IronPython 2.7, browser): no f-strings.
"""
import math

try:
    import library_fit as F
except ImportError:                                   # Grasshopper / browser load modules by path
    F = None

CITE = {
    "wardrobe": "Decret 141/2012 Annex 1 3.10.1 (a wardrobe in every bedroom: 0,60 m deep, 1 m long over 6 m², 1,5 m over 8 m²)",
    "bed_square": "Decret 141/2012 Annex 1 3.8 (2,00 m square in each bedroom, 2,60 m in one when there are 3 or more, free of door swings and storage)",
    "kitchen_equip": "Decret 141/2012 Annex 1 3.15.c and 3.7.3 (sink and cooker on a worktop, 1,00 m free in front of it)",
    "bath_equip": "Decret 141/2012 Annex 1 3.15.b and 3.11.1 (a WC, a basin and a shower)",
    "laundry": "Decret 141/2012 Annex 1 3.15.d (a place for the washing machine)",
    "fixtures_circle": "Decret 141/2012 Annex 1 3.4.1.e and 3.4.1.f (1,20 m circle free of door swings and fixed equipment up to 0,70 m)",
    "furniture": "NOMAD furniture (typical sizes, not law): a bed, a sofa and a dining table fit with room to use them",
}
# typical sizes (m), width along the wall x depth away from it - an assumption, not law
TYPICAL = {"bed_double": (1.50, 2.00), "bed_single": (0.90, 2.00), "sofa": (2.00, 0.90), "table": (1.20, 0.80),
           "wc": (0.40, 0.70), "basin": (0.60, 0.45), "shower": (0.80, 0.80), "washer": (0.60, 0.60), "fridge": (0.60, 0.65)}
WORKTOP_D, WORKTOP_MIN = 0.60, 1.80   # sink + worktop + cooker, 0,60 m each (typical); 0,60 m deep (typical)
USE, USE_PRAC, KITCHEN_FREE = 0.60, 0.80, 1.00
TALL = ("wardrobe", "fridge")         # never in front of a window
STEP = 0.15


# ---------- geometry ----------
def _inside(x, y, pts):
    c, j = False, len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def _rect_in_one(r, pts):
    """r lies inside the rectilinear polygon pts: its corners are inside and no wall crosses it."""
    x0, y0, x1, y1 = r[0] + 0.02, r[1] + 0.02, r[2] - 0.02, r[3] - 0.02
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if not _inside(x, y, pts):
            return False
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if abs(a[1] - b[1]) < 1e-6:
            if y0 < a[1] < y1 and min(a[0], b[0]) < x1 and max(a[0], b[0]) > x0:
                return False
        elif x0 < a[0] < x1 and min(a[1], b[1]) < y1 and max(a[1], b[1]) > y0:
            return False
    return True


def _rect_in(r, polys):
    """r lies inside the union of polys (one polygon: exact; several: sampled on a grid, 2 cm in from its edges)."""
    if len(polys) == 1 or _rect_in_one(r, polys[0]):
        return _rect_in_one(r, polys[0])
    x0, y0, x1, y1 = r
    nx, ny = max(2, int((x1 - x0) / 0.2) + 1), max(2, int((y1 - y0) / 0.2) + 1)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = x0 + 0.02 + (x1 - x0 - 0.04) * i / float(nx)
            y = y0 + 0.02 + (y1 - y0 - 0.04) * j / float(ny)
            if not any(_inside(x, y, p) for p in polys):
                return False
    return True


def _hit(a, b, gap=0.01):
    return a[0] < b[2] - gap and b[0] < a[2] - gap and a[1] < b[3] - gap and b[1] < a[3] - gap


def _edges(pts):
    out = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if math.hypot(b[0] - a[0], b[1] - a[1]) >= 0.4 and (abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6):
            out.append((a, b))
    return out


def _place_on(a, b, pts, t, w, d):
    """Rectangle w along the wall a-b (from offset t) and d deep into the room, its use side away from the wall."""
    if abs(a[1] - b[1]) < 1e-6:                       # horizontal wall
        x0 = min(a[0], b[0]) + t
        mx = x0 + w / 2.0
        up = _inside(mx, a[1] + 0.05, pts)
        y0 = a[1] if up else a[1] - d
        return (x0, y0, x0 + w, y0 + d), ("up" if up else "down")
    y0 = min(a[1], b[1]) + t
    my = y0 + w / 2.0
    right = _inside(a[0] + 0.05, my, pts)
    x0 = a[0] if right else a[0] - d
    return (x0, y0, x0 + d, y0 + w), ("right" if right else "left")


def _use(r, face, depth, sides=0.0):
    """The zone needed to use an item: `depth` in front of it; `sides` along its two long sides (a bed)."""
    x0, y0, x1, y1 = r
    z = []
    if face == "up":
        z.append((x0, y1, x1, y1 + depth))
    elif face == "down":
        z.append((x0, y0 - depth, x1, y0))
    elif face == "right":
        z.append((x1, y0, x1 + depth, y1))
    else:
        z.append((x0 - depth, y0, x0, y1))
    if sides:
        if face in ("up", "down"):
            z += [(x0 - sides, y0, x0, y1), (x1, y0, x1 + sides, y1)]
        else:
            z += [(x0, y0 - sides, x1, y0), (x0, y1, x1, y1 + sides)]
    return z


def _span(r, face):
    return (r[2] - r[0]) if face in ("up", "down") else (r[3] - r[1])


def _clear_width(pts, holes):
    if F is not None:
        return F.clear_width(pts, holes)
    return 0.0


# ---------- doors and windows ----------
def _door_zones(f, sw):
    """Each door's swing and the 0,80 m in front of it on the other side: nothing may stand there."""
    out = []
    for s in sw:
        x0, y0, x1, y1 = s["sweep"]
        p = s["at"]
        # the wall is the side of the sweep nearest the door point
        d = [(abs(p[1] - y0), "y0"), (abs(p[1] - y1), "y1"), (abs(p[0] - x0), "x0"), (abs(p[0] - x1), "x1")]
        side = min(d)[1]
        a = 0.80
        if side == "y0":
            app = (x0, y0 - a, x1, y0)
        elif side == "y1":
            app = (x0, y1, x1, y1 + a)
        elif side == "x0":
            app = (x0 - a, y0, x0, y1)
        else:
            app = (x1, y0, x1 + a, y1)
        out.append((x0, y0, x1, y1))
        out.append(app)
    return out


def _flip(s):
    """A door's sweep mirrored to the other side of its wall (the door opens outward)."""
    x0, y0, x1, y1 = s["sweep"]
    p, w = s["at"], s["w"]
    side = min([(abs(p[1] - y0), "y0"), (abs(p[1] - y1), "y1"), (abs(p[0] - x0), "x0"), (abs(p[0] - x1), "x1")])[1]
    if side == "y0":
        return (x0, y0 - w, x1, y0)
    if side == "y1":
        return (x0, y1, x1, y1 + w)
    if side == "x0":
        return (x0 - w, y0, x0, y1)
    return (x1, y0, x1 + w, y1)


def _window_spans(f):
    D = f["D"]
    out = []
    for w in f.get("windows", []):
        x, h = w["at"][0], w["w"] / 2.0
        if w.get("side") == "front":
            out.append(("h", 0.0, x - h, x + h))
        elif w.get("side") == "back":
            out.append(("h", D, x - h, x + h))
    if not out:                                     # library flats lit across a whole side
        for s in f.get("lit", ()):
            out.append(("h", 0.0 if s == "front" else D, -1e9, 1e9))
    return out


def _under_window(r, face, wins):
    for o, y, a, b in wins:
        wall_y = r[1] if face == "up" else r[3] if face == "down" else None
        if wall_y is not None and abs(wall_y - y) < 0.4 and r[0] < b and a < r[2]:
            return True
    return False


# ---------- placing ----------
def _best_clear(room, polys, blocked, taken, w, d, use_d, holes, tall=False, wins=()):
    """Of the spots where the item fits, the one that leaves the widest clear square in the room (with `holes` and the
    item itself not counting) -> (spot, clear width)."""
    best = None
    for res in _all_wall(room, polys, blocked, taken, w, d, use_d, tall=tall, wins=wins):
        c = _clear_width(room["pts"], list(holes) + [res[0]])
        if best is None or c > best[1] + 1e-6:
            best = (res, c)
    return best


def _all_wall(room, polys, blocked, taken, w, d, use_d, sides=0.0, tall=False, wins=(), step=0.30):
    """Every spot along the walls (corners and every `step`) where the item and its use zone fit."""
    pts = room["pts"]
    for a, b in _edges(pts):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if w > L + 1e-6:
            continue
        n = int((L - w) / step + 1e-6)
        for t in sorted(set([0.0, round(L - w, 3)] + [k * step for k in range(n + 1)])):
            r, face = _place_on(a, b, pts, t, w, d)
            if not _rect_in(r, [pts]) or any(_hit(r, z) for z in blocked) or any(_hit(r, z["rect"]) for z in taken):
                continue
            if tall and _under_window(r, face, wins):
                continue
            uz = _use(r, face, use_d, sides)
            if all(_rect_in(z, polys) and not any(_hit(z, q["rect"]) for q in taken) for z in uz):
                yield (r, face, uz)


def _try_wall(room, polys, blocked, taken, w, d, use_d, sides=0.0, tall=False, wins=(), prefer=None):
    """First spot along the room's walls where the item and the zone to use it fit (inside the room or rooms open to it),
    clear of doors and of what is already placed. prefer(rect) -> sort key (lower first)."""
    pts = room["pts"]
    found = []
    for a, b in _edges(pts):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        for ww, dd in ((w, d),):
            if ww > L + 1e-6:
                continue
            n = int((L - ww) / STEP + 1e-6)
            ts = sorted(set([0.0, L - ww] + [k * STEP for k in range(n + 1)]))
            for t in ts:
                r, face = _place_on(a, b, pts, t, ww, dd)
                if not _rect_in(r, [pts]):
                    continue
                if any(_hit(r, z) for z in blocked) or any(_hit(r, z["rect"]) for z in taken):
                    continue
                if tall and _under_window(r, face, wins):
                    continue
                uz = _use(r, face, use_d, sides)
                ok = True
                for z in uz:
                    if not _rect_in(z, polys) or any(_hit(z, q["rect"]) for q in taken):
                        ok = False
                        break
                if ok:
                    found.append((r, face, uz))
                    if prefer is None:
                        return found[0]
    if not found:
        return None
    if prefer:
        found.sort(key=lambda x: prefer(x[0], x[1]))
    return found[0]


def _try_free(room, polys, blocked, taken, w, d, ring):
    """A free-standing item (the dining table) with `ring` all round for chairs, as near the façade as it goes (daylight
    on the table): inside the room itself first, then reaching into a room open to it."""
    pts = room["pts"]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for pl in ([pts], polys) if len(polys) > 1 else ([pts],):
        best = None
        for rot in ((w, d), (d, w)):
            y = min(ys) + ring
            while y + rot[1] + ring <= max(ys) + 1e-6 and (best is None or y < best[0]):
                x = min(xs) + ring
                while x + rot[0] + ring <= max(xs) + 1e-6:
                    z = (x - ring, y - ring, x + rot[0] + ring, y + rot[1] + ring)
                    if not any(_hit(z, q) for q in blocked) and not any(_hit(z, q["rect"]) for q in taken) and _rect_in(z, pl):
                        best = (y, (x, y, x + rot[0], y + rot[1]), [z])
                        break
                    x += 0.2
                y += 0.2
        if best:
            return (best[1], "free", best[2])
    return None


def furnish(f):
    """Furniture for a fitted flat -> (items, checks). items: [{kind, rect, room, law}]; checks: [{rule, ok, text, cite}]."""
    rooms = f["rooms"]
    n = len(rooms)
    sw = f.get("swings")
    if sw is None and F is not None:
        sw = F.swings(f)
    sw = sw or []
    blocked = _door_zones(f, sw)
    wins = _window_spans(f)
    taken, out = [], []
    nbed = len([r for r in rooms if r["kind"] in ("bed", "bed_main")])
    baths = [i for i in range(n) if rooms[i]["kind"] == "bath"]
    big_bath = max(baths, key=lambda i: rooms[i]["area"]) if baths else None
    open_to = dict((i, set()) for i in range(n))
    for e in f.get("edges", []):
        if e[2] == 0 and e[0] < n and e[1] < n:
            open_to[e[0]].add(e[1]); open_to[e[1]].add(e[0])
    prac = set(i for i in range(n) if rooms[i]["kind"] in ("living", "kitchen", "bed_main")) | (set([big_bath]) if big_bath is not None else set())

    def add(kind, i, res, law):
        r = res[0]
        item = {"kind": kind, "rect": [round(v, 2) for v in r], "room": i, "law": law}
        taken.append(item)
        return item

    def polys_for(i):
        return [rooms[i]["pts"]] + [rooms[j]["pts"] for j in open_to[i] if rooms[j]["kind"] in ("living", "kitchen", "hall")]

    far = lambda i: (lambda r, face: -min([math.hypot((r[0] + r[2]) / 2.0 - s["at"][0], (r[1] + r[3]) / 2.0 - s["at"][1])
                                         for s in sw if i in (s["into"], s["from"])] or [0.0]))
    # bedrooms first: the 2,60 m square goes to the biggest bedroom
    beds = sorted([i for i in range(n) if rooms[i]["kind"] in ("bed", "bed_main")], key=lambda i: -rooms[i]["area"])
    big_square = beds[0] if (nbed >= 3 and beds) else None
    for i in beds:
        r = rooms[i]
        u = USE_PRAC if i in prac else USE
        L = 1.5 if r["area"] > 8.0 else 1.0
        sweeps = [tuple(s["sweep"]) for s in sw if s["into"] == i]
        wr = _best_clear(r, [r["pts"]], blocked, taken, L, 0.60, u, sweeps, tall=True, wins=wins)
        wr = wr[0] if wr else None
        if wr:
            out.append(add("wardrobe", i, wr, True))
        bw, bd = TYPICAL["bed_double"] if r["kind"] == "bed_main" else TYPICAL["bed_single"]
        bed = _try_wall(r, [r["pts"]], blocked, taken, bw, bd, USE, sides=(USE if r["kind"] == "bed_main" else 0.0), prefer=far(i))
        if bed is None:                                              # along the wall: one long side free (0,80 m in practicable rooms)
            bed = _try_wall(r, [r["pts"]], blocked, taken, bd, bw, u, prefer=far(i))
        if bed:
            out.append(add("bed_double" if r["kind"] == "bed_main" else "bed_single", i, bed, False))
    checks = []
    for i in beds:
        r = rooms[i]
        wr = [t for t in taken if t["room"] == i and t["kind"] == "wardrobe"]
        L = 1.5 if r["area"] > 8.0 else 1.0
        checks.append(("wardrobe", bool(wr), "%s: wardrobe %.1f m %s" % (r["kind"], L, "fits" if wr else "does not fit"), "wardrobe"))
        need = 2.60 if i == big_square else 2.00
        holes = [tuple(s["sweep"]) for s in sw if s["into"] == i] + [tuple(t["rect"]) for t in wr]
        c = _clear_width(r["pts"], holes)
        checks.append(("bed_square", c >= need - 1e-6, "%s: %.2f m square free of doors and wardrobe (needs %.2f)" % (r["kind"], c, need), "bed_square"))
        bed = [t for t in taken if t["room"] == i and t["kind"].startswith("bed")]
        checks.append(("furniture", bool(bed), "%s: bed %s" % (r["kind"], "fits with room to get in" if bed else "does not fit"), "furniture"))
    # kitchens: the worktop on the longest free wall, 1,00 m free in front (into the living room when open to it)
    washer_done = False
    for i in [i for i in range(n) if rooms[i]["kind"] == "kitchen"]:
        r = rooms[i]
        pol = polys_for(i)
        best = None
        for L in (3.0, 2.70, 2.40, 2.10, WORKTOP_MIN):
            best = _try_wall(r, pol, blocked, taken, L, WORKTOP_D, KITCHEN_FREE)
            if best:
                break
        if best:
            out.append(add("worktop", i, best, True))
            fr = _try_wall(r, pol, blocked, taken, TYPICAL["fridge"][0], TYPICAL["fridge"][1], KITCHEN_FREE, tall=True, wins=wins)
            if fr:
                out.append(add("fridge", i, fr, False))
        checks.append(("kitchen_equip", bool(best), "kitchen: worktop %s with 1,00 m free in front" %
                       ("%.1f m" % _span(best[0], best[1]) if best else "does not fit"), "kitchen_equip"))
        if i in prac:
            if open_to[i] and any(rooms[j]["kind"] == "living" for j in open_to[i]):
                checks.append(("fixtures_circle", True, "kitchen open to the living room: the 1,20 m circle is there", "fixtures_circle"))
            else:
                holes = [tuple(s["sweep"]) for s in sw if s["into"] == i] + [tuple(t["rect"]) for t in taken if t["room"] == i]
                c = _clear_width(r["pts"], holes)
                checks.append(("fixtures_circle", c >= 1.20 - 1e-6, "kitchen: %.2f m circle clear of doors and worktop" % c, "fixtures_circle"))
    # bathrooms: the practicable one gets WC, basin and shower (one shower per flat, 3.11.1) placed so the 1,20 m circle
    # stays free; its door opens outward (or slides) when that is what frees the circle. Other bathrooms: WC and basin.
    def bath_layout(i, order, bl, sweeps):
        r, mine = rooms[i], []
        for kind in order:
            w, d = TYPICAL[kind]
            if kind == "wc" and i == big_bath:
                res = _best_clear(r, [r["pts"]], bl, taken + mine, w, d, USE, sweeps)
                res = res[0] if res else None
            else:
                res = _try_wall(r, [r["pts"]], bl, taken + mine, w, d, 0.0 if kind == "shower" else USE)
            if res:
                mine.append({"kind": kind, "rect": [round(v, 2) for v in res[0]], "room": i, "law": True})
        wc = [tuple(m["rect"]) for m in mine if m["kind"] == "wc"]
        return mine, _clear_width(r["pts"], list(sweeps) + wc)

    for i in sorted(baths, key=lambda i: -rooms[i]["area"]):
        r = rooms[i]
        sweeps = [tuple(s["sweep"]) for s in sw if s["into"] == i]
        need = ("wc", "basin", "shower") if i == big_bath else ("wc", "basin")
        best, outward = None, False
        for out_ in ((False, True) if (i == big_bath and sweeps) else (False,)):
            bl = [z for z in blocked if z not in sweeps] if out_ else blocked
            for order in (("wc", "shower", "basin"), ("shower", "wc", "basin"), ("shower", "basin", "wc")):
                mine, c = bath_layout(i, order if i == big_bath else ("wc", "basin", "shower"), bl, [] if out_ else sweeps)
                full = all(k in [m["kind"] for m in mine] for k in need)
                key = (full, c >= 1.20 - 1e-6 or i != big_bath, c)
                if best is None or key > best[0]:
                    best, outward = (key, mine, c), out_
                if key[0] and key[1]:
                    break
            if best[0][0] and best[0][1]:
                break
        mine, c = best[1], best[2]
        for m in mine:
            taken.append(m)
            out.append(m)
        if outward:                                   # draw the leaf on the other side of the wall
            for s_ in sw:
                if s_["into"] == i:
                    s_["outward"] = True
                    s_["sweep"] = [round(v, 2) for v in _flip(s_)]
        have = [m["kind"] for m in mine]
        ok = all(k in have for k in need)
        checks.append(("bath_equip", ok, "bathroom: %s" % (" and ".join(need).replace("wc", "WC") + " fit" if ok else
                       "no room for the " + ", ".join(k for k in need if k not in have).replace("wc", "WC")), "bath_equip"))
        if i == big_bath:
            checks.append(("fixtures_circle", c >= 1.20 - 1e-6, "bathroom: %.2f m circle clear of doors and WC%s" %
                           (c, " (its door opens outward)" if outward else ""), "fixtures_circle"))
        if not washer_done:
            res = _try_wall(r, [r["pts"]], blocked, taken, TYPICAL["washer"][0], TYPICAL["washer"][1], USE)
            if res:
                out.append(add("washer", i, res, True))
                washer_done = True
    if not washer_done:
        for i in [i for i in range(n) if rooms[i]["kind"] in ("kitchen", "storage", "hall")]:
            res = _try_wall(rooms[i], polys_for(i), blocked, taken, TYPICAL["washer"][0], TYPICAL["washer"][1], USE)
            if res:
                out.append(add("washer", i, res, True))
                washer_done = True
                break
    checks.append(("laundry", washer_done, "washing machine %s" % ("placed" if washer_done else "has no place"), "laundry"))
    # living room: sofa against a wall, the dining table near the window with chairs round it
    for i in [i for i in range(n) if rooms[i]["kind"] == "living"][:1]:
        r = rooms[i]
        pol = polys_for(i)
        tb = _try_free(r, pol, blocked, taken, TYPICAL["table"][0], TYPICAL["table"][1], 0.60)
        if tb:
            out.append(add("table", i, tb, False))
        so = _try_wall(r, [r["pts"]], blocked, taken, TYPICAL["sofa"][0], TYPICAL["sofa"][1], USE_PRAC)
        if so:
            out.append(add("sofa", i, so, False))
        checks.append(("furniture", bool(so and tb), "living: %s" % ("sofa and dining table fit" if so and tb else
                       "no room for the " + " and ".join(k for k, v in (("sofa", so), ("dining table", tb)) if not v)), "furniture"))
    return out, [{"rule": a, "ok": bool(ok), "text": t, "cite": CITE[c]} for a, ok, t, c in checks]


HARD = ("wardrobe", "bed_square", "kitchen_equip", "bath_equip", "fixtures_circle", "laundry")


def passes(cs, strict_living=False):
    """Every legal furniture check and the bed in every bedroom (habitability) pass; the sofa and table are advice."""
    for c in cs:
        if c["rule"] in HARD and not c["ok"]:
            return False
        if c["rule"] == "furniture" and not c["ok"] and (strict_living or not c["text"].startswith("living")):
            return False
    return True
