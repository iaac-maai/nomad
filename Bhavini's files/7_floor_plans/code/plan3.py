# -*- coding: utf-8 -*-
"""Nomad plan generator v3: real flats, stretched to fit, around a shared hall (Finch's method, the real flats' rules).

How a shop becomes homes, as real buildings do it (lab book E24: 85 % of real flats open into their own hall from a
common stair or corridor; living rooms and bedrooms on the façade, baths and stores inside):
  1 street door + lobby   a 1,50 m wide lobby from the street (CTE DB-SUA Anejo A: 1,50 m turning circle in the
                          entrance vestibule of an accessible route)
  2 shared hall           a corridor behind the street flats, 1,20 m or 1,50 m wide (CTE DB-SUA Anejo A, accessible route
                          >= 1,20 m), from the lobby both ways
  3 street flats          each a REAL flat from the library (7_floor_plans/code/build_library.py): lit only from its front,
                          entered from the back, stretched to its space with locked walls (7_floor_plans/code/library_fit.py),
                          then checked: the law, the plan graph, doors and turning circles
  4 block-interior flats  where the shop has a façade on the block interior: a spine from the lobby to a gallery, and real
                          flats lit from that façade; every flat door within 25 m of the street door (CTE DB-SI SI 3)
  5 what is left          building storage, bike room or community room - never a scrap inside a flat
Iterations (scored with the same Finch-style weights as v2): flat depth, lobby position, hall width, the order of the
flats, "as asked" or "fill the shop", with or without block-interior flats.
Plain Python (Grasshopper IronPython 2.7 and the browser): no f-strings, no shapely.
"""
import io, json, math, os, time

import layout
import furnish as U
import library_fit as F
import plan2
from layout import area, clip

LOBBY = 1.50                     # CTE DB-SUA Anejo A: 1,50 m turning circle in the entrance vestibule
SEG = 40.0                       # one street door per 40 m of street façade: flats on both sides stay within 25 m of it
HALLS = (1.20, 1.50)             # CTE DB-SUA Anejo A: accessible route >= 1,20 m
DEPTHS = (6.0, 7.0, 8.0, 9.0)    # flat depths tried; real one-sided flats are 6,5-7 m deep (library median)
DOOR_DEPTHS = (5.75, 6.0, 6.5, 7.0, 8.0, 9.0)   # flats with their own street door
SHALLOW = (5.0,)                 # also tried in shops under 6,5 m deep
EVAC_MAX = plan2.EVAC_MAX
NAMES = {"living": "living", "bed_main": "bedroom 1", "bed": "bedroom", "kitchen": "kitchen", "bath": "bathroom",
         "hall": "hall", "storage": "storage"}
BEDS = {"studio": 0, "1bed": 1, "2bed": 2, "3bed": 3}
CITE = dict(plan2.CITE)
CITE["lobby"] = "CTE DB-SUA Anejo A (1,50 m turning circle in the entrance vestibule)"
_LIB = {}
_FIT = {}
BUDGET = None                    # seconds for the real-plan search in one run; the browser sets it, the city run and Rhino do not
_DEADLINE = [None]
_EXISTING = []                   # the building's own portal / stair on this ground floor (world polygons): never built over
_PATIOS = []                     # light wells open to the sky on this ground floor (Catastro building parts): never built over
_OUTLINE = []                    # the shop outline (world): every room corner must lie inside it
_FLOOR = []                      # the flats already cut from this floor (world corners)
FLOOR_TOL = 0.05                 # m2: rounding slivers along a shared wall
GAPS = [True]                    # fill the gaps along a facade with generated plans
SMALL = [False]                  # shared.py: allow smaller, generated studios in the rows
USEFUL_MIN = [40.0]              # MPGM 2004 DA1 2.a; shared-space housing (shared.py): 24 m² private + shared rooms
LIT = [None]                     # lit depth (m) from a window: the daylight prediction for this place, else flags.LIT_DEPTH
LIT_CITE = ["NOMAD liveability, not law: the daylight model (DF >= 2 % reaches this depth)"]
LIT_SHARE = 0.5                  # a living room or bedroom has at least half its floor in the lit depth (design choice)


def _lit_share(pts, D, through=False):
    """Share of a room's floor (flat coordinates, window at y = 0, and y = D for a through flat) within LIT of a window."""
    if not LIT[0]:
        return None
    a = area(pts) or 1.0
    lit = area(clip(pts, (-1e9, -1.0, 1e9, LIT[0])))
    if through:
        lit += area(clip(pts, (-1e9, D - LIT[0], 1e9, D + 1.0)))
        if D - LIT[0] < LIT[0]:
            lit -= area(clip(pts, (-1e9, D - LIT[0], 1e9, LIT[0])))
    return round(min(1.0, lit / a), 2)



def _set_outline(outline):
    pts = [tuple(p) for p in outline]
    _OUTLINE[:] = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    del _FLOOR[:]


def _shared(a, b):
    """The floor two convex shapes have in common, m2 (the part of a inside b, clipped edge by edge)."""
    out = _overlap_of(a, b)
    return area(out) if len(out) >= 3 else 0.0


def _overlap_of(a, b):
    """The part of a inside the convex shape b."""
    sign = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(b, b[1:] + b[:1]))
    out = list(a)
    for p, q in zip(b, b[1:] + b[:1]):
        if not out:
            return []
        inside = lambda c: ((q[0] - p[0]) * (c[1] - p[1]) - (q[1] - p[1]) * (c[0] - p[0])) * sign >= 0
        new = []
        for c, d in zip(out, out[1:] + out[:1]):
            if inside(c) != inside(d):
                t0 = (q[0] - p[0]) * (c[1] - p[1]) - (q[1] - p[1]) * (c[0] - p[0])
                t1 = (q[0] - p[0]) * (d[1] - p[1]) - (q[1] - p[1]) * (d[0] - p[0])
                k = t0 / (t0 - t1)
                x = (c[0] + k * (d[0] - c[0]), c[1] + k * (d[1] - c[1]))
                new += [c, x] if inside(c) else [x]
            elif inside(c):
                new.append(c)
        out = new
    return out


def _taken(poly):
    """The rule of the floor: each flat is cut from the floor still free, so no two flats can claim the same floor."""
    return any(_shared(poly, q) > FLOOR_TOL for q in _FLOOR)


def _free(front, u0, u1, d):
    """No existing portal or stair inside this rectangle of a front, and no flat already cut from this floor."""
    box = [tuple(front.frame.to_world(c)) for c in ((u0, 0.0), (u1, 0.0), (u1, d), (u0, d))]
    x0, x1, y0, y1 = min(c[0] for c in box), max(c[0] for c in box), min(c[1] for c in box), max(c[1] for c in box)
    for q in _EXISTING + _PATIOS:                      # the full overlap only for what is near: most of the existing floor is not
        if max(c[0] for c in q) > x0 and min(c[0] for c in q) < x1 and max(c[1] for c in q) > y0 and min(c[1] for c in q) < y1:
            if plan2._overlap(front.frame, (u0, 0.0, u1, d), q):
                return False
    return not _taken(box)


def library(path=None):
    """The street-flat library: real flats lit from one side that pass every check (built by 7_floor_plans/code/build_library.py,
    kept small by 7_floor_plans/code/street_library.py)."""
    if "lib" not in _LIB:
        here = os.path.dirname(os.path.abspath(__file__))
        for p in [path] if path else [os.path.join(here, "library_street.json"),
                                       os.path.join(here, "..", "output", "library", "library_street.json")]:
            if p and os.path.exists(p):
                with io.open(p, encoding="utf-8") as f:
                    _LIB["lib"] = json.load(f)
                break
    if "all" not in _LIB:                              # one list, so the mirrored plans in library_fit.candidates are made once
        _LIB["all"] = _LIB.get("lib", []) + _LIB.get("own", [])
    return _LIB["all"]


def use_table(path):
    """The browser's shortcut: 7_floor_plans/code/fit_table.py lists the plans that can pass at each size, so the rest are never tried."""
    if F.TABLE[0] is None and os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            F.TABLE[0] = json.load(f)


def set_own(entries):
    """Your own plans (7_floor_plans/code/own_plans.py) join the library for the next layouts."""
    entries = list(entries or [])
    if [e["id"] for e in entries] != [e["id"] for e in _LIB.get("own", [])]:
        _LIB["own"] = entries
        _LIB.pop("all", None)
        F._CAND.clear()
        _FIT.clear()


MODES = {"door": (("front",), ("front",)),                       # entered from the street through its own door
         "hall": (("front",), ("back",)),                       # lit sides allowed, entrance sides allowed
         "through_l": (("front", "back"), ("right",)),             # a through flat left of a passage: door on its right
         "through_r": (("front", "back"), ("left",)),
         "side_l": (("front",), ("right",)),                       # a street flat left of a passage, entered from its side
         "side_r": (("front",), ("left",))}


def fits(t, W, D, target=None, mode="hall", gen=True):
    """The best real plans for this space, furnished and checked (up to 3). None real fits and gen: generated plans
    (library_fit.best_fits generate=True: a real plan's room graph re-proportioned further, same checks)."""
    key = (t, round(W * 4), round(D * 4), round(target or 0), mode)
    if key not in _FIT and _DEADLINE[0] and time.time() > _DEADLINE[0]:
        return []                                     # out of search time: this bay takes a NOMAD-placed flat, checked by the same rules
    if key not in _FIT:
        _FIT[key] = _furnished(t, W, D, target, mode, False)
    if _FIT[key] or not gen:
        return _FIT[key]
    gk = key + ("gen",)
    if gk not in _FIT and _DEADLINE[0] and time.time() > _DEADLINE[0]:
        return []
    if gk not in _FIT:
        _FIT[gk] = _furnished(t, W, D, target, mode, True)
    return _FIT[gk]


def _flat_ok(g, through):
    """The flat checks of _check that depend on the plan alone, before it is ranked: useful area, daylight depth of the
    living room and bedrooms, window share (1/8 of the floor)."""
    if sum(r["area"] for r in g["rooms"]) < USEFUL_MIN[0] - 1e-6:
        return False
    D = g["D"]
    for r in g["rooms"]:
        if r["kind"] not in ("living", "bed_main", "bed"):
            continue
        ls = _lit_share(r["pts"], D, through)
        if ls is not None and ls < LIT_SHARE - 1e-6:
            return False
        front = 0.0
        for a, b in zip(r["pts"], r["pts"][1:] + r["pts"][:1]):
            if (a[1] <= 0.3 and b[1] <= 0.3) or (through and a[1] >= D - 0.3 and b[1] >= D - 0.3):
                front += abs(b[0] - a[0])
        if layout.WINDOW_SHARE * front * layout.WINDOW_H / max(r["area"], 0.1) < 1.0 / 8.0:
            return False
    return True


def _furnished(t, W, D, target, mode, generate):
    lit, ent = MODES[mode]
    keep = []
    for g in F.iter_fits(library(), BEDS[t], W, D, lit=lit, entry_sides=ent, target_m2=target, generate=generate):
        if not _flat_ok(g, mode.startswith("through")):  # would fail the flat checks: let the next plan take the slot
            continue
        items, cs = U.furnish(g)                     # furnished and checked (7_floor_plans/code/furnish.py): wardrobe, bed, kitchen, bathroom
        if U.passes(cs):
            g["furniture"], g["checks_furn"] = items, cs
            keep.append(g)
            if len(keep) >= 3:
                break
    return keep


