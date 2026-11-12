# -*- coding: utf-8 -*-
"""Nomad plan generator v2: circulation and light first, then flats, then rooms, then many scored iterations.

After Finch 3D's method (docs.finch3d.com: corridors are placed first and give every flat its entrance; flats are
fitted around them to a target mix; many iterations are scored with weight sliders and the best kept), adapted to the
law of a Barcelona ground floor:
  * every dwelling needs a façade on the building's exterior free space - the street, or the block's interior
    courtyard where the plan makes it free space (Decret 141/2012 Annex 1 3.6.1), at least S/9 m long (3.6.2) and
    >= 3 m in Barcelona (MPGM 2004 DA1 2.b). A patio cut inside the shop lights rooms (2.5.1) but is NOT that façade.
  * a shared corridor >= 1,20 m (CTE DB-SUA, accessible route), every flat door within 25 m of the street door
    (CTE DB-SI SI 3 Table 3.1, one exit; Annex A: the route starts at the dwelling's door).

So a shop gets three kinds of flats:
  STREET flat   on the street, all rooms lit from it (living + bedrooms in front, hall, kitchen + bath behind).
  THROUGH flat  on the street, deeper: living (and bedroom 1) on the street; behind the hall the kitchen and bath; then
                a patio inside the flat (3 m circle, >= 9 m², Decret 141/2012 Annex 1 2.5.1) lighting the bedrooms at
                the back; a 1,30 m passage along the patio joins front and back (the Eixample "pis passant").
  BACK flat     on an exterior façade at the back of the shop (block interior), entered from a shared corridor that
                runs from a street door (a "spine"), plus a gallery along the back flats.
Iterations: corridor position and width, through flats on/off, the order of the flats along the street, and "as
asked" vs "fill the shop". Each is checked with the same rules as before (layout._check_unit) plus 3.6.1, the patio
and the escape route, then scored. Three are kept (Finch-style weights set three ways): as asked, more space per
home, most homes.
Plain Python (Grasshopper IronPython 2.7 and the browser): no f-strings, no shapely.
"""
import math

import layout
from layout import area, clip

CORR_W = (1.20, 1.50)          # CTE DB-SUA Anejo A: accessible route >= 1,20 m
EVAC_MAX = 25.0                # CTE DB-SI SI 3 Table 3.1: one exit, route <= 25 m from the dwelling's door
PATIO = 3.0                    # Decret 141/2012 Annex 1 2.5.1: patios lighting rooms: 3 m circle, >= 9 m²
LIT = layout.FRONT_MAX         # 5,5 m: deepest room lit from one side (NOMAD design assumption)
HALL = 1.30                    # hall: 1,10 m clear between partitions (Decret 141/2012 Annex 1 3.4.1.d: >= 1 m)
PASS = 1.30                    # passage along the patio of a through flat
SERVICE = 2.40                 # kitchen / bathroom band
SERVICE_MIN = 1.80
UNIT_MIN_W = 3.6
CITE = {
    "corridor": "CTE DB-SUA Anejo A (accessible route >= 1,20 m)",
    "evac": "CTE DB-SI SI 3 Table 3.1 (one exit: route <= 25 m from the dwelling's door)",
    "patio": "Decret 141/2012 Annex 1 2.5.1 (patio lighting rooms: 3 m circle, >= 9 m²)",
    "exterior": "Decret 141/2012 Annex 1 3.6.1 (a façade on the building's exterior free space, lighting the living room)",
}
ORDER = ["3bed", "2bed", "1bed", "studio"]


