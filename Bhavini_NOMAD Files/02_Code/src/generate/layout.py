# -*- coding: utf-8 -*-
"""Nomad floor-plan generator: a shell (shop outline + façade) and a unit mix -> a housing layout.

Runs in Grasshopper (IronPython 2.7) and Python 3: plain Python only, no f-strings, no shapely.

How it lays out a plan (the same logic an architect uses for a deep ground-floor local):
  1. The longest façade with windows is the street front. Everything is measured from it:
     u = along the façade, v = depth into the shop.
  2. Each flat is a strip that touches that façade. Its rooms that need light (living room,
     bedrooms) sit in a front band; rooms that do not (kitchen, bathroom, hall) sit behind them.
  3. Room sizes come from room_programs.json (learned from 13,444 Swiss flats that pass all
     Nomad rules). "typical" uses the median size, "compact" the 25th percentile.
  4. Flats are placed side by side along the façade in the order asked for, until the façade
     or the depth runs out; anything that does not fit is listed with the reason.
  5. Every flat is checked against the Nomad rules (useful area, bedroom size and square, living
     circle, windows 1/8, façade S/9 and 3 m, height, bathrooms, Barcelona density) with citations.
Assumptions (stated in every report): each ground-floor flat is entered from the street; new
windows can be opened in the façade (60% of each room's width, 1,5 m tall); flats are placed only
along façades that already have windows (all of them, longest first); no patios are cut in yet.
"""
import math

TYPES = ["3bed", "2bed", "1bed", "studio"]          # placement order: biggest first
BEDS = {"studio": 0, "1bed": 1, "2bed": 2, "3bed": 3}
WALL = 0.10                                          # half a partition each side, m
FRONT_MAX = 5.5                                      # deepest a room with one window should be, m
MIN_WIDTH = {"living": 3.3, "bed_main": 2.9, "bed": 2.3}
WINDOW_SHARE, WINDOW_H = 0.6, 1.5

CITE = {
    "useful": "MPGM 2004 Barcelona DA1 2.a (>= 40 m² útils) / Decret 141/2012 Annex 1 3.1 (>= 36 m²)",
    "bedroom": "Decret 141/2012 Annex 1 3.8 (>= 6 m², 2,00 m square; 2,60 m in one if >= 3 bedrooms)",
    "living": "Decret 141/2012 Annex 1 3.7.2 (2,80 m circle)",
    "windows": "Decret 141/2012 Annex 1 3.9.1 (windows >= 1/8 of the room)",
    "facade": "Decret 141/2012 Annex 1 3.6.2 (L >= S/9) + MPGM 2004 DA1 2.b (>= 3 m)",
    "height": "Decret 141/2012 Annex 4 group C (Annex 1 3.5: >= 2,40 m for a change of use)",
    "wet_height": "Decret 141/2012 Annex 1 3.5 (bathrooms, kitchens, circulation >= 2,20 m)",
    "living_facade": "Decret 141/2012 Annex 1 3.7.2 (living room touches the façade over >= 2,20 m)",
    "hall": "Decret 141/2012 Annex 1 3.4.1.d (circulation to the accessible rooms >= 1 m wide)",
    "bath": "Decret 141/2012 Annex 1 3.11 (1 bathroom; 2 WC if >= 4 bedrooms)",
    "density": "MPGM 2004 Barcelona art. 318 (zone 12) / art. 323 (zone 13) (dwellings <= built area / 80 m²)",
}