def widths_for(t, D, mode="hall"):
    key = ("w", t, round(D * 4), mode)
    if key not in _FIT:
        lit, ent = MODES[mode]
        _FIT[key] = F.natural_widths(library(), BEDS[t], D, lit=lit, entry_sides=ent)
    return _FIT[key]


# ---------- one flat ----------
def inside_shop(front, u0, W, D, tol=0.97):
    """The flat's rectangle lies inside the shop (at least 97 % of it)."""
    q = clip(front.local, (u0, 0.0, u0 + W, D))
    return len(q) >= 3 and area(q) >= tol * W * D


def _swing_line(x):
    """A door as architects draw it, in flat coordinates: hinge -> open leaf -> quarter arc -> other jamb."""
    x0, y0, x1, y1 = x["sweep"]
    w = x["w"]
    px, py = x["at"]
    if abs(py - y0) < 0.12 or abs(py - y1) < 0.12:          # the wall runs along x
        wy = y0 if abs(py - y0) < abs(py - y1) else y1
        d = 1.0 if wy == y0 else -1.0
        hinge, other = (x0, wy), (x1, wy)
        pts = [hinge] + [(x0 + w * math.sin(k * math.pi / 16), wy + d * w * math.cos(k * math.pi / 16)) for k in range(9)]
    else:                                                   # the wall runs along y
        wx = x0 if abs(px - x0) < abs(px - x1) else x1
        d = 1.0 if wx == x0 else -1.0
        hinge, other = (wx, y0), (wx, y1)
        pts = [hinge] + [(wx + d * w * math.cos(k * math.pi / 16), y0 + w * math.sin(k * math.pi / 16)) for k in range(9)]
    return [(round(q[0], 3), round(q[1], 3)) for q in pts]


def _unit(fr, u0, f, t, height, kind, back, alts=None):
    """A fitted library flat placed at u0 along a front -> a NOMAD unit with rooms in world coordinates and checks."""
    W, D = f["W"], f["D"]
    tw = lambda p: fr.to_world((u0 + p[0], p[1]))
    rooms, nb = [], 1
    for r in f["rooms"]:
        xs, ys = [p[0] for p in r["pts"]], [p[1] for p in r["pts"]]
        on_f, on_b = min(ys) <= 0.3, kind == "through" and max(ys) >= D - 0.3
        on = on_f or on_b
        front_len = 0.0
        for a, b in zip(r["pts"], r["pts"][1:] + r["pts"][:1]):
            if (on_f and a[1] <= 0.3 and b[1] <= 0.3) or (on_b and a[1] >= D - 0.3 and b[1] >= D - 0.3):
                front_len += abs(b[0] - a[0])
        name = NAMES.get(r["kind"], r["kind"])
        if r["kind"] == "bed":
            nb += 1
            name = "bedroom %d" % nb
        rooms.append({"name": name, "kind": r["kind"], "pts": [tw(p) for p in r["pts"]], "area": round(r["area"], 1),
                      "w": round(front_len if on else max(xs) - min(xs), 2), "d": round(max(ys) - min(ys), 2),
                      "clear": r["clear"], "on_facade": on, "via_patio": False,
                      "lit_share": _lit_share(r["pts"], D, kind == "through")})
    u = {"type": t, "outline": [tw(p) for p in ((0, 0), (W, 0), (W, D), (0, D))], "facade_w": round(W, 2), "depth": round(D, 2),
         "area_m2": round(sum(r["area"] for r in rooms), 1), "rooms": rooms, "kind": kind,
         "entry": {"through": "passage", "door": "own street door"}.get(kind, "shared hall"),
         "on_patio": back, "doors": [{"at": tw(d["at"]), "w": d["w"]} for d in f.get("doors", [])],
         "entrance": tw(f["entrance"]["at"]) if f.get("entrance") else None,
         "swings": [[tw(q) for q in _swing_line(x)] for x in f.get("swings", [])],
         "furniture": [{"kind": x["kind"], "law": x["law"], "pts": [tw(q) for q in ((x["rect"][0], x["rect"][1]), (x["rect"][2], x["rect"][1]),
                                                                                    (x["rect"][2], x["rect"][3]), (x["rect"][0], x["rect"][3]))]}
                       for x in f.get("furniture", [])],
         "lib": {"id": f["id"], "score": f["score"], "adaptivity": f["adaptivity"], "doors_widened": f.get("doors_widened", 0),
                 "mirrored": bool(f.get("mirrored")), "own_size": [f.get("W0"), f.get("D0")], "generated": bool(f.get("generated")),
                 "source": ("generated from " if f.get("generated") else "") + f.get("source", "Swiss Dwellings")},
         "room_scores": F.room_scores(f), "comfort": F.comfort(f), "matrix": F.matrix_items(f),
         "ducts": [[tw(q) for q in ((d["rect"][0], d["rect"][1]), (d["rect"][2], d["rect"][1]), (d["rect"][2], d["rect"][3]), (d["rect"][0], d["rect"][3]))] for d in F.ducts(f)]}
    _check(u, height, f)
    if alts is not None:
        _FLOOR.append([tuple(p) for p in u["outline"]])                                  # the gallery, built for the kept layouts only (_options)
        u["_alts"] = (fr, u0, list(alts), t, height, kind, back)
    return u


def _options(plan):
    """The gallery of each flat: this plan and the next best real plans for the same space."""
    for u in plan.get("units", []):
        a = u.pop("_alts", None)
        if a is not None:
            fr, u0, alts, t, height, kind, back = a
            u["options"] = [_option(u)] + [_option(_unit(fr, u0, g, t, height, kind, back)) for g in alts]
    return plan


def _option(u):
    return {"lib": u["lib"], "rooms": u["rooms"], "swings": u["swings"], "furniture": u["furniture"], "doors": u["doors"], "entrance": u["entrance"],
            "ok": u["ok"], "fails": u["fails"], "room_scores": u["room_scores"], "area_m2": u["area_m2"], "checks": u["checks"]}


def _check(u, height, f):
    """NOMAD's legal checks (layout.CITE), measured on the real rooms' shapes, + the library checks (plan graph, doors,
    turning circles, widths)."""
    out = []
    S = u["area_m2"]
    out.append(("useful", S >= USEFUL_MIN[0] - 1e-6, "%.1f m² useful (>= %d)" % (S, USEFUL_MIN[0])))
    beds = [r for r in u["rooms"] if r["kind"] in ("bed", "bed_main")]
    for r in beds:
        need = 2.6 if (r["kind"] == "bed_main" and len(beds) >= 3) else 2.0
        ok = r["area"] >= 6.0 and r["clear"] >= need
        r["ok"], r["why"] = ok, "" if ok else "%.1f m², %.2f m clear (needs 6 m² and a %.2f m square)" % (r["area"], r["clear"], need)
        out.append(("bedroom", ok, "%s %.1f m², %.2f m clear" % (r["name"], r["area"], r["clear"])))
    for r in u["rooms"]:
        if r["kind"] == "living":
            ok = r["clear"] >= 2.8
            r["ok"], r["why"] = ok, "" if ok else "narrower than the 2,80 m circle"
            out.append(("living", ok, "living %.2f m circle" % r["clear"]))
        if r["kind"] in ("living", "bed", "bed_main"):
            ratio = (layout.WINDOW_SHARE * r["w"] * layout.WINDOW_H) / max(r["area"], 0.1)
            ok = r["on_facade"] and ratio >= 1.0 / 8.0
            if not ok:
                r["ok"], r["why"] = False, "window only %.2f of the floor (needs 1/8)" % ratio
            out.append(("windows", ok, "%s window ratio %.2f" % (r["name"], ratio)))
        if r["kind"] == "living":
            out.append(("living_facade", r["on_facade"] and r["w"] >= 2.2, "living on the façade over %.2f m" % (r["w"] if r["on_facade"] else 0)))
        if r["kind"] == "hall":
            ok = r["clear"] >= 1.0
            if not ok:
                r["ok"], r["why"] = False, "hall %.2f m wide (needs 1 m)" % r["clear"]
            out.append(("hall", ok, "hall %.2f m wide" % r["clear"]))
    need_f = max(S / 9.0, 3.0)
    fac = u["facade_w"] * (2 if u["kind"] == "through" else 1)          # a through flat has its street and its block-interior façade
    out.append(("facade", fac >= need_f - 1e-6, "façade %.2f m (needs %.2f)" % (fac, need_f)))
    out.append(("height", height >= 2.4, "clear height %.2f m" % height))
    out.append(("wet_height", height >= 2.2, "bathroom, kitchen and hall height %.2f m" % height))
    out.append(("bath", any(r["kind"] == "bath" and r["area"] >= 2.5 for r in u["rooms"]), "bathroom present"))
    if LIT[0]:                                            # NOMAD liveability (not law): rooms mostly within the lit depth
        for r in u["rooms"]:
            if r["kind"] in ("living", "bed_main", "bed") and r.get("lit_share") is not None:
                ok = r["lit_share"] >= LIT_SHARE - 1e-6
                if not ok:
                    r["ok"], r["why"] = False, "only %d %% of it within %.1f m of the window (daylight)" % (100 * r["lit_share"], LIT[0])
                u.setdefault("_lit", []).append({"rule": "daylight", "ok": ok, "cite": LIT_CITE[0],
                    "text": "%s: %d %% of the floor within %.1f m of a window" % (r["name"], 100 * r["lit_share"], LIT[0])})
    for r in u["rooms"]:
        r.setdefault("ok", r["area"] > 0.5)
        r.setdefault("why", "")
    u["checks"] = [{"rule": k, "ok": ok, "text": txt, "cite": layout.CITE[k]} for k, ok, txt in out] + f.get("checks_lib", []) + f.get("checks_furn", []) + u.pop("_lit", [])
    u["checks"].append({"rule": "exterior", "ok": any(r["kind"] == "living" and r["on_facade"] for r in u["rooms"]),
                        "text": "living room on the %s" % ("block interior" if u["on_patio"] else "street"), "cite": CITE["exterior"]})
    if _OUTLINE:                                          # the same test as the Stage 5 card (flags.inside_card)
        out_pts = [q for r in u["rooms"] for q in r["pts"] if not _in_shop(q)]
        u["checks"].append({"rule": "inside", "ok": not out_pts, "cite": "NOMAD geometry check (not a law)",
                            "text": "every room inside the shop" if not out_pts else "a room crosses the shop outline"})
    u["ok"] = all(c["ok"] for c in u["checks"])
    u["fails"] = sorted(set(c["rule"] for c in u["checks"] if not c["ok"]))


def _in_shop(q, tol=0.15):
    poly = _OUTLINE
    if F.inside(q[0], q[1], poly):
        return True
    return any(F._seg_dist(q, poly[i], poly[(i + 1) % len(poly)]) <= tol for i in range(len(poly)))