# ---------- rooms of one flat, in flat coordinates (x along its façade, y away from it) ----------
def _street_rooms(t, programs, size, W, D):
    front, back = layout.program_for(t, programs, size)
    L = min(LIT, D - HALL - SERVICE_MIN)
    if L < 3.0:
        return None, "too shallow"
    widths = [max(layout.MIN_WIDTH[k], a / L) for _, k, a in front]
    if sum(widths) > W + 1e-6:
        return None, "too narrow"
    k = W / sum(widths)
    widths = [w * k for w in widths]
    rooms, x = [], 0.0
    for (name, kind, _), w in zip(front, widths):
        rooms.append({"name": name, "kind": kind, "rect": (x, 0.0, x + w, L), "lit": True})
        x += w
    S = min(D - L - HALL, SERVICE + 0.6)
    rooms.append({"name": "hall", "kind": "hall", "rect": (0.0, L, W, L + HALL), "lit": False})
    rooms += _service(widths[0], W, L + HALL, L + HALL + S)
    return rooms, None


def _row_rooms(t, programs, size, W, D):
    """A shallow shop (4,5-7,4 m): living and bedrooms side by side on the street, all as deep as the shop; at one end a
    service column: entrance hall on the street, bathroom and kitchen behind it."""
    if not (4.5 <= D < 7.4):
        return None, "row flats only for 4,5-7,4 m deep"
    front, back = layout.program_for(t, programs, size)
    col = 2.4
    widths = [max(layout.MIN_WIDTH[k], a / D) for _, k, a in front]
    if sum(widths) + col > W + 1e-6:
        return None, "too narrow"
    k = (W - col) / sum(widths)
    widths = [w * k for w in widths]
    rooms, x = [], 0.0
    for (name, kind, _), w in zip(front, widths):
        rooms.append({"name": name, "kind": kind, "rect": (x, 0.0, x + w, D), "lit": True})
        x += w
    h = 1.3
    m = h + (D - h) / 2.0
    rooms += [{"name": "hall", "kind": "hall", "rect": (x, 0.0, W, h), "lit": False},
              {"name": "bathroom", "kind": "bath", "rect": (x, h, W, m), "lit": False},
              {"name": "kitchen", "kind": "kitchen", "rect": (x, m, W, D), "lit": False}]
    return rooms, None


def _service(kw0, W, y0, y1, x0=0.0):
    """Kitchen behind the living room, bathroom beside it, storage in what is left."""
    kw = max(min(kw0, W - x0 - 1.7), 1.8)
    bw = max(1.7, min(2.6, W - x0 - kw))
    out = [{"name": "kitchen", "kind": "kitchen", "rect": (x0, y0, x0 + kw, y1), "lit": False},
           {"name": "bathroom", "kind": "bath", "rect": (x0 + kw, y0, x0 + kw + bw, y1), "lit": False}]
    if W - (x0 + kw + bw) > 1.2:
        out.append({"name": "storage", "kind": "hall", "rect": (x0 + kw + bw, y0, W, y1), "lit": False})
    return out


def _through_rooms(t, programs, size, W, D, bed_front=False):
    """Living (+ bedroom 1 if bed_front and it fits) on the street; hall; kitchen + bath; patio with a side passage;
    the other bedrooms behind, lit by the patio."""
    front, back = layout.program_for(t, programs, size)
    living, beds = front[0], list(front[1:])
    if not beds or W < PASS + PATIO:
        return None, "no bedrooms to put behind, or too narrow for a patio"
    L1 = min(LIT, max(3.3, living[2] / max(W, 1.0)))
    on_street = [living]
    lw = max(layout.MIN_WIDTH["living"], living[2] / L1)
    if bed_front and len(beds) > 1 and lw + max(layout.MIN_WIDTH[beds[0][1]], beds[0][2] / L1) <= W:
        on_street.append(beds.pop(0))
    y_s = L1 + HALL
    y_p = y_s + SERVICE
    y_b = y_p + PATIO
    Lb = min(LIT, D - y_b)
    if beds and Lb < 3.0:
        return None, "too shallow for a patio and bedrooms behind"
    if not beds:
        return None, "nothing to put behind the patio"
    ws = [max(layout.MIN_WIDTH[k], a / L1) for _, k, a in on_street]
    if sum(ws) > W:
        return None, "too narrow"
    ws = [w * W / sum(ws) for w in ws]
    rooms, x = [], 0.0
    for (name, kind, _), w in zip(on_street, ws):
        rooms.append({"name": name, "kind": kind, "rect": (x, 0.0, x + w, L1), "lit": True})
        x += w
    rooms.append({"name": "hall", "kind": "hall", "rect": (0.0, L1, W, y_s), "lit": False})
    rooms.append({"name": "passage", "kind": "hall", "rect": (0.0, y_s, PASS, y_b + Lb), "lit": False})
    rooms += _service(max(ws[0] - PASS, 1.8), W, y_s, y_p, x0=PASS)
    bw = [max(layout.MIN_WIDTH[k], a / Lb) for _, k, a in beds]
    if sum(bw) > W - PASS + 1e-6:
        return None, "bedrooms behind the patio do not fit"
    bw = [w * (W - PASS) / sum(bw) for w in bw]
    x = PASS
    for (name, kind, _), w in zip(beds, bw):
        rooms.append({"name": name, "kind": kind, "rect": (x, y_b, x + w, y_b + Lb), "lit": True, "patio": True})
        x += w
    rooms.append({"name": "patio", "kind": "patio", "rect": (PASS, y_p, W, y_b), "lit": False})
    return rooms, None