# ---------- small geometry helpers ----------
def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def centroid(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def clip(subject, rect):
    """Sutherland-Hodgman: part of polygon `subject` inside axis-aligned rect (u0, v0, u1, v1)."""
    u0, v0, u1, v1 = rect
    edges = [(lambda p: p[0] >= u0, lambda a, b: _ix(a, b, 0, u0)),
             (lambda p: p[0] <= u1, lambda a, b: _ix(a, b, 0, u1)),
             (lambda p: p[1] >= v0, lambda a, b: _ix(a, b, 1, v0)),
             (lambda p: p[1] <= v1, lambda a, b: _ix(a, b, 1, v1))]
    out = list(subject)
    for inside, cut in edges:
        if not out:
            break
        inp, out = out, []
        for i in range(len(inp)):
            a, b = inp[i - 1], inp[i]
            if inside(b):
                if not inside(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside(a):
                out.append(cut(a, b))
    return out


def _ix(a, b, axis, value):
    t = (value - a[axis]) / ((b[axis] - a[axis]) or 1e-12)
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


class Frame(object):
    """Local frame of the main façade: u along it, v into the building."""

    def __init__(self, outline, facade):
        best = max(facade, key=lambda s: math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
        (ax, ay), (bx, by) = best
        L = math.hypot(bx - ax, by - ay)
        self.ux, self.uy = (bx - ax) / L, (by - ay) / L
        self.vx, self.vy = -self.uy, self.ux
        cx, cy = centroid(outline)
        if (cx - ax) * self.vx + (cy - ay) * self.vy < 0:      # make v point inside
            self.vx, self.vy = -self.vx, -self.vy
        self.ox, self.oy = ax, ay

    def to_local(self, p):
        dx, dy = p[0] - self.ox, p[1] - self.oy
        return (dx * self.ux + dy * self.uy, dx * self.vx + dy * self.vy)

    def to_world(self, p):
        return (self.ox + p[0] * self.ux + p[1] * self.vx, self.oy + p[0] * self.uy + p[1] * self.vy)


def facade_intervals(frame, facade, tol_angle=0.26, tol_dist=1.0):
    """u-ranges of façade segments parallel to (and on) the main façade line."""
    spans = []
    for a, b in facade:
        la, lb = frame.to_local(a), frame.to_local(b)
        if abs(la[1]) > tol_dist or abs(lb[1]) > tol_dist:
            continue
        ang = abs(math.atan2(lb[1] - la[1], lb[0] - la[0]))
        if min(ang, math.pi - ang) > tol_angle:
            continue
        spans.append((min(la[0], lb[0]), max(la[0], lb[0])))
    spans.sort()
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1] + 0.6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], s[1]))
        else:
            merged.append(s)
    return merged


_DEPTH = {}


def depth_at(local_outline, u0, u1, step=0.25):
    """Usable depth of the shell between u0 and u1, measured from the façade line v=0.
    Uses the 25th-percentile depth along the strip, so one notch does not shrink the whole flat;
    rooms are clipped to the real outline afterwards and checked."""
    key = (tuple(tuple(p) for p in local_outline), round(u0, 3), round(u1, 3), step)
    if key not in _DEPTH:
        if len(_DEPTH) > 200000:
            _DEPTH.clear()
        _DEPTH[key] = _depth_at(local_outline, u0, u1, step)
    return _DEPTH[key]


def _depth_at(local_outline, u0, u1, step=0.25):
    ds = []
    u = u0 + 0.05
    while u <= u1 - 0.05:
        cuts = []
        n = len(local_outline)
        for i in range(n):
            a, b = local_outline[i - 1], local_outline[i]
            if (a[0] - u) * (b[0] - u) <= 0 and a[0] != b[0]:
                t = (u - a[0]) / (b[0] - a[0])
                cuts.append(a[1] + t * (b[1] - a[1]))
        cuts = [c for c in cuts if c > 0.3]
        ds.append(min(cuts) if cuts else 0.0)
        u += step
    if not ds:
        return 0.0
    ds.sort()
    return ds[len(ds) // 4]


def facade_groups(facade):
    """Group façade segments by direction and line, so each street front gets its own frame."""
    groups = []
    for seg in sorted(facade, key=lambda s: -math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1])):
        (ax, ay), (bx, by) = seg
        ang = math.atan2(by - ay, bx - ax) % math.pi
        home = None
        for g in groups:
            d = abs(ang - g["ang"])
            if min(d, math.pi - d) < 0.26:
                f = g["frame"]
                if abs(f.to_local((ax, ay))[1]) < 1.0 and abs(f.to_local((bx, by))[1]) < 1.0:
                    home = g
                    break
        if home is None:
            groups.append({"ang": ang, "segs": [seg], "frame": None, "first": seg})
            groups[-1]["frame"] = _seg_frame(seg)
        else:
            home["segs"].append(seg)
    return groups


def _seg_frame(seg):
    f = Frame.__new__(Frame)
    (ax, ay), (bx, by) = seg
    L = math.hypot(bx - ax, by - ay) or 1e-9
    f.ux, f.uy = (bx - ax) / L, (by - ay) / L
    f.vx, f.vy = -f.uy, f.ux
    f.ox, f.oy = ax, ay
    return f