# ---------- flats along one stretch of façade ----------
def _row(front, a, b, D, types, fill, need_depth, sizes, mode="hall"):
    """Real flats side by side between u=a and u=b, D deep. The types asked first (in order), then (fill) 1-beds and
    studios. Returns [(u0, W, type)] and the types that did not fit."""
    out, u, left = [], a, list(types)
    while True:
        pool = left + ([t for t in ("1bed", "studio") if t not in left] if fill else [])   # filling: smaller flats where the asked ones do not fit
        got = None
        deep_here = layout.depth_at(front.local, u, u + 3.0) >= need_depth - 0.05   # too shallow here: no width can work
        for t in (pool if deep_here else []):
            ws = widths_for(t, D, mode)
            if SMALL[0]:                                  # shared-space housing: real plans re-proportioned smaller (generated)
                ws = sorted(set(round(w * k * 4) / 4.0 for w in ws for k in (0.7, 0.8, 0.9, 1.0) if w * k >= 3.0))
            elif GAPS[0] and ws:                          # the gaps real plans leave: generated plans, narrower and wider, same checks
                ws = sorted(set(ws) | set(round(w * k * 4) / 4.0 for w in (ws[0], ws[-1]) for k in F.GAP_KS))
            for w in ws:
                if u + w > b + 1e-6:
                    break
                if layout.depth_at(front.local, u, u + w) < need_depth - 0.05:
                    break                                 # wider reaches no deeper: stop trying wider flats here
                if not inside_shop(front, u, w, need_depth) or not _free(front, u, u + w, need_depth):
                    continue
                if fits(t, w, D, sizes.get(t), mode, gen=SMALL[0] or GAPS[0]):
                    got = (t, w)
                    break
            if got:
                break
        if not got:
            if pool and u + 4.0 < b:                      # too shallow or too narrow here: try further along
                u += 0.5
                continue
            break
        t, w = got
        if t in left:
            left.remove(t)
        out.append([u, w, t])
        u += w
    if not out and pool and b - a >= 4.0:                 # no real plan fits this row: generated plans (fits gen=True)
        for t in pool:
            nat = widths_for(t, D, mode)
            if not nat:
                continue
            for k in (1, 2, 3):
                w = (b - a) / float(k)
                if not (min(nat) * F.GEN_STRETCH[0] <= w <= max(nat) * F.GEN_STRETCH[1]):
                    continue
                us = [a + i * w for i in range(k)]
                if all(layout.depth_at(front.local, x, x + w) >= need_depth - 0.05 and inside_shop(front, x, w, need_depth)
                       and _free(front, x, x + w, need_depth) for x in us) and fits(t, w, D, sizes.get(t), mode):
                    out = [[x, w, t] for x in us]
                    if t in left:
                        left.remove(t)
                    return out, left
    spare = b - u                                         # spread what is left over the flats (they stretch to it)
    if out and spare > 0.05:
        k = 0.0
        for s in out:
            add = min(spare / len(out), s[1] * (F.MAX_STRETCH[1] - 1.0) * 0.5)
            s[0] += k
            s[1] += add
            k += add
    return out, left


def _street_block(front, a, b, ul, LW, label, D, cw, left, fill, sizes, height, want, taken):
    """Flats on both sides of one street door: a lobby LW wide at ul and a hall behind the flats between a and b.
    A flat whose door is more than 25 m from the street door along the hall, or that overlaps what is already
    placed, is not placed."""
    fr, local = front.frame, front.local
    rows = []
    for pa, pb in sorted([(a, ul), (ul + LW, b)], key=lambda p: -(p[1] - p[0])):
        r, left = _row(front, pa, pb, D, left, fill, D + cw, sizes)
        rows += r
    units, kept = [], []
    for u0, w, t in rows:
        f = fits(t, w, D, sizes.get(t))
        u = _unit(fr, u0, f[0], t, height, "street", False, f[1:]) if f else None
        if u:
            door = fr.to_local(u["entrance"]) if u.get("entrance") else (u0 + w / 2.0, D)
            evac = D + cw / 2.0 + abs(door[0] - (ul + LW / 2.0)) + plan2.far_door(u)
            u["checks"].append({"rule": "evac", "ok": evac <= EVAC_MAX, "cite": plan2.CITE["evac"],
                                "text": "furthest room door %.1f m from the street door" % evac})
        if u and u["ok"] and evac <= EVAC_MAX and not any(plan2._overlap(fr, (u0, 0.0, u0 + w, D + cw), q) for q in taken):
            units.append(u)
            kept.append((u0, w))
        elif t in want:
            left.append(t)
    corridors = []
    if units:
        lo = min([u0 for u0, _ in kept] + [ul])
        hi = max([u0 + w for u0, w in kept] + [ul + LW])
        for rect, name in (((ul, 0.0, ul + LW, D + cw), label), ((lo, D, hi, D + cw), "shared hall")):
            q = clip(local, rect)
            if len(q) >= 3:
                corridors.append({"pts": [fr.to_world(p) for p in q], "width": round(min(rect[2] - rect[0], rect[3] - rect[1]), 2),
                                  "length": round(max(rect[2] - rect[0], rect[3] - rect[1]), 1), "name": name})
    return units, corridors, left


def build(outline, facade, street, height, mix, D=7.0, lobby_at=0.5, cw=1.2, fill=False, small_first=False,
          back_flats=True, sizes=None):
    _set_outline(outline)
    sizes = sizes or {}
    fronts = plan2._fronts(outline, facade, street)
    want = []
    for t in (plan2.ORDER[::-1] if small_first else plan2.ORDER):
        want += [t] * int(mix.get(t, 0) or 0)
    params = {"depth": D, "lobby_at": lobby_at, "corridor_w": cw, "fill": fill, "small_first": small_first, "back_flats": back_flats}
    if not fronts:
        return _plan(outline, [], [], want, want, params, [])
    main = fronts[0]
    fr, local = main.frame, main.local
    s0, s1 = max(main.spans, key=lambda s: s[1] - s[0])
    LW, portal = LOBBY, None
    for q in _EXISTING:                                   # the building's portal on the street: the flats' entrance
        ql = [fr.to_local(p) for p in q]
        if min(p[1] for p in ql) <= 0.6 and s0 - 0.5 <= min(p[0] for p in ql) and max(p[0] for p in ql) <= s1 + 0.5:
            portal = (max(s0, min(p[0] for p in ql)), min(s1, max(p[0] for p in ql)))
            break
    if portal:
        ul, LW = portal[0], max(portal[1] - portal[0], 1.2)
        params["portal"] = True
    else:
        ul = s0 + lobby_at * max(0.0, s1 - s0 - LOBBY)
    left = list(want)
    units, corridors, notes = [], [], []
    # every street façade gets street doors: one lobby per stretch of up to SEG m, so every flat door is within 25 m
    for k_, sf in enumerate([main] + [f for f in fronts[1:] if f.public]):
        for a, b in sorted(sf.spans, key=lambda x: -(x[1] - x[0])):
            n = max(1, int(math.ceil((b - a) / SEG)))
            for i in range(n):
                sa, sb = a + (b - a) * i / n, a + (b - a) * (i + 1) / n
                if sb - sa < LOBBY + 4.0:
                    continue
                if sf is main and i == 0 and portal:
                    u_l, w_l, lab = ul, LW, "the building's portal"
                elif sf is main and i == 0:
                    u_l, w_l, lab = sa + lobby_at * max(0.0, sb - sa - LOBBY), LOBBY, "lobby"
                else:
                    u_l, w_l, lab = sa + 0.5 * max(0.0, sb - sa - LOBBY), LOBBY, "lobby %d" % (len([c for c in corridors if c["name"].startswith("lobby")]) + 1)
                    if not _free(sf, u_l, u_l + w_l, D + cw):
                        continue
                us, cs, left = _street_block(sf, sa, sb, u_l, w_l, lab, D, cw, left, fill, sizes, height, want,
                                             [u["outline"] for u in units] + [c["pts"] for c in corridors])
                units += us
                corridors += cs
                if sf is main and i == 0:
                    ul = u_l
    # flats along the other façades (a long side onto the block interior), each row off a hall behind it that runs to a
    # street door; every flat door within 25 m of it (CTE DB-SI SI 3)
    back = [f for f in fronts[1:] if not f.public and plan2._is_back(main, f)]
    for sf in [f for f in fronts[1:] if f not in back and not f.public]:
        for a, b in sf.spans:
            if b - a < 4.0:
                continue
            srows, left = _row(sf, a, b, D, left, fill, D + cw, sizes)
            if not srows:
                continue
            ends = [(a, sf.frame.to_world((a, D + cw / 2.0))), (b, sf.frame.to_world((b, D + cw / 2.0)))]
            ue, pe = min(ends, key=lambda e: fr.to_local(e[1])[1])            # the hall's end nearest the street
            reach = fr.to_local(pe)[1]
            if reach > (D + cw if units else 0.0) + 2.0:                       # it does not reach the street or the main hall
                for _, _, t in srows:
                    if t in want:
                        left.append(t)
                continue
            taken = [u["outline"] for u in units] + [c["pts"] for c in corridors]
            sunits = []
            for u0, w, t in srows:
                f = fits(t, w, D, sizes.get(t))
                u = _unit(sf.frame, u0, f[0], t, height, "side", not sf.public, f[1:]) if f else None
                if u:
                    door = u["entrance"] or sf.frame.to_world((u0 + w / 2.0, D))
                    evac = max(reach, 0.0) + abs(sf.frame.to_local(door)[0] - ue) + plan2.far_door(u)
                    ok = evac <= EVAC_MAX
                    u["checks"].append({"rule": "evac", "ok": ok, "cite": plan2.CITE["evac"],
                                        "text": "furthest room door %.1f m from the street door" % evac})
                    if not ok:
                        u["ok"] = False
                        u["fails"].append("evac")
                if u and u["ok"] and not any(plan2._overlap(sf.frame, (u0, 0.0, u0 + w, D + cw), q) for q in taken):
                    sunits.append(u)
                elif t in want:
                    left.append(t)
            if sunits:
                units += sunits
                xs = [sf.frame.to_local(p)[0] for u in sunits for p in u["outline"]] + [ue]
                q = clip(sf.local, (min(xs), D, max(xs), D + cw))
                if len(q) >= 3:
                    corridors.append({"pts": [sf.frame.to_world(p) for p in q], "width": cw, "length": round(max(xs) - min(xs), 1),
                                      "name": "hall along the side"})
    # block-interior flats: a spine from the lobby to a gallery along them
    if back_flats and back and units:
        bf = back[0]
        bf.back = True
        Y = min(fr.to_local(p)[1] for a, b in bf.spans for p in (bf.frame.to_world((a, D + cw)), bf.frame.to_world((b, D + cw))))
        if Y > D + cw + 0.5:
            spine_u = (ul, ul + LOBBY)
            brows = []
            for a, b in bf.spans:
                ca = bf.frame.to_local(fr.to_world((spine_u[0], Y)))[0]
                cb = bf.frame.to_local(fr.to_world((spine_u[1], Y)))[0]
                cut = (min(ca, cb), max(ca, cb))
                for pa, pb in ((a, min(b, cut[0])), (max(a, cut[1]), b)):
                    if pb - pa >= 4.0:
                        r, left = _row(bf, pa, pb, D, left, fill, D + cw, sizes)
                        brows += r
            bunits = []
            for u0, w, t in brows:
                f = fits(t, w, D, sizes.get(t))
                if not f:
                    continue
                u = _unit(bf.frame, u0, f[0], t, height, "back", True, f[1:])
                door = u["entrance"] or bf.frame.to_world((u0 + w / 2.0, D))
                dl = fr.to_local(door)
                evac = Y + abs(dl[0] - (ul + LOBBY / 2.0)) + plan2.far_door(u)
                ok = evac <= EVAC_MAX
                u["checks"].append({"rule": "evac", "ok": ok, "cite": plan2.CITE["evac"],
                                    "text": "furthest room door %.1f m from the street door" % evac})
                u["ok"] = u["ok"] and ok
                if not ok:
                    u["fails"].append("evac")
                placed = [q["outline"] for q in units] + [c["pts"] for c in corridors]
                if ok and not any(plan2._overlap(bf.frame, (u0, 0.0, u0 + w, D + cw), q) for q in placed):
                    bunits.append(u)
                elif t in want:
                    left.append(t)
            if bunits:
                units += bunits
                q = clip(local, (ul, D + cw, ul + LOBBY, Y))
                if len(q) >= 3:
                    corridors.append({"pts": [fr.to_world(p) for p in q], "width": LOBBY, "length": round(Y - D - cw, 1), "name": "spine"})
                xs = [bf.frame.to_local(p)[0] for u in bunits for p in u["outline"]] + [bf.frame.to_local(fr.to_world((ul, Y)))[0],
                                                                                          bf.frame.to_local(fr.to_world((ul + LOBBY, Y)))[0]]
                q = clip(bf.local, (min(xs), D, max(xs), D + cw))
                if len(q) >= 3:
                    corridors.append({"pts": [bf.frame.to_world(p) for p in q], "width": cw, "length": round(max(xs) - min(xs), 1), "name": "gallery"})
    return _plan(outline, units, corridors, left, want, params, notes)