def _size(rooms):
    return sum((r["rect"][2] - r["rect"][0] - 2 * layout.WALL) * (r["rect"][3] - r["rect"][1] - 2 * layout.WALL)
               for r in rooms if r["kind"] != "patio")


_CACHE = {}


STYLES = {"street": lambda t, P, z, W, D: _street_rooms(t, P, z, W, D),
          "row": lambda t, P, z, W, D: _row_rooms(t, P, z, W, D),
          "through": lambda t, P, z, W, D: _through_rooms(t, P, z, W, D, False),
          "through, bedroom 1 on the street": lambda t, P, z, W, D: _through_rooms(t, P, z, W, D, True)}


def _need_width(t, programs, size, D, through):
    """Narrowest flat of type t, D deep, that fits and meets S/9 (3.6.2) and 3 m (MPGM 2004).
    Returns (W, rooms, style); styles tried: through flats first when allowed, then street, then row."""
    key = (t, size, round(D * 4), through, id(programs))
    if key in _CACHE:
        return _CACHE[key]
    styles = (["through", "through, bedroom 1 on the street"] if through else []) + ["street", "row"]
    res = (None, None, None)
    for st in styles:
        w = UNIT_MIN_W
        while w <= 16.0:
            rooms, why = STYLES[st](t, programs, size, w, D)
            if rooms and w >= max(_size(rooms) / 9.0, 3.0):
                if res[0] is None or w < res[0] - 1e-6:
                    res = (w, rooms, st)
                break
            w += 0.25
        if res[0] is not None and st.startswith("through"):
            break                                                   # a through flat uses the depth: keep it
    _CACHE[key] = res
    return res


# ---------- fronts: every façade line of the shop ----------
class Front(object):
    def __init__(self, frame, local, spans, public):
        self.frame, self.local, self.spans, self.public = frame, local, spans, public
        self.back = False
        self.halve = False             # another usable façade faces this one: flats take half the depth (back to back)


def _key(seg):
    return tuple(tuple(round(c, 2) for c in p) for p in seg)


def _fronts(outline, facade, street):
    street_set = set(_key(s) for s in (street or facade))
    street_set |= set(_key(s[::-1]) for s in (street or facade))
    out = []
    for g in layout.facade_groups(facade):
        fr = g["frame"]
        cx, cy = layout.centroid(outline)
        if (cx - fr.ox) * fr.vx + (cy - fr.oy) * fr.vy < 0:
            fr.vx, fr.vy = -fr.vx, -fr.vy
        spans = [s for s in layout.facade_intervals(fr, g["segs"]) if s[1] - s[0] >= 3.0]
        if not spans:
            continue
        pub = any(_key(s) in street_set for s in g["segs"])
        out.append(Front(fr, [fr.to_local(p) for p in outline], spans, pub))
    out.sort(key=lambda f: (not f.public, -sum(b - a for a, b in f.spans)))
    return out