def _overlap(frame, rect, placed):
    """Area of the candidate rect (in this frame) already taken by placed flats."""
    tot = 0.0
    for poly in placed:
        loc = [frame.to_local(p) for p in poly]
        part = clip(loc, rect)
        if len(part) >= 3:
            tot += area(part)
    return tot


# ---------- programs ----------
def program_for(t, programs, size="typical"):
    p = programs[t]
    key = "median" if size == "typical" else "p25"
    rooms = [("living", "living", max(p["living_m2"][key], 16.0 if t != "studio" else 20.0))]
    if BEDS[t] >= 1:
        rooms.append(("bedroom 1", "bed_main", max(p["main_bedroom_m2"][key], 9.0)))
    for i in range(2, BEDS[t] + 1):
        rooms.append(("bedroom %d" % i, "bed", max((p["other_bedroom_m2"] or p["main_bedroom_m2"])[key], 7.0)))
    back = [("kitchen", "kitchen", max(p["kitchen_m2"][key], 5.0)),
            ("bathroom", "bath", max(p["bath_m2"][key], 3.5)),
            ("hall", "hall", max(p["circulation_m2"][key], 2.5))]
    return rooms, back


def with_targets(programs, targets, size="typical"):
    """The user's flat sizes: a copy of programs in which every room of a flat type is scaled so the flat adds up to
    targets[type] m² (useful area). Rooms never go below the minimums program_for keeps, so a target under the legal
    minimum still gives a legal room set (the flat check then shows what fails). targets: {"1bed": 55.0, ...}."""
    out = dict(programs)
    key = "median" if size == "typical" else "p25"
    for t, goal in (targets or {}).items():
        if t not in programs or not goal:
            continue
        rooms, back = program_for(t, programs, size)
        now = sum(a for _, _, a in rooms + back)
        k = float(goal) / now if now else 1.0
        p = dict(programs[t])
        for f in ("living_m2", "main_bedroom_m2", "other_bedroom_m2", "kitchen_m2", "bath_m2", "circulation_m2"):
            if p.get(f):
                p[f] = dict(p[f])
                p[f][key] = round(p[f][key] * k, 2)
        out[t] = p
    return out


# ---------- the generator ----------
def generate(outline, facade, height, mix, programs, size="typical", built_ratio=0.9, blocked=None, extra_fronts=None,
             small_first=False):
    """mix: dict type -> how many. Returns a plan dict (world coordinates) with checks.
    blocked: polygons flats must keep clear of (patios, a shared corridor) - Stage 6 (src/generate/better.py).
    extra_fronts: [(segment, away_point)] new façades (e.g. a patio's sides); their flats grow away from away_point."""
    shell_area = area(outline)
    order = []
    for t in (TYPES[::-1] if small_first else TYPES):
        order += [t] * int(mix.get(t, 0) or 0)
    cap = int(math.ceil(shell_area / built_ratio / 80.0 - 1e-9))

    # every street front (group of parallel façade segments) is a run of slots, longest front first
    fronts = []
    for g in facade_groups(facade):
        fr = g["frame"]
        cx, cy = centroid(outline)
        if (cx - fr.ox) * fr.vx + (cy - fr.oy) * fr.vy < 0:
            fr.vx, fr.vy = -fr.vx, -fr.vy
        spans = facade_intervals(fr, g["segs"])
        if spans:
            fronts.append({"frame": fr, "local": [fr.to_local(p) for p in outline], "spans": spans,
                           "len": sum(b - a for a, b in spans)})
    fronts.sort(key=lambda f: -f["len"])
    for seg, away in (extra_fronts or []):
        fr = _seg_frame(seg)
        if (away[0] - fr.ox) * fr.vx + (away[1] - fr.oy) * fr.vy > 0:   # grow away from the patio centre
            fr.vx, fr.vy = -fr.vx, -fr.vy
        L = math.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1])
        fronts.append({"frame": fr, "local": [fr.to_local(p) for p in outline], "spans": [(0.0, L)], "len": L, "patio": True})
    facade_total = sum(f["len"] for f in fronts)

    units, unplaced, taken = [], [], [list(b) for b in (blocked or [])]
    for t in order:
        front, back = program_for(t, programs, size)
        placed = None
        for fr in fronts:
            placed = _find_slot(fr, front, back, taken)
            if placed:
                break
        if placed is None:
            unplaced.append({"type": t, "reason": "no façade or depth left"})
            continue
        fr, u0, W, F, B, widths = placed
        unit = _build_unit(t, u0, W, F, B, widths, front, back, fr["local"], fr["frame"])
        unit["on_patio"] = bool(fr.get("patio"))
        units.append(unit)
        taken.append(unit["outline"])

    for u in units:
        _check_unit(u, height)
    total = len(units)
    density_ok = total <= cap
    unused = shell_area - sum(u["area_m2"] for u in units)
    req = len(order)
    compliant = [u for u in units if u["ok"]]
    return {
        "requested": req, "placed": total, "compliant": len(compliant), "unplaced": unplaced,
        "density_cap": cap, "density_ok": density_ok, "shell_area_m2": round(shell_area, 1),
        "facade_m": round(facade_total, 1), "unused_m2": round(max(unused, 0), 1),
        "proposal_ok": req > 0 and not unplaced and len(compliant) == req and density_ok,
        "units": units, "size": size,
        "assumptions": "each flat entered from the street; new façade windows 60% of room width x 1,5 m; flats sit along "
                       "façades that already have windows; no inner patios or lightwells added yet",
        "density_cite": CITE["density"],
    }