def build_through(outline, facade, street, height, mix, la=0.0, fill=False, small_first=False, sizes=None, kind="through"):
    """Through flats (street + block interior, the Eixample "pis passant") in pairs, each pair entered from a passage
    between them that runs from a street door to the block-interior façade."""
    _set_outline(outline)
    sizes = sizes or {}
    fronts = plan2._fronts(outline, facade, street)
    want = []
    for t in (plan2.ORDER[::-1] if small_first else plan2.ORDER):
        want += [t] * int(mix.get(t, 0) or 0)
    params = {"layout": kind, "lobby_at": la, "fill": fill, "small_first": small_first, "corridor_w": LOBBY}
    ml, mr = ("through_l", "through_r") if kind == "through" else ("side_l", "side_r")
    if not fronts:
        return _plan(outline, [], [], want, want, params, [])
    main = fronts[0]
    back = [f for f in fronts[1:] if not f.public and plan2._is_back(main, f)]
    if kind == "through" and not back:
        return _plan(outline, [], [], want, want, params, ["no block-interior façade across the shop"])
    fr, local = main.frame, main.local
    s0, s1 = max(main.spans, key=lambda s: s[1] - s[0])
    left, units, corridors = list(want), [], []
    u = s0 + la * min(4.0, max(0.0, (s1 - s0) % 20.0))
    while u < s1 - 6.0:
        pool = left if left else (["2bed", "1bed"] if fill else [])
        placed = None
        for t1 in pool:
            D = layout.depth_at(local, u, min(s1, u + 20.0))
            if D < 6.0:
                break
            Df = D if kind == "through" else min(D, 9.0)          # a one-sided flat takes only the front of a deep shop
            ws1 = [w for w in widths_for(t1, Df, ml) if u + w + LOBBY <= s1 + 1e-6 and inside_shop(main, u, w, Df)
                   and _free(main, u, u + w + LOBBY, Df)]
            f1 = next(((w, fits(t1, w, Df, sizes.get(t1), ml)) for w in ws1 if fits(t1, w, Df, sizes.get(t1), ml, gen=False)), None)
            if not f1:
                continue
            p0 = u + f1[0]
            f2, t2 = None, None
            for t in pool:
                ws2 = [w for w in widths_for(t, Df, mr) if p0 + LOBBY + w <= s1 + 1e-6 and inside_shop(main, p0 + LOBBY, w, Df)
                       and _free(main, p0 + LOBBY, p0 + LOBBY + w, Df)]
                f2 = next(((w, fits(t, w, Df, sizes.get(t), mr)) for w in ws2 if fits(t, w, Df, sizes.get(t), mr, gen=False)), None)
                if f2:
                    t2 = t
                    break
            placed = (t1, f1, t2, f2, Df, p0)
            break
        if not placed:
            break
        t1, f1, t2, f2, D, p0 = placed
        for t in (t1, t2):
            if t and t in left:
                left.remove(t)
        uk = "through" if kind == "through" else "street"
        units.append(_unit(fr, u, f1[1][0], t1, height, uk, False, f1[1][1:]))
        if f2:
            units.append(_unit(fr, p0 + LOBBY, f2[1][0], t2, height, uk, False, f2[1][1:]))
        q = clip(local, (p0, 0.0, p0 + LOBBY, D))
        if len(q) >= 3:
            corridors.append({"pts": [fr.to_world(p) for p in q], "width": LOBBY, "length": round(D, 1), "name": "passage"})
        u = p0 + LOBBY + (f2[0] if f2 else 0.0)
    return _plan(outline, units, corridors, left, want, params, [])


def _passage(f, a, b, corridors):
    """Deep floor behind the flats gets a way in: a lobby taken from the end of the longest street span."""
    if max(p[1] for p in f.local) > 12.0 and b - a > LOBBY + 6.0:
        b -= LOBBY
        q = clip(f.local, (b, 0.0, b + LOBBY, 9.0))
        if len(q) >= 3:
            corridors.append({"pts": [f.frame.to_world(p) for p in q], "width": LOBBY, "length": 9.0, "name": "lobby"})
            _FLOOR.append([tuple(f.frame.to_world(c)) for c in ((b, 0.0), (b + LOBBY, 0.0), (b + LOBBY, 9.0), (b, 9.0))])
    return b


def build_doors(outline, facade, street, height, mix, D=7.0, fill=False, small_first=False, sizes=None):
    """Flats side by side along the street, each with its own street door: no lobby and no shared hall, so a shop too
    shallow for a hall behind the flats can still hold homes."""
    _set_outline(outline)
    sizes = sizes or {}
    fronts = [f for f in plan2._fronts(outline, facade, street) if f.public]
    want = []
    for t in (plan2.ORDER[::-1] if small_first else plan2.ORDER):
        want += [t] * int(mix.get(t, 0) or 0)
    left, units, corridors = list(want), [], []
    fronts = sorted(fronts, key=lambda f: -max(b - a for a, b in f.spans))
    main = max(fronts[0].spans, key=lambda q: q[1] - q[0]) if fronts else None
    for f in fronts:
        for a, b in sorted(f.spans, key=lambda q: q[0] - q[1]):
            if f is fronts[0] and (a, b) == main:
                b = _passage(f, a, b, corridors)
            row, left = _row(f, a, b, D, left, fill, D, sizes, "door")
            for u0, w, t in row:
                gs = fits(t, w, D, sizes.get(t), "door")
                if gs:
                    units.append(_unit(f.frame, u0, gs[0], t, height, "door", False, gs[1:]))
    params = {"layout": "doors", "D": D, "fill": fill, "small_first": small_first, "corridor_w": 0}
    return _plan(outline, units, corridors, left, want, params, [])


# ---------- cut the real outline: flats that follow the building, not boxes ----------
REACH = 9.0                      # a flat lit from one facade cannot go deeper: Decret 141/2012 Annex 1 3.6.2 (facade >= S/9)
MIN_W = {"studio": 4.85, "1bed": 7.25, "2bed": 10.0, "3bed": 12.75}   # living room | hall | bedrooms across the facade
SERVICE = ("quiet work alcove, task lighting", "bike storage", "shared laundry", "tenant lockers")     # the biggest piece first; these uses need no daylight (design choice)
LEAF_MIN, SERVICE_W, RISER_M2 = 0.05, 1.20, 1.5   # no sliver is left out; the service corridor (CTE DB-SUA Anejo A: accessible route >= 1,20 m); under 1,5 m2 a piece serves as a riser (design choice)


def _shift(poly, u0):
    return [[round(x - u0, 3), round(y, 3)] for x, y in poly]


def _near_room(p, r, d=0.3):
    return F.inside(p[0], p[1], r["pts"]) or any(F._seg_dist(p, a, b) <= d for a, b in zip(r["pts"], r["pts"][1:] + r["pts"][:1]))


def _split(q):
    """True when clipping left a room in two pieces: two of its edges run back over each other along the clip line."""
    E = [(q[i], q[(i + 1) % len(q)]) for i in range(len(q))]
    for k in (0, 1):
        for i, (a, b) in enumerate(E):
            for c, d in E[i + 2:]:
                if abs(a[k] - b[k]) < 1e-6 and abs(c[k] - d[k]) < 1e-6 and abs(a[k] - c[k]) < 1e-6:
                    lo, hi = max(min(a[1 - k], b[1 - k]), min(c[1 - k], d[1 - k])), min(max(a[1 - k], b[1 - k]), max(c[1 - k], d[1 - k]))
                    if hi - lo > 0.02:
                        return True
    return False


def _cut_flat(t, cell, W, D, ident, flip=False, pair=None, ys=None):
    """The best legal flat for this piece of floor (cell: its real shape, flat coordinates): the room placer's rooms, cut by the cell's own walls."""
    key = (t, tuple(tuple(round(c * 4) for c in p) for p in cell), round(W * 4), round(D * 4), flip, pair, ys)
    if key in _FIT:
        return _FIT[key]
    best = None
    rectangular = area(cell) >= 0.985 * W * D
    if rectangular and pair is None:                       # the plan library first: a real plan, morphed to this bay and checked
        for g in fits(t, W, D, None, "door", False) or []:
            _FIT[key] = dict(g, score=g.get("score", 60))
            return _FIT[key]
    for Yb in (ys,) if ys else (2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0, 4.2, 4.4, 4.6, 4.8):
        for dd in (D, D - 0.5, D - 1.0):
            if dd < 5.5:
                continue
            f0 = F.place_flat(BEDS[t], W, round(dd, 2), Yb, "%s-%d" % (ident, int(Yb * 10)), street=True, fit=True, pair=pair)
            if not f0:
                continue
            for f in (((F.mirror(f0),) if flip else (f0,)) if pair is not None else ((F.mirror(f0), f0) if flip else (f0, F.mirror(f0)))):      # neighbours are mirrored across their party wall
                g = dict(f); rooms = []; ok = True
                for r in f["rooms"]:
                    xs, ys = [q[0] for q in r["pts"]], [q[1] for q in r["pts"]]
                    q = clip([tuple(p) for p in cell], (min(xs), min(ys), max(xs), max(ys)))     # the room, cut by the walls of this cell
                    if len(r["pts"]) > 4:                  # an L or T hall keeps its own shape: it must stand whole inside the cell
                        if abs(area(q) - (max(xs) - min(xs)) * (max(ys) - min(ys))) > 0.01:
                            ok = False; break
                        rooms.append(dict(r)); continue
                    if len(q) < 3 or _split(q):
                        ok = False; break
                    a0, a1 = F.poly_area(r["pts"]), F.poly_area(q)
                    if a1 < 0.6 * a0 or a1 < 1.0:
                        ok = False; break
                    pts = [[round(x, 3), round(y, 3)] for x, y in q]
                    rooms.append(dict(r, pts=pts, area=round(a1, 2), clear=round(F.clear_width(pts), 2)))
                if not ok:
                    continue
                g["rooms"] = rooms
                if any(not _near_room(d["at"], rooms[e[0]]) or not _near_room(d["at"], rooms[e[1]]) for d, e in zip(g["doors"], [x for x in g["edges"] if x[2] > 0])):
                    continue
                g["useful"] = round(sum(r["area"] for r in rooms), 1)
                if not _flat_ok(g, False):
                    continue
                cs = F.checks(g)
                if not all(c["ok"] for c in cs):
                    continue
                items, fc = U.furnish(g)
                if not U.passes(fc):
                    continue
                g["furniture"], g["checks_furn"], g["checks_lib"], g["swings"] = items, fc, cs, F.swings(g)
                g["score"] = round(60 + 40 * F.graph_score(g), 1); g["adaptivity"] = 0.0; g["source"] = "NOMAD cut to the building"
                rank = (f is not f0 if flip else f is f0, -round(F.share_gap(g), 1), g["useful"], g["score"])   # step 3: rooms as near the brief's shares as the law allows
                if best is None or rank > best[0]:
                    best = (rank, g)
    _FIT[key] = best[1] if best else None
    return _FIT[key]