def _is_back(main, f):
    """A façade roughly parallel to the street and across the shop from it."""
    a1 = math.atan2(f.frame.uy, f.frame.ux)
    a0 = math.atan2(main.frame.uy, main.frame.ux)
    d = abs(a1 - a0) % math.pi
    if min(d, math.pi - d) > 0.35:
        return False
    return main.frame.to_local((f.frame.ox, f.frame.oy))[1] > 8.0


# ---------- flats along one front ----------
def _cut(front, a, b, types, programs, size, through, fill):
    """Flats along a front between u=a and u=b: the types asked first (in order), then (fill) as many 1-beds as fit."""
    slots, u, left = [], a, list(types)
    while u < b - UNIT_MIN_W + 1e-6:
        D = layout.depth_at(front.local, u, min(b, u + 5.0))
        if front.halve:
            D /= 2.0
        if D < 4.5:                                                   # row flats work from 4,5 m deep
            u += 0.5
            continue
        choice = None
        pool = left if left else (["1bed", "studio"] if fill else [])
        for t in pool:
            for th in ((True, False) if (through and D >= 12.0) else (False,)):
                w, rooms, st = _need_width(t, programs, size, D, th)
                if w and u + w <= b + 1e-6:
                    choice = (t, w, rooms, st)
                    break
            if choice:
                break
        if not choice:
            break
        t, w, rooms, st = choice
        if t in left:
            left.remove(t)
        slots.append({"front": front, "u0": u, "u1": u + w, "type": t, "rooms": rooms, "style": st})
        u += w
    if slots and 0.2 < b - u < 3.0 * len(slots):                    # spread what is left over the flats
        extra = (b - u) / len(slots)
        for i, s in enumerate(slots):
            s["u0"] += i * extra
            s["u1"] += (i + 1) * extra
            D = layout.depth_at(front.local, s["u0"], s["u1"]) / (2.0 if front.halve else 1.0)
            rooms, _ = STYLES[s["style"]](s["type"], programs, size, s["u1"] - s["u0"], D)
            if rooms:
                s["rooms"] = rooms
    return slots, left


def _build_unit(s, height):
    """Rooms -> world polygons (clipped to the shop) and the checks."""
    fr, local, u0 = s["front"].frame, s["front"].local, s["u0"]
    rooms, patio = [], None
    D = max(r["rect"][3] for r in s["rooms"])
    for r in s["rooms"]:
        x0, y0, x1, y1 = r["rect"]
        if r["kind"] == "patio":
            pts = clip(local, (u0 + x0, y0, u0 + x1, y1))
            if len(pts) >= 3:
                patio = {"pts": [fr.to_world(p) for p in pts], "area": round(area(pts), 1),
                         "side": round(min(x1 - x0, y1 - y0), 2), "kind": "patio inside the flat"}
            continue
        pts = clip(local, (u0 + x0 + layout.WALL, y0 + layout.WALL, u0 + x1 - layout.WALL, y1 - layout.WALL))
        a = area(pts) if len(pts) >= 3 else 0.0
        rooms.append({"name": r["name"], "kind": r["kind"], "pts": [fr.to_world(p) for p in pts] if len(pts) >= 3 else [],
                      "area": round(a, 1), "w": round(x1 - x0 - 2 * layout.WALL, 2), "d": round(y1 - y0 - 2 * layout.WALL, 2),
                      "on_facade": r["lit"], "via_patio": bool(r.get("patio"))})
    out = clip(local, (u0, 0.0, s["u1"], D))
    back = s["front"].back
    u = {"type": s["type"], "outline": [fr.to_world(p) for p in out], "facade_w": round(s["u1"] - u0, 2), "depth": round(D, 2),
         "area_m2": round(sum(r["area"] for r in rooms), 1), "rooms": rooms,
         "kind": "back" if back else s["style"].split(",")[0],
         "entry": "corridor" if back else "street", "on_patio": back}
    layout._check_unit(u, height)
    living_out = any(r["kind"] == "living" and r["on_facade"] and not r["via_patio"] for r in rooms)
    u["checks"].append({"rule": "exterior", "ok": living_out,
                        "text": "living room on the %s" % ("block interior" if back else "street"), "cite": CITE["exterior"]})
    if patio:
        ok = patio["side"] >= PATIO - 1e-6 and patio["area"] >= 9.0
        u["checks"].append({"rule": "patio", "ok": ok, "text": "patio %.1f m², smallest side %.2f m" % (patio["area"], patio["side"]),
                            "cite": CITE["patio"]})
    u["ok"] = all(c["ok"] for c in u["checks"])
    u["fails"] = sorted(set(c["rule"] for c in u["checks"] if not c["ok"]))
    return u, patio