def _find_slot(fr, front, back, taken, step=0.5):
    """First place along this street front where the flat fits (depth, façade, no overlap)."""
    back_area = sum(a for _, _, a in back)
    edges = []                                              # also try starting exactly where a placed flat ends
    for poly in taken:
        us = [fr["frame"].to_local(p)[0] for p in poly]
        edges += [max(us), min(us)]
    for s0, s1 in fr["spans"]:
        cands, u = [], s0
        while u < s1 - 3.0:
            cands.append(u)
            u += step
        cands = sorted(set([round(c, 3) for c in cands] + [round(e, 3) for e in edges if s0 <= e < s1 - 3.0]))
        for u in cands:
            trial_w = sum(MIN_WIDTH[k] for _, k, _ in front)
            D = depth_at(fr["local"], u, min(s1, u + max(trial_w, 3.0)))
            F = min(FRONT_MAX, D - 2.2)                     # leave >= 2,2 m behind for kitchen/bath/hall
            if F < 3.0:
                continue
            widths = [max(MIN_WIDTH[k], a / F) for _, k, a in front]
            W = max(sum(widths), 3.0)
            B = max(2.2, back_area / W)
            if F + B > D:
                F = D - B
                if F < 3.0:
                    continue
                widths = [max(MIN_WIDTH[k], a / F) for _, k, a in front]
                W = max(sum(widths), 3.0)
            if u + W > s1 + 1e-6:
                continue
            if _overlap(fr["frame"], (u, 0.0, u + W, F + B), taken) > 0.5:
                continue
            return fr, u, W, F, B, widths
    return None


def _rect(frame, u0, v0, u1, v1, local):
    pts = clip(local, (u0, v0, u1, v1))
    if len(pts) < 3:
        return [], 0.0
    return [frame.to_world(p) for p in pts], area(pts)


def _build_unit(t, u0, W, F, B, widths, front, back, local, frame):
    rooms = []
    u = u0
    for (name, kind, target), w in zip(front, widths):
        scale = W / sum(widths)
        w = w * scale
        pts, a = _rect(frame, u + WALL, 0.0, u + w - WALL, F - WALL, local)
        rooms.append({"name": name, "kind": kind, "pts": pts, "area": round(a, 1),
                      "w": round(w - 2 * WALL, 2), "d": round(F - WALL, 2), "on_facade": True})
        u += w
    total_back = sum(a for _, _, a in back)
    u = u0
    for name, kind, target in back:
        w = W * target / total_back
        pts, a = _rect(frame, u + WALL, F + WALL, u + w - WALL, F + B - WALL, local)
        rooms.append({"name": name, "kind": kind, "pts": pts, "area": round(a, 1),
                      "w": round(w - 2 * WALL, 2), "d": round(B - 2 * WALL, 2), "on_facade": False})
        u += w
    outline_pts, ua = _rect(frame, u0, 0.0, u0 + W, F + B, local)
    return {"type": t, "outline": outline_pts, "facade_w": round(W, 2), "depth": round(F + B, 2),
            "area_m2": round(sum(r["area"] for r in rooms), 1), "rooms": rooms}