def _cell(front, u0, u1):
    """The floor of a street front between u0 and u1, up to 9 m deep, as the walls really run."""
    q = clip(front.local, (u0, 0.0, u1, REACH))
    return q if len(q) >= 3 else None


def _bisect(q, a, b, shares):
    """Binary space partition of a stretch of the 9 m band: each cut in proportion to the flats on either side, until every flat has its cell."""
    if len(q) < 3:
        return []
    if len(shares) <= 1:
        return [(a, b, q)]
    h, y1 = len(shares) // 2, max(p[1] for p in q) + 1.0
    m = a + (b - a) * sum(shares[:h]) / float(sum(shares))
    return _bisect(clip(q, (a - 1.0, -1.0, m, y1)), a, m, shares[:h]) + _bisect(clip(q, (m, -1.0, b + 1.0, y1)), m, b, shares[h:])


PAIR_W = {"studio": 4.0, "1bed": 6.45, "2bed": 11.4, "3bed": 14.15}   # living room | closet bank | bedrooms, before the lobby's half width
LOBBY_MIN = 2.10                 # two foyer doors of 0,90 m side by side in the lobby's end wall, either side of the party wall
CORE_SHARE, LOBBY_SHARE = 0.05, 0.10   # the cascade's step 1: ~5 % of the floor for cores, ~10 % for the shared lobby (v4.0 brief)
UNIT_SHARE = {"studio": 30.0, "1bed": 25.0, "2bed": 35.0, "3bed": 45.0}   # step 2: the brief's shares; it gives none for a 2-bed, 35 lies between (our choice)


def _shares(seq):
    """Step 2: each flat's share of the street front. A type's share is split among its flats, and no flat goes under its minimum width."""
    n = dict((t, seq.count(t)) for t in seq)
    return [UNIT_SHARE[t] / n[t] for t in seq]


def _fit_shares(seq, span):
    w = _shares(seq)
    tot = sum(w) or 1.0
    out = [max(MIN_W[t], span * x / tot) for t, x in zip(seq, w)]
    over = sum(out) - span
    if over > 0:
        room = [max(0.0, x - MIN_W[t]) for t, x in zip(seq, out)]
        k = over / (sum(room) or 1.0)
        out = [x - r * k for x, r in zip(out, room)]
    return out


def _fit_widths(seq, span, least):
    """Step 2 with each flat's own minimum width."""
    w = _shares(seq)
    tot = sum(w) or 1.0
    out = [max(m, span * x / tot) for m, x in zip(least, w)]
    over = sum(out) - span
    if over > 0:
        room = [x - m for m, x in zip(least, out)]
        k = over / (sum(room) or 1.0)
        out = [x - r * k for x, r in zip(out, room)]
    return out


def _cut_span(front, a, b, want, fill, height, sizes, kept):
    """Cut a span of a street front into flats, end to end. Tries each number of flats and keeps the one with the most homes, then the most floor."""
    best = (0, 0.0, [], list(want))
    line = [None]                                          # flats along a front keep one back wall line, for the structure
    for k in range(int((b - a) // MIN_W["studio"]), 0, -1):
        seq = list(want)[:k]                              # no fixed sizes: the whole street front is shared out in proportion to the flats
        while len(seq) < k:
            seq.append("studio" if not fill or len(seq) % 2 else "1bed")
        if sum(MIN_W[t] for t in seq) > b - a:
            continue
        cells, left, units = [], list(want), []
        for i, (u0, u1, q) in enumerate(_bisect(_cell(front, a, b) or [], a, b, _fit_shares(seq, b - a))):
            w = u1 - u0
            D = min(REACH, max(p[1] for p in q))
            if D < 5.5 or _taken([tuple(front.frame.to_world(c)) for c in ((u0, 0.0), (u1, 0.0), (u1, D), (u0, D))]):
                continue
            pool = [seq[i]] + [t for t in plan2.ORDER if t in left and w >= MIN_W[t]] + ([t for t in ("1bed", "studio") if w >= MIN_W[t]] if fill else [])
            for t in pool:
                g = _cut_flat(t, [tuple(p) for p in _shift(q, u0)], w, D, "cut-%s-%g" % (t, round(w, 1)), bool(i % 2), None, line[0]) or \
                    _cut_flat(t, [tuple(p) for p in _shift(q, u0)], w, D, "cut-%s-%g" % (t, round(w, 1)), bool(i % 2))
                if g:
                    if t in left:
                        left.remove(t)
                    line[0] = line[0] or g.get("Yb")
                    units.append((u0, g, t))
                    break
        area_ = sum(g["useful"] for _, g, _ in units)
        if (len(units), area_) > best[:2]:
            best = (len(units), area_, units, left)
    return best[2], best[3]


def _hull(q):
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in q))
    if len(pts) < 3:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for c in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], c) <= 0:
            lo.pop()
        lo.append(c)
    for c in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], c) <= 0:
            up.pop()
        up.append(c)
    return lo[:-1] + up[:-1]


LOBBY_MAX = 4.0                  # a lobby this wide already has room for every shared use (design choice)
LOBBY_USES = ("parcel lockers", "quiet work alcove", "coat and shoe bank")   # a lobby wider than 1,20 m is a place, not just a way through (v3.5 brief)
ROOM_MAX = 40.0                  # a shared room is cut in two above this (design choice): a very deep shop gets rooms, not one hall


def _bsp(q, solids, depth=0):
    """Binary space partition of the floor no home uses: cut along the edges of what stands in it, until each piece is free."""
    if len(q) < 3 or area(q) < LEAF_MIN:
        return []
    hits = [s for s in solids if _shared(q, s) > 0.02]
    if not hits and area(q) <= ROOM_MAX:
        return [q]
    if depth > 16:
        return []
    xs, ys = [p[0] for p in q], [p[1] for p in q]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cuts = [("y", p[1]) for s in hits for p in s if y0 + 0.2 < p[1] < y1 - 0.2] + [("x", p[0]) for s in hits for p in s if x0 + 0.2 < p[0] < x1 - 0.2]
    if cuts and hits:
        k, c = min(cuts, key=lambda t: abs(t[1] - ((y0 + y1) / 2.0 if t[0] == "y" else (x0 + x1) / 2.0)))
    else:
        k, c = ("x", (x0 + x1) / 2.0) if x1 - x0 >= y1 - y0 else ("y", (y0 + y1) / 2.0)
    a, b = ((x0 - 1, y0 - 1, c, y1 + 1), (c, y0 - 1, x1 + 1, y1 + 1)) if k == "x" else ((x0 - 1, y0 - 1, x1 + 1, c), (x0 - 1, c, x1 + 1, y1 + 1))
    return _bsp(clip(q, a), solids, depth + 1) + _bsp(clip(q, b), solids, depth + 1)