def _inside(x, y, poly):
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def _hit(pa, pb):
    """Two polygons overlap (the centre of one inside the other)?"""
    ca = (sum(p[0] for p in pa) / len(pa), sum(p[1] for p in pa) / len(pa))
    cb = (sum(p[0] for p in pb) / len(pb), sum(p[1] for p in pb) / len(pb))
    return _inside(ca[0], ca[1], pb) or _inside(cb[0], cb[1], pa)


def _overlap(frame, rect, poly, tol=0.5):
    """Does world polygon `poly` cover more than tol m² of the flat rect (u0, v0, u1, v1) of this front frame?
    (The centre test above misses two flats that cross at a corner.)"""
    pts = clip([frame.to_local(p) for p in poly], rect)
    return len(pts) >= 3 and area(pts) > tol


# ---------- one iteration ----------
def build(outline, facade, street, height, mix, programs, size="typical", cw=1.2, pos=0.5, through=True,
          small_first=False, fill=False, spine=True, halve=False):
    """One plan. spine=False: no shared corridor, so the block-interior façade gets no flats (nothing reaches it).
    halve: where two usable façades face each other, flats on each take half the depth (back to back)."""
    fronts = _fronts(outline, facade, street)
    want = []
    for t in (ORDER[::-1] if small_first else ORDER):
        want += [t] * int(mix.get(t, 0) or 0)
    if not fronts:
        return _plan(outline, size, [], [], [], want, want, {})
    main = fronts[0]
    back = [f for f in fronts[1:] if not f.public and _is_back(main, f)]
    if not spine:
        fronts = [f for f in fronts if f not in back]
        back = []
    side = [f for f in fronts[1:] if f not in back]
    for f in fronts:
        f.halve = halve and any(g is not f and _is_back(f, g) for g in fronts)
    left = list(want)
    s0, s1 = max(main.spans, key=lambda s: s[1] - s[0])
    spine = None
    if back:
        c = s0 + cw / 2 + pos * (s1 - s0 - cw)
        spine = (c - cw / 2, c + cw / 2)
    slots = []
    pieces = [(s0, s1)] if not spine else [(s0, spine[0]), (spine[1], s1)]
    for a, b in sorted(pieces, key=lambda p: -(p[1] - p[0])):           # 1. the street
        sl, left = _cut(main, a, b, left, programs, size, through, fill)
        slots += sl
    for f in side:                                                       # 2. a second street (corner shop)
        for a, b in f.spans:
            sl, left = _cut(f, a, b, left, programs, size, False, fill)
            slots += sl
    for f in back:                                                       # 3. the block interior, from the corridor
        f.back = True
        for a, b in f.spans:
            sl, left = _cut(f, a, b, left, programs, size, False, fill)
            slots += sl
    for s in slots:
        s["front_no"] = fronts.index(s["front"])
    units, patios, placed, where = [], [], [], []
    for s in slots:
        u, pat = _build_unit(s, height)
        rect = (s["u0"], 0.0, s["u1"], u["depth"])
        if len(u["outline"]) < 3 or u["area_m2"] < 30.0 or any(_overlap(s["front"].frame, rect, q) for q in placed):
            left.append(s["type"]) if s["type"] in want else None
            continue
        u["front_no"] = s["front_no"]
        placed.append(u["outline"])
        units.append(u)
        where.append((s["front"].frame, rect))
        if pat:
            patios.append(pat)
    corridors = []
    backs = [u for u in units if u["kind"] == "back"]
    if spine and backs:
        fr, local = main.frame, main.local
        mid = (spine[0] + spine[1]) / 2

        def route(us):                                                   # spine to the gallery, then along it
            pts = [fr.to_local(p) for u in us for p in u["outline"]]
            return min(p[1] for p in pts), pts
        vb, _ = route(backs)
        for u in backs:                                                  # a back flat beyond 25 m is not proposed
            uc = sum(fr.to_local(p)[0] for p in u["outline"]) / len(u["outline"])
            u["_evac"] = vb + abs(uc - mid) + far_door(u)
        far = [u for u in backs if u["_evac"] > EVAC_MAX]
        backs = [u for u in backs if u["_evac"] <= EVAC_MAX]
        if backs:
            vb, pts = route(backs)
            lo, hi = min(p[0] for p in pts), max(p[0] for p in pts)
            for rect in ((spine[0], 0.0, spine[1], vb), (min(lo, spine[0]), vb - cw, max(hi, spine[1]), vb)):
                q = clip(local, rect)
                if len(q) >= 3:
                    corridors.append({"pts": [fr.to_world(p) for p in q], "width": cw, "length": round(vb, 1)})
            for u in backs:
                u["checks"].append({"rule": "evac", "ok": True, "cite": CITE["evac"],
                                    "text": "door %.1f m from the street door along the corridor" % u.pop("_evac")})
        cut = [u for u, (ufr, rect) in zip(units, where)                 # street flats the corridor or gallery crosses
               if u["kind"] != "back" and any(_overlap(ufr, rect, c["pts"]) for c in corridors)]
        for u in far + cut:
            units.remove(u)
            if u["type"] in want:
                left.append(u["type"])
        for u in units:
            u.pop("_evac", None)
    if not corridors:                                                    # back flats with no corridor have no door
        for u in [u for u in units if u["kind"] == "back"]:
            units.remove(u)
            if u["type"] in want:
                left.append(u["type"])
    return _plan(outline, size, units, patios, corridors, left, want,
                 {"corridor_w": cw if corridors else None, "corridor_at": pos if corridors else None, "through": through,
                  "small_first": small_first, "fill": fill, "back_to_back": halve})