def _check_unit(u, height):
    checks = []
    S = u["area_m2"]
    checks.append(("useful", S >= 40.0, "%.1f m² useful (>= 40)" % S))
    beds = [r for r in u["rooms"] if r["kind"] in ("bed", "bed_main")]
    for r in beds:
        need = 2.6 if (r["kind"] == "bed_main" and len(beds) >= 3) else 2.0
        ok = r["area"] >= 6.0 and min(r["w"], r["d"]) >= need
        r["ok"] = ok
        r["why"] = "" if ok else "%.1f m², %.2f x %.2f m (needs 6 m² and a %.2f m square)" % (r["area"], r["w"], r["d"], need)
        checks.append(("bedroom", ok, "%s %.1f m² %.2fx%.2f m" % (r["name"], r["area"], r["w"], r["d"])))
    for r in u["rooms"]:
        if r["kind"] == "living":
            ok = min(r["w"], r["d"]) >= 2.8 and r["area"] >= 0.9 * r["w"] * r["d"]
            r["ok"], r["why"] = ok, ("" if ok else "narrower than the 2,80 m circle")
            checks.append(("living", ok, "living %.2fx%.2f m" % (r["w"], r["d"])))
    for r in u["rooms"]:
        if r["kind"] in ("living", "bed", "bed_main"):
            ratio = (WINDOW_SHARE * r["w"] * WINDOW_H) / max(r["area"], 0.1)
            ok = r["on_facade"] and ratio >= 1.0 / 8.0
            if not ok:
                r["ok"], r["why"] = False, "window only %.2f of the floor (needs 1/8)" % ratio
            checks.append(("windows", ok, "%s window ratio %.2f" % (r["name"], ratio)))
    need_f = max(S / 9.0, 3.0)
    checks.append(("facade", u["facade_w"] >= need_f - 1e-6, "façade %.2f m (needs %.2f)" % (u["facade_w"], need_f)))
    checks.append(("height", height >= 2.4, "clear height %.2f m" % height))
    checks.append(("wet_height", height >= 2.2, "bathroom, kitchen and hall height %.2f m" % height))
    for r in u["rooms"]:
        if r["kind"] == "living":
            ok = r["on_facade"] and r["w"] >= 2.2
            checks.append(("living_facade", ok, "living touches the façade over %.2f m" % (r["w"] if r["on_facade"] else 0)))
        if r["kind"] == "hall":
            ok = min(r["w"], r["d"]) >= 1.0
            if not ok:
                r["ok"], r["why"] = False, "hall %.2f m wide (needs 1 m)" % min(r["w"], r["d"])
            checks.append(("hall", ok, "hall %.2f x %.2f m" % (r["w"], r["d"])))
    checks.append(("bath", any(r["kind"] == "bath" and r["area"] >= 2.5 for r in u["rooms"]), "bathroom present"))
    for r in u["rooms"]:
        r.setdefault("ok", r["area"] > 1.0)
        r.setdefault("why", "")
    u["checks"] = [{"rule": k, "ok": ok, "text": txt, "cite": CITE[k]} for k, ok, txt in checks]
    u["ok"] = all(c["ok"] for c in u["checks"])
    u["fails"] = sorted(set(c["rule"] for c in u["checks"] if not c["ok"]))


def report(plan):
    lines = ["Nomad floor-plan proposal (%s sizes)" % plan["size"],
             "Shell %.0f m², façade %.1f m. Asked for %d flats, placed %d, %d pass every rule."
             % (plan["shell_area_m2"], plan["facade_m"], plan["requested"], plan["placed"], plan["compliant"]),
             "Density: %d flats allowed (%s) -> %s" % (plan["density_cap"], plan["density_cite"], "OK" if plan["density_ok"] else "TOO MANY"),
             "RESULT: %s" % ("PROPOSAL WORKS" if plan["proposal_ok"] else "NOT YET - see below")]
    for i, u in enumerate(plan["units"]):
        lines.append("Flat %d %s: %.1f m², %.1f m façade x %.1f m deep -> %s"
                     % (i + 1, u["type"], u["area_m2"], u["facade_w"], u["depth"], "PASS" if u["ok"] else "FAIL " + ", ".join(u["fails"])))
        for r in u["rooms"]:
            if r.get("why"):
                lines.append("    %s: %s" % (r["name"], r["why"]))
    for x in plan["unplaced"]:
        lines.append("Not placed: %s (%s)" % (x["type"], x["reason"]))
    lines.append("Unused floor area: %.0f m² (too deep for daylight or left over)" % plan["unused_m2"])
    lines.append("Assumptions: " + plan["assumptions"])
    return "\n".join(lines)