def _middle(p, outline, facade, street):
    """All of the property accounted for: the floor no home uses is partitioned and named, and a corridor beyond the flats
    joins the deep rooms to the lobby or the street."""
    total, homes = area([tuple(q) for q in outline]), sum(u.get("area_m2", 0.0) for u in p.get("units", []))
    p["floor"] = {"total": round(total, 1), "homes": round(homes, 1), "shared": round(max(0.0, total - homes), 1), "coverage": None}
    fronts = sorted([f for f in plan2._fronts(outline, facade, street) if f.public], key=lambda f: -max(b - a for a, b in f.spans))
    pieces = []
    if fronts:
        fr = fronts[0]
        loc = lambda x: _hull([fr.frame.to_local(c) for c in x])
        shapes = [loc(u["outline"]) for u in p.get("units", [])] + [loc(c["pts"]) for c in p.get("corridors", [])] + [loc(c if isinstance(c, list) else c["pts"]) for c in p.get("cores", [])] +             [loc(c if isinstance(c, list) else c["pts"]) for c in p.get("patios", [])] + [loc(c) for c in _EXISTING]
        solids = [s for s in shapes if len(s) >= 3]
        for x in [c["pts"] for c in p.get("corridors", [])]:
            if len(x) > 4:
                q = [fr.frame.to_local(c) for c in x]
                solids.remove(_hull(q))
                u, u1 = min(c[0] for c in q), max(c[0] for c in q)
                while u < u1:
                    t = clip(q, (u, -1e6, u + 1.0, 1e6))
                    if len(t) >= 3:
                        solids.append(_hull(t))
                    u += 1.0
        top = max(q[1] for q in fr.local)
        y0 = max([c[1] for s in solids for c in s if c[1] <= REACH + 0.5] or [0.0])
        if solids and top - y0 >= 3.0:                     # the service corridor, first, then the rooms off it
            q = clip(fr.local, (min(c[0] for c in fr.local), y0, max(c[0] for c in fr.local), y0 + SERVICE_W))
            if len(q) >= 3:
                pieces.append({"pts": [list(fr.frame.to_world(c)) for c in q], "area": round(area(q), 1), "name": "service corridor"})
                x0, x1 = min(c[0] for c in q), max(c[0] for c in q)
                solids = solids + [[(x0, y0), (x1, y0), (x1, y0 + SERVICE_W), (x0, y0 + SERVICE_W)]]
        leaves = sorted(_bsp([tuple(c) for c in fr.local], solids), key=lambda x: -area(x))
        pieces += [{"pts": [list(fr.frame.to_world(c)) for c in q], "area": round(area(q), 1)} for q in leaves]
    _rooms_for(p, pieces, street or facade)
    p["shared_spaces"] = pieces
    halls = sum(area([tuple(c) for c in x["pts"]]) for x in p.get("corridors", [])) + sum(x["area"] for x in pieces if x.get("name") == "service corridor")
    p["floor"]["lobby_pct"] = round(100.0 * halls / total, 1) if total else 0.0
    p["lobby_uses"] = list(LOBBY_USES) if any(x.get("width", 0) > 1.20 for x in p.get("corridors", [])) else []
    for c in p.get("corridors", []):                      # what is wider than the 1,20 m walking line becomes active shared use
        q = [tuple(x) for x in c["pts"]]
        if str(c.get("name", "")).startswith("lobby") and c.get("width", 0) > 1.20 and len(q) == 4:
            a, b, d = q[0], q[1], q[3]
            la, lb = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5, ((d[0] - a[0]) ** 2 + (d[1] - a[1]) ** 2) ** 0.5
            (s0, e0), (lng, n) = ((b, a), (d, lb)) if la < lb else ((d, a), (b, la))
            short = (s0[0] - e0[0], s0[1] - e0[1])
            sl = min(la, lb)
            if sl <= 1.20:                                # a lobby clipped by the outline to nothing wider than the walking line
                continue
            f0 = max(0.0, 1.0 - (sl - 1.20) / sl)
            for i, name in enumerate(LOBBY_USES):
                t0, t1 = i / 3.0, (i + 1) / 3.0
                along = lambda t: (a[0] + (lng[0] - a[0]) * t, a[1] + (lng[1] - a[1]) * t)
                u, v = along(t0), along(t1)
                z = [[u[0] + short[0] * f0, u[1] + short[1] * f0], [u[0] + short[0], u[1] + short[1]], [v[0] + short[0], v[1] + short[1]], [v[0] + short[0] * f0, v[1] + short[1] * f0]]
                pieces.append({"pts": z, "area": round((sl - 1.20) * n / 3.0, 1), "name": name, "access": "shared"})
    infra = sum(area([tuple(k) for k in (x if isinstance(x, list) else x["pts"])]) for x in p.get("cores", [])) + sum(x["area"] for x in pieces if x.get("name") == "service riser")
    p["floor"]["infrastructure"] = round(infra, 1)
    p["floor"]["amenities"] = round(max(0.0, total - homes - infra), 1)
    p["cascade"] = {"gross": round(total, 1), "core_target": round(CORE_SHARE * total, 1), "lobby_target": round(LOBBY_SHARE * total, 1), "net": round((1.0 - CORE_SHARE - LOBBY_SHARE) * total, 1)}
    p["dead_m2"] = round(sum(x["area"] for x in pieces if x["access"] is None), 1)
    lines = list(street or []) + list(facade or [])
    near_line = lambda a, b: any(_pt_seg(a, c, d) <= 0.3 or _pt_seg(b, c, d) <= 0.3 for c, d in lines)
    poly = [tuple(c) for c in outline]
    poly = poly[:-1] if poly[0] == poly[-1] else poly
    p["fire_walls"] = [{"a": list(a), "b": list(b), "rating": "EI 120", "kind": "wall to the next building", "cite": FIRE_CITE["party"]}
                       for a, b in zip(poly, poly[1:] + poly[:1]) if not near_line(((a[0] * 2 + b[0]) / 3.0, (a[1] * 2 + b[1]) / 3.0), ((a[0] + b[0] * 2) / 3.0, (a[1] + b[1] * 2) / 3.0))]
    us = [u["comfort"] for u in p.get("units", []) if "comfort" in u]
    p["comfort"] = round(sum(us) / float(len(us))) if us else None
    return p


FIRE_CITE = {"party": "CTE DB-SI SI 2 1.1 (walls to another building at least EI 120)"}


def _close(a, b, d=0.3):
    es = lambda q: list(zip(q, q[1:] + q[:1]))
    return any(_pt_seg(c, x, y) <= d for c in a for x, y in es(b)) or any(_pt_seg(c, x, y) <= d for c in b for x, y in es(a))


def _rooms_for(p, pieces, street):
    """Every piece of floor gets a use it can really have, starting from how you reach it: from a shared hall or the street it is a
    shared room; beside a flat and nowhere else it becomes that flat's store; a piece too small for a room is a riser.
    Only a piece with no neighbour left is dead, and that is reported and costs the layout points."""
    halls = [[tuple(c) for c in x["pts"]] for x in p.get("corridors", [])] + [[tuple(c) for c in (x if isinstance(x, list) else x["pts"])] for x in p.get("cores", [])]
    Q = [[tuple(c) for c in x["pts"]] for x in pieces]
    seen, todo = set(), [i for i, q in enumerate(Q) if any(_close(q, h) for h in halls) or any(_close(q, [tuple(a), tuple(b)]) for a, b in street)]
    while todo:
        i = todo.pop()
        if i not in seen:
            seen.add(i)
            todo += [j for j, q in enumerate(Q) if j not in seen and _close(Q[i], q)]
    units = [[tuple(c) for c in u["outline"]] for u in p.get("units", [])]
    left = list(SERVICE[:3])
    for i, x in sorted(enumerate(pieces), key=lambda t: -t[1]["area"]):
        if x.get("name") == "service corridor":
            x["access"] = "shared" if i in seen else None
        elif i in seen:
            x["access"] = "shared"
            x["name"] = left.pop(0) if left and x["area"] >= 8.0 else "tenant lockers" if x["area"] >= RISER_M2 else "service riser"
        elif x["area"] < RISER_M2:
            x["name"], x["access"] = "service riser", "riser"
        else:
            own = [k for k, q in enumerate(units) if _close(Q[i], q)]
            x["name"], x["access"] = ("walk-in closet or pantry for home %d" % (own[0] + 1), "flat") if own else ("dead: no way in", None)


def _aspect(a, b, outline):
    """Which way a stretch of facade looks: N, E, S or W. Coordinates are UTM, y to the north."""
    cx, cy = sum(c[0] for c in outline) / float(len(outline)), sum(c[1] for c in outline) / float(len(outline))
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    nx, ny = b[1] - a[1], a[0] - b[0]
    if nx * (mx - cx) + ny * (my - cy) < 0:
        nx, ny = -nx, -ny
    az = math.degrees(math.atan2(nx, ny)) % 360.0
    return "N" if az >= 315 or az < 45 else "E" if az < 135 else "S" if az < 225 else "W"


def _solar(p, outline, facade, street):
    """Solar and Daylight Autonomy, 0-100, our own score, not law. Zone I: facades looking south, east or west, for living rooms and kitchens.
    Zone II: north facades, for bedrooms. Zone III: everything beyond the daylight, which must have a use.
    40 points: living rooms and bedrooms with at least half their floor in the lit depth. 30: rooms on the facade that suits them. 30: dark floor in use."""
    lines = [(a, b) for a, b in list(street or []) + list(facade or [])]
    fronts = [{"a": list(a), "b": list(b), "aspect": _aspect(a, b, outline)} for a, b in lines]
    for x in fronts:
        x["zone"] = "II" if x["aspect"] == "N" else "I"
    rooms = [r for u in p.get("units", []) if u.get("ok") for r in u["rooms"] if r["kind"] in ("living", "bed", "bed_main", "kitchen")]
    near, suit, lit = 0, 0, 0
    for r in rooms:
        c = (sum(q[0] for q in r["pts"]) / len(r["pts"]), sum(q[1] for q in r["pts"]) / len(r["pts"]))
        f = min(fronts, key=lambda x: _pt_seg(c, x["a"], x["b"])) if fronts else None
        z = "I" if r["kind"] in ("living", "kitchen") else "II"
        if f:
            suit += f["zone"] == z
        if r["kind"] != "kitchen":
            near += 1
            lit += r.get("lit_share", 0.0) >= LIT_SHARE
    deep = (p.get("score") or {}).get("deep_pct", 100.0)
    a = 40.0 * lit / near if near else 0.0
    b = 30.0 * suit / len(rooms) if rooms else 0.0
    return {"score": round(a + b + 30.0 * deep / 100.0), "fronts": fronts, "lit_rooms": lit, "rooms": near, "well_placed": suit}


POINTS = {"1.1": 15, "1.2": 15, "1.3": 10, "1.4": 5, "1.5": 5, "2.1": 8, "2.2": 7, "2.3": 5, "2.4": 5, "3.1": 7, "3.2": 6, "3.3": 7, "3.4": 5}
PASSED = 60.0