def far_door(u):
    """Flat door to its furthest room door, m: the fire route starts at the furthest room (evaluation matrix 1.5)."""
    e = u.get("entrance")
    if not e:
        return 0.0
    return max([((d["at"][0] - e[0]) ** 2 + (d["at"][1] - e[1]) ** 2) ** 0.5 for d in u.get("doors", [])] or [0.0])


def _plan(outline, size, units, patios, corridors, left, want, params):
    shell = area(outline)
    compliant = [u for u in units if u["ok"]]
    cap = int(math.ceil(shell / 0.9 / 80.0 - 1e-9))
    req = len(want)
    plan = {"requested": req, "placed": len(units), "compliant": len(compliant),
            "unplaced": [{"type": t, "reason": "no façade or depth left"} for t in left],
            "density_cap": cap, "density_ok": len(units) <= cap, "shell_area_m2": round(shell, 1),
            "unused_m2": round(max(shell - sum(u["area_m2"] for u in units) - sum(p["area"] for p in patios), 0), 1),
            "units": units, "size": size, "patios": patios, "corridors": corridors, "params": params,
            "density_cite": layout.CITE["density"],
            "assumptions": "street and through flats entered from the street, back flats from a shared corridor; new windows 60%% of "
                           "each room's width x 1,5 m; rooms lit from one side up to %.1f m deep" % LIT}
    plan["proposal_ok"] = req > 0 and not left and len(compliant) >= req and plan["density_ok"]
    plan["other_use_m2"] = plan["unused_m2"]
    plan["other_use"] = ("%.0f m² stay non-residential: no flat there would have its own façade on the street or the block "
                         "interior (Decret 141/2012 Annex 1 3.6.1, 3.6.2 S/9). Use: storage, bike room, community room or a "
                         "small workshop for the building." % plan["unused_m2"]) if plan["unused_m2"] >= 15 else ""
    iv = []
    n_th = sum(1 for u in units if u["kind"] == "through")
    if n_th:
        iv.append("%d through flat%s with a patio inside (%s m²) - %s" % (
            n_th, "s" if n_th > 1 else "", " + ".join("%.0f" % p["area"] for p in patios), CITE["patio"]))
    if corridors:
        iv.append("shared corridor %.2f m wide to the back flats - %s; %s" % (params.get("corridor_w") or 0, CITE["corridor"], CITE["evac"]))
    plan["interventions"] = iv
    return plan


