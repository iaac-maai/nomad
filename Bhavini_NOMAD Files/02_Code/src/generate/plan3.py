# -*- coding: utf-8 -*-
"""Nomad plan generator v3: real flats, stretched to fit, around a shared hall (Finch's method, the real flats' rules).

How a shop becomes homes, as real buildings do it (lab book E24: 85 % of real flats open into their own hall from a
common stair or corridor; living rooms and bedrooms on the façade, baths and stores inside):
  1 street door + lobby   a 1,50 m wide lobby from the street (CTE DB-SUA Anejo A: 1,50 m turning circle in the
                          entrance vestibule of an accessible route)
  2 shared hall           a corridor behind the street flats, 1,20 m or 1,50 m wide (CTE DB-SUA Anejo A, accessible route
                          >= 1,20 m), from the lobby both ways
  3 street flats          each a REAL flat from the library (src/library/build_library.py): lit only from its front,
                          entered from the back, stretched to its space with locked walls (src/generate/library_fit.py),
                          then checked: the law, the plan graph, doors and turning circles
  4 block-interior flats  where the shop has a façade on the block interior: a spine from the lobby to a gallery, and real
                          flats lit from that façade; every flat door within 25 m of the street door (CTE DB-SI SI 3)
  5 what is left          building storage, bike room or community room - never a scrap inside a flat
Iterations (scored with the same Finch-style weights as v2): flat depth, lobby position, hall width, the order of the
flats, "as asked" or "fill the shop", with or without block-interior flats.
Plain Python (Grasshopper IronPython 2.7 and the browser): no f-strings, no shapely.
"""
import io, json, math, os

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
_EXISTING = []                   # the building's own portal / stair on this ground floor (world polygons): never built over
_OUTLINE = []                    # the shop outline (world): every room corner must lie inside it
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


def _free(front, u0, u1, d):
    """No existing portal or stair inside this rectangle of a front."""
    return not any(plan2._overlap(front.frame, (u0, 0.0, u1, d), q) for q in _EXISTING)


def library(path=None):
    """The street-flat library: real flats lit from one side that pass every check (built by src/library/build_library.py,
    kept small by src/library/street_library.py)."""
    if "lib" not in _LIB:
        here = os.path.dirname(os.path.abspath(__file__))
        for p in [path] if path else [os.path.join(here, "library_street.json"),
                                       os.path.join(here, "..", "..", "results", "library", "library_street.json")]:
            if p and os.path.exists(p):
                with io.open(p, encoding="utf-8") as f:
                    _LIB["lib"] = json.load(f)
                break
    return _LIB.get("lib", []) + _LIB.get("own", [])


def set_own(entries):
    """Your own plans (src/library/own_plans.py) join the library for the next layouts."""
    entries = list(entries or [])
    if [e["id"] for e in entries] != [e["id"] for e in _LIB.get("own", [])]:
        _LIB["own"] = entries
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
    if key not in _FIT:
        _FIT[key] = _furnished(t, W, D, target, mode, False)
    if _FIT[key] or not gen:
        return _FIT[key]
    gk = key + ("gen",)
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
    for g in F.best_fits(library(), BEDS[t], W, D, lit=lit, entry_sides=ent, target_m2=target, top=10, generate=generate):
        if not _flat_ok(g, mode.startswith("through")):  # would fail the flat checks: let the next plan take the slot
            continue
        items, cs = U.furnish(g)                     # furnished and checked (src/generate/furnish.py): wardrobe, bed, kitchen, bathroom
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
         "room_scores": F.room_scores(f)}
    _check(u, height, f)
    if alts is not None:                                  # the gallery, built for the kept layouts only (_options)
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
            evac = D + cw / 2.0 + abs(door[0] - (ul + LW / 2.0))
            u["checks"].append({"rule": "evac", "ok": evac <= EVAC_MAX, "cite": plan2.CITE["evac"],
                                "text": "door %.1f m from the street door along the hall" % evac})
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
                    evac = max(reach, 0.0) + abs(sf.frame.to_local(door)[0] - ue)
                    ok = evac <= EVAC_MAX
                    u["checks"].append({"rule": "evac", "ok": ok, "cite": plan2.CITE["evac"],
                                        "text": "door %.1f m from the street door along the hall" % evac})
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
                evac = Y + abs(dl[0] - (ul + LOBBY / 2.0))
                ok = evac <= EVAC_MAX
                u["checks"].append({"rule": "evac", "ok": ok, "cite": plan2.CITE["evac"],
                                    "text": "door %.1f m from the street door along the hall" % evac})
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


def build_doors(outline, facade, street, height, mix, D=7.0, fill=False, small_first=False, sizes=None):
    """Flats side by side along the street, each with its own street door: no lobby and no shared hall, so a shop too
    shallow for a hall behind the flats can still hold homes."""
    _set_outline(outline)
    sizes = sizes or {}
    fronts = [f for f in plan2._fronts(outline, facade, street) if f.public]
    want = []
    for t in (plan2.ORDER[::-1] if small_first else plan2.ORDER):
        want += [t] * int(mix.get(t, 0) or 0)
    left, units = list(want), []
    for f in fronts:
        for a, b in sorted(f.spans, key=lambda q: q[0] - q[1]):
            row, left = _row(f, a, b, D, left, fill, D, sizes, "door")
            for u0, w, t in row:
                gs = fits(t, w, D, sizes.get(t), "door")
                if gs:
                    units.append(_unit(f.frame, u0, gs[0], t, height, "door", False, gs[1:]))
    params = {"layout": "doors", "D": D, "fill": fill, "small_first": small_first, "corridor_w": 0}
    return _plan(outline, units, [], left, want, params, [])