def _pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1.0)))
    return ((p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2) ** 0.5


def _score(p, outline, facade, street):
    """The evaluation matrix, run before a layout leaves the engine (the team's 100-point PDF). K legal = 0 on any gate."""
    units = [u for u in p.get("units", []) if u.get("ok")]
    p["score"] = None
    if not units:
        return p
    lines = [q for q in list(street or []) + list(facade or [])]
    far = 0.0
    for u in units:
        for r in u["rooms"]:
            if r["kind"] in ("living", "bed", "bed_main"):
                c = (sum(x[0] for x in r["pts"]) / len(r["pts"]), sum(x[1] for x in r["pts"]) / len(r["pts"]))
                far = max(far, min(_pt_seg(c, a, b) for a, b in lines))
    over = 0.0
    for i, u in enumerate(units):
        for v in units[i + 1:]:
            for r in u["rooms"]:
                for t in v["rooms"]:
                    over = max(over, _shared([tuple(c) for c in r["pts"]], _hull(t["pts"])))
    items = [u.get("matrix", {}) for u in units]
    every = lambda k: all(x.get(k, True) for x in items)
    route = lambda u: [float(c["text"].split(" m from")[0].split()[-1]) for c in u.get("checks", []) if c.get("rule") == "evac" and " m from" in c.get("text", "")]
    egress = max([(route(u) or [plan2.far_door(u)])[0] for u in units] + [0.0])
    inside = lambda c, q: F.inside(c[0], c[1], q)
    deep, done, plot, held = 0, 0, 0, 0
    claimed = [[tuple(c) for c in u["outline"]] for u in units]
    used = [q for q in p.get("patios", []) if isinstance(q, list)] + [q["pts"] for q in p.get("patios", []) if isinstance(q, dict)] + [r["pts"] for u in units for r in u["rooms"]] + [c["pts"] for c in p.get("corridors", [])] + [x["pts"] for x in p.get("shared_spaces", []) if x.get("access")] + [c if isinstance(c, list) else c["pts"] for c in p.get("cores", [])]
    xs, ys = [c[0] for c in outline], [c[1] for c in outline]
    x = min(xs) + 0.25
    while x < max(xs):                                    # 3.3: the floor beyond 9 m, read on a 50 cm grid
        y = min(ys) + 0.25
        while y < max(ys):
            c = (x, y)
            if F.inside(x, y, outline):
                plot += 1
                held += any(inside(c, q) for q in used) or any(inside(c, q) for q in claimed) or any(F.inside(x, y, [tuple(k) for k in h["pts"]]) for h in p.get("shared_spaces", []) if not h.get("access"))
                if min(_pt_seg(c, a, b) for a, b in lines) > REACH:
                    deep += 1
                    done += any(inside(c, q) for q in used)
            y += 0.5
        x += 0.5
    deep_pct = 100.0 * done / deep if deep else 100.0
    if p.get("floor"):
        p["floor"]["coverage"] = round(100.0 * held / plot, 1) if plot else None
    for x in p.get("shared_spaces", []):                  # the deep rooms are part of the fire route too
        if x.get("access") == "shared":
            c = (sum(q[0] for q in x["pts"]) / len(x["pts"]), sum(q[1] for q in x["pts"]) / len(x["pts"]))
            egress = max(egress, min(_pt_seg(c, a, b) for a, b in (street or facade)))
    fire = [(c.get("ok") if isinstance(c, dict) else c[1]) for c in p.get("building_checks", []) if (c.get("rule") if isinstance(c, dict) else c[0]) in ("exits", "stair_type")]
    door_up = p.get("levels", 1) > 1 and any(u.get("kind") == "door" for u in units)
    ok = {"1.1": far <= REACH, "1.2": over <= 0.001, "1.3": every("openings"), "1.4": not door_up,
          "2.1": every("foyer"), "2.2": every("no_thoroughfare"), "2.3": every("widths"), "2.4": every("doors"),
          "3.1": every("grocery"), "3.2": every("quiet"), "3.3": deep_pct >= 99.9 and not p.get("dead_m2"), "3.4": every("affinity")}
    pts = {k: POINTS[k] if ok[k] else 0 for k in ok}
    pts["1.5"] = round(max(0.0, 5.0 - max(0.0, egress - 25.0)), 1)
    gate = ok["1.1"] and ok["1.2"] and ok["1.3"] and ok["1.4"] and all(fire)
    total = sum(pts.values()) if gate else 0.0
    p["score"] = {"total": round(total, 1), "gate": gate, "tier": "Rejected" if total < PASSED else "Bronze" if total < 75 else "Silver" if total < 90 else "Gold", "points": pts, "deep_pct": round(deep_pct, 1), "egress_m": round(egress, 1)}
    p["solar"] = _solar(p, outline, facade, street)
    return p


def build_pairs(outline, facade, street, height, mix, fill=True, sizes=None, budget=True):
    """Mirrored flats round one shared lobby: along each street front flat A, the lobby, then flat B, A flipped across the lobby so
    their foyers meet at it. The cascade runs top down: the lobby is taken from the floor first, then the flats share what is left."""
    _set_outline(outline)
    sizes = sizes or {}
    gross = area([tuple(q) for q in outline])
    fronts = sorted([f for f in plan2._fronts(outline, facade, street) if f.public], key=lambda f: -max(b - a for a, b in f.spans))
    want = []
    for t in plan2.ORDER:
        want += [t] * int(mix.get(t, 0) or 0)
    left, units, corridors = list(want), [], []
    params = {"layout": "pairs", "fill": fill, "corridor_w": 0}
    for f in fronts:
        for a, b in sorted(f.spans, key=lambda q: q[0] - q[1]):
            best = (0, 0.0, None)
            for k in range(int((b - a) // PAIR_W["studio"]), 0, -1):
                seq = list(left)[:k]
                while len(seq) < k:
                    seq.append("studio" if len(seq) % 2 else "1bed")
                nodes = (k + 1) // 2
                L = max(LOBBY_MIN, min(LOBBY_MAX, LOBBY_SHARE * gross / (nodes * 4.0))) if budget else LOBBY_MIN
                flats = b - a - (L / 2.0 if k % 2 else 0.0)        # an odd flat at the end keeps a whole lobby beside it
                wants = [PAIR_W[t] + L / 2.0 for t in seq]
                if flats < sum(wants):
                    continue
                widths, u, got, floor, nodes_at = _fit_widths(seq, flats, wants), a, [], 0.0, []
                for i in range(0, k, 2):                           # flat A, then flat B reflected across their party wall
                    wa = widths[i]
                    wall = u + wa
                    q = _cell(f, u, wall)
                    D = min(REACH, max(c[1] for c in q)) if q else 0.0
                    A = None
                    if q and D >= 5.5 and not _taken([tuple(f.frame.to_world(c)) for c in ((u, 0.0), (wall, 0.0), (wall, D), (u, D))]):
                        A = _cut_flat(seq[i], [tuple(c) for c in _shift(q, u)], wa, D, "pair-%s-%g" % (seq[i], round(wa, 1)), False, L / 2.0)
                    B, wb = None, widths[i + 1] if i + 1 < k else 0.0
                    if A and wb:
                        q2 = _cell(f, wall, wall + wb)
                        D2 = min(REACH, max(c[1] for c in q2)) if q2 else 0.0
                        if q2 and D2 >= 5.5:
                            B = _cut_flat(seq[i + 1], [tuple(c) for c in _shift(q2, wall)], wb, D2, "pair-%s-%g" % (seq[i + 1], round(wb, 1)), True, L / 2.0, A["Yb"])
                    if A:
                        got.append((u, A, seq[i])); floor += A["useful"]
                        nodes_at.append((wall, A["Yb"]))
                    if B:
                        got.append((wall, B, seq[i + 1])); floor += B["useful"]
                    u = wall + wb
                if (len(got), floor) > best[:2]:
                    best = (len(got), floor, (got, nodes_at, L))
            if best[2]:
                got, nodes_at, L = best[2]
                for wall, Yb in nodes_at:
                    q = clip(f.local, (wall - L / 2.0, 0.0, wall + L / 2.0, Yb + 0.1))
                    if len(q) >= 3:
                        corridors.append({"pts": [f.frame.to_world(c) for c in q], "width": L, "length": Yb + 0.1, "name": "lobby"})
                for u0, g, t in got:
                    u = _unit(f.frame, u0, g, t, height, "door", False, [])
                    u["entry"] = "shared lobby, foyer beside its mirrored neighbour"
                    units.append(u)
                    if t in left:
                        left.remove(t)
    return _plan(outline, units, corridors, left, want, params, [])


def build_cut(outline, facade, street, height, mix, fill=True, sizes=None):
    """Homes cut from the real shop outline: each street front is sliced end to end into flats that follow the walls,
    each flat with its own street door; a passage from the street reaches the deep middle, which gets uses that need no daylight."""
    _set_outline(outline)
    sizes = sizes or {}
    fronts = sorted([f for f in plan2._fronts(outline, facade, street) if f.public], key=lambda f: -max(b - a for a, b in f.spans))
    want = []
    for t in plan2.ORDER:
        want += [t] * int(mix.get(t, 0) or 0)
    left, units, corridors, service = list(want), [], [], []
    params = {"layout": "cut", "fill": fill, "corridor_w": 0}
    if not fronts:
        return _plan(outline, [], [], left, want, params, [])
    main = fronts[0]
    a0, b0 = max(main.spans, key=lambda q: q[1] - q[0])
    for f in fronts:
        for a, b in sorted(f.spans, key=lambda q: q[0] - q[1]):
            if f is main and (a, b) == (a0, b0):
                b = _passage(f, a, b, corridors)
            while b - a > 4.6 and _taken([tuple(f.frame.to_world(c)) for c in ((a, 0.0), (a + 0.5, 0.0), (a + 0.5, 5.5), (a, 5.5))]):
                a += 0.5                                      # a corner already cut from the next street
            while b - a > 4.6 and _taken([tuple(f.frame.to_world(c)) for c in ((b - 0.5, 0.0), (b, 0.0), (b, 5.5), (b - 0.5, 5.5))]):
                b -= 0.5
            cut, left = _cut_span(f, a, b, left, fill, height, sizes, units)
            for u0, g, t in cut:
                units.append(_unit(f.frame, u0, g, t, height, "door", False, []))
    return _plan(outline, units, corridors, left, want, params, [])


def _trim(u):
    """Every room stands inside the real walls: what pokes past the outline is cut off, and the flat's floor follows."""
    for r in u["rooms"]:
        q = [tuple(c) for c in r["pts"]]
        if len(q) == 4:
            t = _overlap_of(_OUTLINE, q)
            if len(t) >= 3 and area(q) - area(t) > 0.005:
                r["pts"] = [list(c) for c in t]
                r["area"] = round(area(t), 1)
        else:                                              # an L or T hall: any corner past the wall comes back onto it
            out = []
            ring = list(zip(_OUTLINE, _OUTLINE[1:] + _OUTLINE[:1]))
            for c in q:
                if F.inside(c[0], c[1], _OUTLINE):
                    out.append(list(c))
                else:
                    a, b = min(ring, key=lambda e: _pt_seg(c, e[0], e[1]))
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    t = max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / (dx * dx + dy * dy or 1.0)))
                    out.append([a[0] + t * dx, a[1] + t * dy])
            r["pts"] = out
    u["area_m2"] = round(sum(r["area"] for r in u["rooms"]), 1)


def _plan(outline, units, corridors, left, want, params, notes):
    for u in units:
        _trim(u)
    kept = []                                             # the same rule, last: a flat on floor already taken does not stay
    for u in units:
        q = [tuple(p) for p in u["outline"]]
        if any(_shared(q, [tuple(p) for p in k["outline"]]) > FLOOR_TOL for k in kept) or \
                any(_shared([tuple(c) for c in r["pts"]], _hull(t["pts"])) > 0.001 for k in kept for r in u["rooms"] for t in k["rooms"]):
            left = list(left) + [u["type"]]
        else:
            kept.append(u)
    units = kept
    plan = plan2._plan(outline, "typical", units, [], corridors, left, want, params)
    halls = sum(area([tuple(p) for p in c["pts"]]) for c in corridors)
    plan["circulation_m2"] = round(halls, 1)
    plan["unused_m2"] = plan["other_use_m2"] = round(max(plan["shell_area_m2"] - sum(u["area_m2"] for u in units) - halls, 0), 1)
    plan["other_use"] = ("%.0f m² for the building: storage rooms, a bike room or a community room (no flat there would have its "
                         "own façade: Decret 141/2012 Annex 1 3.6.1)." % plan["unused_m2"]) if plan["unused_m2"] >= 4 else ""
    plan["assumptions"] = ("every flat is a real plan (Swiss Dwellings, CC BY 4.0) stretched to its space; entered from a shared "
                           "hall behind a street lobby; windows 60%% of each room's façade x 1,5 m")
    iv = []
    lob = [c for c in corridors if c.get("name", "").startswith("lobby")]
    if len(lob) > 1:
        iv.append("%d street doors with a lobby each, so every flat door is within 25 m of one - %s" % (len(lob), plan2.CITE["evac"]))
    if corridors and params.get("layout") == "through":
        iv.append("%d passage%s %.2f m wide from the street to the block interior, a through flat on each side - %s" % (
            len(corridors), "s" if len(corridors) > 1 else "", LOBBY, CITE["lobby"]))
    elif corridors and params.get("portal"):
        iv.append("shared hall %.2f m from the building's portal - %s" % (params.get("corridor_w") or 0, CITE["corridor"]))
    elif corridors:
        iv.append("street lobby %.2f m - %s; shared hall %.2f m - %s" % (LOBBY, CITE["lobby"], params.get("corridor_w") or 0, CITE["corridor"]))
    if params.get("portal"):
        iv.append("the flats are entered through the building's existing portal (Catastro common parts), not a new door")
    widened = sum(u["lib"]["doors_widened"] for u in units)
    if widened:
        iv.append("%d doors widened to the legal width - Decret 141/2012 Annex 1 3.4" % widened)
    plan["interventions"] = iv + notes
    for u in units:
        u.setdefault("front_no", 0)
    if _PATIOS:                                           # a flat may not stand over a light well open to the sky
        keep = [u for u in plan["units"] if not any(_polys_overlap(u["outline"], q) for q in _PATIOS)]
        gone = len(plan["units"]) - len(keep)
        if gone:
            plan.setdefault("unplaced", []).extend({"type": u["type"], "reason": "over a light well (Catastro)"} for u in plan["units"] if u not in keep)
            plan["units"] = keep
            plan["interventions"].append("%d flat%s left out: over a light well open to the sky (Catastro building parts)" % (gone, "s" if gone > 1 else ""))
    plan["existing"] = [list(q) for q in _EXISTING]
    plan["light_wells"] = [list(q) for q in _PATIOS]
    return plan


def _polys_overlap(a, b, tol=0.05):
    """True if two simple polygons share area (more than touching): a vertex of one strictly inside the other, or two
    edges crossing. No shapely (the website engine runs without it)."""
    def inside(p, poly):
        x, y, c = p[0], p[1], False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                c = not c
        return c
    def shrink(poly):                                     # pull vertices 5 cm towards the centre so touching does not count
        cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
        out = []
        for x, y in poly:
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 or 1.0
            out.append((x - (x - cx) * tol / d, y - (y - cy) * tol / d))
        return out
    a, b = shrink([tuple(p) for p in a]), shrink([tuple(p) for p in b])
    if any(inside(p, b) for p in a) or any(inside(p, a) for p in b):
        return True
    def cross(p, q, r, s):
        d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
        if abs(d) < 1e-12:
            return False
        t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / d
        u = ((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])) / d
        return 0 < t < 1 and 0 < u < 1
    return any(cross(p, q, r, s) for p, q in zip(a, a[1:] + a[:1]) for r, s in zip(b, b[1:] + b[:1]))