# ---------- iterations, scored ----------
def metrics(plan, mix):
    req = max(plan["requested"], 1)
    got = {}
    for u in plan["units"]:
        if u["ok"]:
            got[u["type"]] = got.get(u["type"], 0) + 1
    match = sum(min(got.get(t, 0), int(mix.get(t, 0) or 0)) for t in ORDER) / float(req)
    shell = max(plan["shell_area_m2"], 1)
    used = sum(u["area_m2"] for u in plan["units"] if u["ok"])
    return {"match": match, "passing": plan["compliant"], "eff": used / shell,
            "per_home": used / max(plan["compliant"], 1), "fails": plan["placed"] - plan["compliant"]}


WEIGHTS = {"match": 10, "passing": 1, "eff": 3, "per_home": 0.0, "fails": -2}    # Finch-style weight sliders


def scaled(programs, k):
    """Room sizes k times the learned ones (rooms never go under the minimums program_for keeps)."""
    out = {}
    for t, p in programs.items():
        q = dict(p)
        for f in ("living_m2", "main_bedroom_m2", "other_bedroom_m2", "kitchen_m2", "bath_m2", "circulation_m2"):
            if q.get(f):
                q[f] = dict((kk, v * k) for kk, v in q[f].items())
        out[t] = q
    return out


# The iterations are CIRCULATION STRATEGIES (as Finch's floor-plate options: around existing circulation, new cores,
# corridors + core), each searched over its own parameters and scored with the same weights.
# "As it is" is the baseline: flats along the street, each entered from it, as deep as their rooms need.
#   both façades   where two façades face each other (a shop running through the block, a corner) flats on each side,
#                  back to back, each half the depth: more façade = more homes, since S/9 caps a flat's depth (~9-10 m)
#   corridor       a shared corridor from a street door to flats on the block-interior façade (+ a gallery)
#   small flats    fill the shop with studios and 1-beds on every reachable façade (most homes, compact rooms)
# Not a strategy: the "through" flat with a patio inside. Its patio lights the bedrooms (2.5.1) but is not exterior
# façade (3.6.1), so its useful area outgrows S/9 of its street façade at every width (tested 5-13 m): it never passes.
# A strategy is shown only if it changes the plan (both façades: passing flats on >= 2 façades; corridor: >= 1 back
# flat passes; small flats: more homes than as it is) and is not the same plan as one already shown. Variants: corridor width and position, flat order.
STRATEGIES = [
    ("flats on both façades", {"spine": [False, True], "halve": [True], "fill": [False, True], "size": ["typical"]}),
    ("corridor to the block interior", {"spine": [True], "halve": [False, True], "fill": [False], "size": ["typical"]}),
    ("small flats, fill the shop", {"spine": [True], "halve": [False, True], "fill": [True], "size": ["compact"]}),
]


def _needs(name, plan):
    ok = [u for u in plan["units"] if u["ok"]]
    if name == "flats on both façades":
        return len(set(u["front_no"] for u in ok)) >= 2 and plan["params"].get("back_to_back")
    if name == "corridor to the block interior":
        return any(u["kind"] == "back" for u in ok)
    return bool(ok)


def _sig(plan):
    return tuple(sorted((u["type"], round(sum(p[0] for p in u["outline"]), 0), round(sum(p[1] for p in u["outline"]), 0))
                        for u in plan["units"]))