def _plan(outline, units, corridors, left, want, params, notes):
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
    plan["existing"] = [list(q) for q in _EXISTING]
    return plan


def _sig(plan):
    return tuple(sorted((u["type"], round(sum(p[0] for p in u["outline"]), 0), round(sum(p[1] for p in u["outline"]), 0), str(u["lib"]["id"]))
                        for u in plan["units"]))


STRATEGIES = [
    ("homes with their own street door", {"doors": True}),
    ("through flats off a passage", {"through": True}),
    ("flats off a street passage", {"through": True, "kind": "side"}),
    ("as asked, off a shared hall", {"fill": [False], "back": [False, True]}),
    ("homes on the block interior too", {"fill": [False, True], "back": [True]}),
    ("most homes, off a shared hall", {"fill": [True], "back": [False, True]}),
]


def iterations(outline, facade, height, mix, programs=None, street=None, sizes=None, existing=None, weights=None,
               lit_depth=5.5, lit_source=None):
    """'As it is' (the flats asked, lobby at the end of the façade, 7 m deep) and one iteration per strategy that
    changes the plan (0 to 3), each the best of its variants. weights: {match, passing, eff, per_home, fails, plan}
    (plan = the real-plan fit scores). existing: the building's portal / stair. Returns (before, [(name, plan, metrics)], tried)."""
    st = street or facade
    _FIT.clear()
    layout._DEPTH.clear()
    LIT[0] = lit_depth                                  # the predicted lit depth here, else the 5,5 m design assumption
    LIT_CITE[0] = ("NOMAD liveability, not law: lit depth %.1f m from the daylight model (DF >= 2 %%) for this place" % lit_depth
                   if lit_source == "bars" else "NOMAD liveability, not law: lit depth %.1f m assumed (no daylight prediction here)" % lit_depth)
    _EXISTING[:] = [[tuple(p) for p in q] for q in (existing or [])]
    W = dict(plan2.WEIGHTS, plan=0.02)                 # Finch-style weight sliders (the website can change them)
    W.update(dict((k, float(v)) for k, v in (weights or {}).items() if k in W))
    score = lambda p, m: sum(W[k] * m[k] for k in plan2.WEIGHTS) + W["plan"] * sum(u["lib"]["score"] for u in p["units"])
    before = build(outline, facade, st, height, mix, D=7.0, lobby_at=0.0, back_flats=False, sizes=sizes)
    best, tried = {}, 0
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
                        if name not in best or sc > best[name][0]:
                            best[name] = (sc, p, m)
            continue
        if v.get("doors"):
            for D in DOOR_DEPTHS:
                for fill in (False, True):
                    for sf in (False, True):
                        p = build_doors(outline, facade, st, height, mix, D, fill, sf, sizes)
                        tried += 1
                        if not p["units"]:
                            continue
                        m = plan2.metrics(p, mix)
                        sc = score(p, m)
                        if name not in best or sc > best[name][0]:
                            best[name] = (sc, p, m)
            continue
        deep = max([layout.depth_at(f.local, x0, x1) for f in plan2._fronts(outline, facade, st) for x0, x1 in f.spans] or [0.0])
        for D in (DEPTHS if deep >= 6.5 else SHALLOW + DEPTHS):   # a shallow shop also tries 5 m deep flats (real ones from 4,2 m)
            for la in (0.0, 0.5, 1.0):
                for cw in plan2.CORR_W:
                    for fill in v["fill"]:
                        for bk in v["back"]:
                            for sf in (False, True):
                                p = build(outline, facade, st, height, mix, D, la, cw, fill, sf, bk, sizes)
                                tried += 1
                                if name.startswith("homes on the block") and not any(u["kind"] == "back" and u["ok"] for u in p["units"]):
                                    continue
                                m = plan2.metrics(p, mix)
                                sc = score(p, m)
                                if name not in best or sc > best[name][0]:
                                    best[name] = (sc, p, m)
    out, seen = [], set([_sig(before)])
    for name, _ in STRATEGIES:
        if name not in best:
            continue
        sc, p, m = best[name]
        if _sig(p) in seen or not p["compliant"]:
            continue
        seen.add(_sig(p))
        p = _options(plan2._passing_only(dict(p)))
        p["strategy"] = name
        if p["params"].get("fill"):
            p["unplaced"], p["requested"] = [], p["placed"]
        p["proposal_ok"] = p["placed"] > 0 and p["compliant"] >= p["requested"] and p["density_ok"] and not p["unplaced"]
        p["stage6"] = "%s: %d real flats fit and pass, %.0f%% of the floor in homes, %.0f m² for the building" % (
            name, p["compliant"], 100 * m["eff"], p["unused_m2"])
        out.append((name, p, m))
    if not out:
        p = dict(before)
        p["strategy"] = "no real flat fits"
        p["stage6"] = "no real flat plan fits this shop's façade and depth with a lobby and a shared hall"
        out.append(("no real flat fits", p, plan2.metrics(p, mix)))
    for _, p, _ in [(None, before, None)] + out:
        _options(p)
    for _, p, _ in best.values():                          # layouts not kept: drop what only the gallery needs
        for u in p.get("units", []):
            u.pop("_alts", None)
    return before, out, tried