def _sig(plan):
    return tuple(sorted((u["type"], round(sum(p[0] for p in u["outline"]), 0), round(sum(p[1] for p in u["outline"]), 0), str(u["lib"]["id"]))
                        for u in plan["units"]))


STRATEGIES = [
    ("mirrored flats round a shared lobby", {"pairs": True}),
    ("flats cut to fit the building", {"cut": True}),
    ("homes with their own street door", {"doors": True}),
    ("through flats off a passage", {"through": True}),
    ("flats off a street passage", {"through": True, "kind": "side"}),
    ("as asked, off a shared hall", {"fill": [False], "back": [False, True]}),
    ("homes on the block interior too", {"fill": [False, True], "back": [True]}),
    ("most homes, off a shared hall", {"fill": [True], "back": [False, True]}),
]


MOST = "As many homes as fit"
MAX_ITERATIONS = 5               # one of them is always as many homes as fit


def _keep(best, most, name, sc, p, m):
    if name not in best or sc > best[name][0]:
        best[name] = (sc, p, m)
    most.append(((p.get("compliant", 0), sum(u.get("area_m2", 0.0) for u in p.get("units", []) if u.get("ok"))), len(most), sc, p, m, name))


def iterations(outline, facade, height, mix, programs=None, street=None, sizes=None, existing=None, weights=None,
               lit_depth=5.5, lit_source=None, patios=None):
    """'As it is' (the flats asked, lobby at the end of the façade, 7 m deep) and one iteration per strategy that
    changes the plan (0 to 3), each the best of its variants. weights: {match, passing, eff, per_home, fails, plan}
    (plan = the real-plan fit scores). existing: the building's portal / stair. Returns (before, [(name, plan, metrics)], tried)."""
    st = street or facade
    _FIT.clear()
    _DEADLINE[0] = time.time() + BUDGET if BUDGET else None
    layout._DEPTH.clear()
    LIT[0] = lit_depth                                  # the predicted lit depth here, else the 5,5 m design assumption
    LIT_CITE[0] = ("NOMAD liveability, not law: lit depth %.1f m from the daylight model (DF >= 2 %%) for this place" % lit_depth
                   if lit_source == "bars" else "NOMAD liveability, not law: lit depth %.1f m assumed (no daylight prediction here)" % lit_depth)
    _EXISTING[:] = [[tuple(p) for p in q] for q in (existing or [])]
    _PATIOS[:] = [[tuple(p) for p in q] for q in (patios or [])]
    W = dict(plan2.WEIGHTS, plan=0.02)                 # Finch-style weight sliders (the website can change them)
    W.update(dict((k, float(v)) for k, v in (weights or {}).items() if k in W))
    score = lambda p, m: sum(W[k] * m[k] for k in plan2.WEIGHTS) + W["plan"] * sum(u["lib"]["score"] for u in p["units"])
    before = build(outline, facade, st, height, mix, D=7.0, lobby_at=0.0, back_flats=False, sizes=sizes)
    best, most, tried = {}, [], 0
    late = lambda: bool(most) and _DEADLINE[0] and time.time() > _DEADLINE[0] + 0.5 * BUDGET   # the browser stops widening the search here
    for name, v in STRATEGIES:
        if v.get("through"):
            for la in (0.0, 0.5, 1.0):
                for fill in (False, True):
                    for sf in (False, True):
                        p = build_through(outline, facade, st, height, mix, la, fill, sf, sizes, v.get("kind", "through"))
                        tried += 1
                        if not p["units"]:
                            continue
                        m = plan2.metrics(p, mix)
                        sc = score(p, m)
                        _keep(best, most, name, sc, p, m)
            continue
        if v.get("pairs"):
            for fill in (False, True):
                p = build_pairs(outline, facade, st, height, mix, fill, sizes)
                tried += 1
                if p["units"]:
                    m = plan2.metrics(p, mix)
                    _keep(best, most, name, score(p, m), p, m)
            continue
        if v.get("cut"):
            for fill in (False, True):
                p = build_cut(outline, facade, st, height, mix, fill, sizes)
                tried += 1
                if p["units"]:
                    m = plan2.metrics(p, mix)
                    sc = score(p, m)
                    _keep(best, most, name, sc, p, m)
            continue
        if v.get("doors"):
            for D in DOOR_DEPTHS:
                for fill in (False, True):
                    for sf in (False, True):
                        if late():
                            continue
                        p = build_doors(outline, facade, st, height, mix, D, fill, sf, sizes)
                        tried += 1
                        if not p["units"]:
                            continue
                        m = plan2.metrics(p, mix)
                        sc = score(p, m)
                        _keep(best, most, name, sc, p, m)
            continue
        deep = max([layout.depth_at(f.local, x0, x1) for f in plan2._fronts(outline, facade, st) for x0, x1 in f.spans] or [0.0])
        for D in (DEPTHS if deep >= 6.5 else SHALLOW + DEPTHS):   # a shallow shop also tries 5 m deep flats (real ones from 4,2 m)
            for la in (0.0, 0.5, 1.0):
                for cw in plan2.CORR_W:
                    for fill in v["fill"]:
                        for bk in v["back"]:
                            for sf in (False, True):
                                if late():
                                    continue
                                p = build(outline, facade, st, height, mix, D, la, cw, fill, sf, bk, sizes)
                                tried += 1
                                if name.startswith("homes on the block") and not any(u["kind"] == "back" and u["ok"] for u in p["units"]):
                                    continue
                                m = plan2.metrics(p, mix)
                                sc = score(p, m)
                                _keep(best, most, name, sc, p, m)
    small = {"studio": 40}                                 # the smallest flats, everywhere they fit, whatever was asked for
    if any(v.get("cut") for _, v in STRATEGIES):           # buildings with stacked floors have no street-door flats
        for p in [build_cut(outline, facade, st, height, small, True, sizes)] + [build_doors(outline, facade, st, height, small, D, True, False, sizes) for D in DOOR_DEPTHS]:
            tried += 1
            if p["units"]:
                m = plan2.metrics(p, mix)
                _keep({}, most, "the smallest flats, everywhere they fit", 0.0, p, m)
    def finish(name, way, p, m):
        p = _options(plan2._passing_only(dict(p)))
        p["strategy"], p["way"] = name, way
        if p["params"].get("fill"):
            p["unplaced"], p["requested"] = [], p["placed"]
        p["proposal_ok"] = p["placed"] > 0 and p["compliant"] >= p["requested"] and p["density_ok"] and not p["unplaced"]
        p["stage6"] = "%s (%s): %d real flats fit and pass, %.0f%% of the floor in homes, %.0f m² for the building" % (
            name, way, p["compliant"], 100 * m["eff"], p["unused_m2"])
        _options(p)
        _middle(p, outline, facade, st)
        _score(p, outline, facade, st)
        return (name, p, m)                                # the matrix decides before any 3D or export
    passes = lambda r: not r[1].get("score") or r[1]["score"]["tier"] != "Rejected"
    def good(p):
        return [u for u in p.get("units", []) if u.get("ok")]
    def mean(v):
        return sum(v) / float(len(v)) if v else 0.0
    def real_plans(x):
        us = good(x[3])
        return (mean([1.0 if u["lib"].get("source", "").startswith(("Swiss", "ResPlan")) else 0.0 for u in us]), mean([u["lib"].get("score", 0.0) for u in us]), x[0][0])
    def circulation(x):
        p = x[3]
        halls = sum(area([tuple(c) for c in h["pts"]]) for h in p.get("corridors", []))
        return (mean([u.get("comfort", 0) for u in good(p)]), p["params"].get("layout") == "pairs", -halls, x[0][0])
    def daylight(x):
        return (_solar(x[3], outline, facade, st)["score"], x[0][0])
    # five layouts, each with one criterion at 100 %: the first candidate that passes the matrix and differs from those already kept
    FIVE = [("The flats you asked for", lambda x: (x[4]["match"], x[0])), (MOST, lambda x: x[0]), ("How well real plans fit", real_plans),
            ("Best circulation", circulation), ("Most daylight", daylight)]
    pool = [x for x in most if x[3].get("compliant")]
    out, seen, most_sig = [], set([_sig(before)]), None
    for name, key in [FIVE[1], FIVE[0]] + FIVE[2:]:        # the most homes are claimed first, so that layout can never go to another slot
        for x in sorted(pool, key=lambda c: (key(c), -c[1]), reverse=True):
            same = name == FIVE[0][0] and out and _sig(x[3]) == most_sig     # when what was asked is also the most that fits, both show it
            if _sig(x[3]) in seen and not same:
                continue
            p = dict(x[3], params=dict(x[3]["params"], fill=True)) if name == MOST else x[3]
            r = finish(name, x[5], p, x[4])
            seen.add(_sig(x[3]))
            if passes(r):
                out.append(r)
                if name == MOST:
                    most_sig = _sig(x[3])
                break
    out.sort(key=lambda r: [x[0] for x in FIVE].index(r[0]))
    _options(before)
    _middle(before, outline, facade, st)
    _score(before, outline, facade, st)
    if not out:
        p = dict(before)
        p["strategy"] = "no real flat fits"
        p["stage6"] = "no real flat plan fits this shop's façade and depth, or none passes the evaluation matrix"
        out.append(("no real flat fits", p, plan2.metrics(p, mix)))
    for x in most:
        for u in x[3].get("units", []):
            u.pop("_alts", None)
    for _, p, _ in best.values():                          # layouts not kept: drop what only the gallery needs
        for u in p.get("units", []):
            u.pop("_alts", None)
    return before, out, tried