def search(outline, facade, street, height, mix, programs):
    """Best plan of each strategy. Returns ({name: (score, plan, metrics)}, tried)."""
    best, tried = {}, 0
    for name, v in STRATEGIES:
        for spine in v["spine"]:
            for cw in (CORR_W if spine else CORR_W[:1]):
                for pos in ((0.0, 0.5, 1.0) if spine else (0.5,)):
                    for halve in v["halve"]:
                        for fill in v["fill"]:
                            for small_first in (False, True):
                                plan = build(outline, facade, street, height, mix, programs, v["size"][0], cw, pos, False,
                                             small_first, fill, spine, halve)
                                tried += 1
                                if not _needs(name, plan):
                                    continue
                                m = metrics(plan, mix)
                                sc = sum(WEIGHTS[kk] * m[kk] for kk in WEIGHTS)
                                if name not in best or sc > best[name][0]:
                                    best[name] = (sc, plan, m)
    return best, tried


def _passing_only(plan):
    """A proposal shows only flats that pass: a failing one goes to 'unplaced' with the room that fails."""
    bad = [u for u in plan["units"] if not u["ok"]]
    if not bad:
        return plan
    plan = dict(plan)
    plan["units"] = [u for u in plan["units"] if u["ok"]]
    plan["unplaced"] = list(plan["unplaced"]) + [{"type": u["type"], "reason": "its %s does not fit" % ", ".join(u.get("fails") or ["rooms"])}
                                                 for u in bad]
    plan["placed"] = len(plan["units"])
    plan["density_ok"] = plan["placed"] <= plan["density_cap"]
    plan["unused_m2"] = plan["other_use_m2"] = round(plan["unused_m2"] + sum(u["area_m2"] for u in bad), 1)
    return plan


def iterations(outline, facade, height, mix, programs, street=None):
    """'as it is' (street flats only, rooms as learned) and one iteration per circulation strategy that gives a plan
    different from it (0 to 3). Returns (before, [(name, plan, metrics)], tried)."""
    st = street or facade
    _CACHE.clear()                     # keyed by id(programs): a later run (browser worker) can reuse that id
    before = build(outline, facade, [], height, mix, programs, "typical", through=False, spine=False)
    best, tried = search(outline, facade, st, height, mix, programs)
    out, seen = [], set([_sig(before)])
    for name, _ in STRATEGIES:
        if name not in best:
            continue
        sc, plan, m = best[name]
        if _sig(plan) in seen or (name == "small flats, fill the shop" and plan["compliant"] <= before["compliant"]):
            continue                                                   # same plan, or no more homes than as it is
        seen.add(_sig(plan))
        plan = dict(plan)
        plan["strategy"] = name
        if plan["params"].get("fill"):                                 # judged on what it places, not on the mix asked
            plan["unplaced"] = []
            plan = _passing_only(plan)
            plan["unplaced"] = []
            plan["requested"] = plan["placed"]
            plan["proposal_ok"] = plan["placed"] > 0 and plan["compliant"] == plan["placed"] and plan["density_ok"]
        else:
            plan = _passing_only(plan)
            plan["proposal_ok"] = plan["requested"] > 0 and not plan["unplaced"] and plan["compliant"] >= plan["requested"] and plan["density_ok"]
        plan["stage6"] = "%s: %d flats pass, %.0f%% of the floor in homes" % (name, plan["compliant"], 100 * m["eff"])
        out.append((name, plan, m))
    if not out:                                                        # nothing beats the street flats: say why
        plan = _passing_only(dict(before))
        plan["proposal_ok"] = plan["requested"] > 0 and not plan["unplaced"] and plan["compliant"] >= plan["requested"] and plan["density_ok"]
        plan["strategy"] = "street flats only"
        plan["stage6"] = ("street flats only: no second façade facing it and no block-interior façade within %.0f m of a "
                          "street door, so no circulation adds a home (Decret 141/2012 Annex 1 3.6.1, 3.6.2 S/9; "
                          "CTE DB-SI SI 3)" % EVAC_MAX)
        out.append(("street flats only", plan, metrics(plan, mix)))
    return before, out, tried
