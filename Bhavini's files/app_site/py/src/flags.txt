# -*- coding: utf-8 -*-
"""Nomad Stage 5: flags on the plan. Plain Python (runs in Grasshopper's IronPython 2.7 and in Python 3).

Given a shop (outline + façade segments), its height and a generated plan (src/generate/layout.py):
  1. daylight(): cuts the floor into a grid and measures each cell's distance to the nearest façade
     with windows. Cells are put in three bands:
        lit      distance <= lit_depth            rooms that need daylight can go here
        service  lit_depth .. lit_depth + 2,20 m  kitchen, bath, hall, storage (no daylight needed)
        dark     deeper than that                 not usable for housing without a patio or new window
     lit_depth is a DESIGN ASSUMPTION (slider, 5,5 m by default, the same as the generator), not a law:
     no article in the Nomad rulebook sets a maximum room depth.
  2. cards(): one rule card per legal check, each with OK / FAIL, the measured value, the limit,
     the article it comes from, and a point on the plan it refers to.
  3. verdict(): YES (every flat asked for fits and passes), PARTLY (some flats pass), NO (the shop
     itself fails a shell rule, or no flat passes).
"""
import math

SERVICE_DEPTH = 2.2          # m behind the lit band: kitchen / bath / hall (same as the generator)
LIT_DEPTH = 5.5              # m, design assumption (see above)

# a shop becoming homes is a change of use of part of a building: Decret 141/2012 Annex 4 group C applies Annex 1
# with 2,40 m in place of 2,50 m (Annex 1 3.5); checked word for word in rules/rules.json (CAT-141-2012-height-04C)
MIN_HEIGHT = 2.40
SHELL_CITE = {
    "height": "Decret 141/2012 Annex 4 group C (Annex 1 3.5 at 2,40 m for a change of use)",
    "useful": "MPGM 2004 Barcelona DA1 2.a",
    "facade": "MPGM 2004 Barcelona DA1 2.b",
    "density": "MPGM 2004 Barcelona art. 318 (zone 12) / art. 323 (zone 13)",
}
UNIT_TITLE = {"inside": "Flats inside the shop", "useful": "Useful area", "bedroom": "Bedrooms", "living": "Living room", "windows": "Windows",
              "facade": "Façade", "height": "Clear height", "bath": "Bathroom",
              "wet_height": "Height, wet rooms", "living_facade": "Living room on the façade", "hall": "Hall width",
              "exterior": "Façade on the street or block interior", "patio": "Patio inside the flat", "evac": "Escape route",
              "corridor": "Shared corridor", "access": "Entrance"}


def _inside(x, y, poly):
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def _seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def daylight(outline, facade, cell=0.5, lit_depth=LIT_DEPTH, service_depth=SERVICE_DEPTH):
    """Grid cells inside the outline with their distance to the nearest façade and their band."""
    pts = outline[:-1] if outline[0] == outline[-1] else outline
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cells, tot = [], {"lit": 0.0, "service": 0.0, "dark": 0.0}
    nx, ny = int(math.ceil((max(xs) - min(xs)) / cell)), int(math.ceil((max(ys) - min(ys)) / cell))
    for i in range(nx):
        for j in range(ny):
            x0, y0 = min(xs) + i * cell, min(ys) + j * cell
            cx, cy = x0 + cell / 2, y0 + cell / 2
            if not _inside(cx, cy, pts):
                continue
            d = min(_seg_dist(cx, cy, a, b) for a, b in facade) if facade else 1e9
            band = "lit" if d <= lit_depth else ("service" if d <= lit_depth + service_depth else "dark")
            tot[band] += cell * cell
            cells.append((x0, y0, x0 + cell, y0 + cell, d, band))
    total = sum(tot.values()) or 1.0
    return {"cells": cells, "cell": cell, "lit_depth": lit_depth, "service_depth": service_depth,
            "area": dict((k, round(v, 1)) for k, v in tot.items()),
            "share": dict((k, round(v / total, 3)) for k, v in tot.items()),
            "max_depth": round(max([c[4] for c in cells] or [0]), 1)}


def band_colour(d, lit_depth=LIT_DEPTH, service_depth=SERVICE_DEPTH):
    """Light-penetration colour (r, g, b), kept very light so the plan stays readable:
    pale sun-yellow at the window, white at the end of the lit band, soft blue-grey where it is dark. No orange."""
    def mix(a, b, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
    if d <= lit_depth:
        return mix((255, 241, 196), (255, 253, 246), d / lit_depth)
    if d <= lit_depth + service_depth:
        return mix((252, 252, 250), (236, 239, 243), (d - lit_depth) / service_depth)
    return mix((228, 233, 240), (210, 219, 230), (d - lit_depth - service_depth) / 6.0)


# Room colours used everywhere (plans, 3D, Rhino, slides) - the scheme of the first generated plans (lab book E05)
ROOM_RGB = {"living": (240, 159, 38), "bed_main": (128, 120, 222), "bed": (176, 168, 237), "kitchen": (250, 199, 117),
            "bath": (133, 184, 235), "hall": (204, 204, 204)}
FAIL_RGB, FACADE_RGB, PATIO_RGB, CORRIDOR_RGB = (227, 74, 74), (44, 93, 143), (196, 224, 244), (222, 222, 218)
VERDICT_RGB = {"YES": (63, 143, 90), "PARTLY": (201, 138, 43), "NO": (196, 71, 58)}


def _centre(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def cards(outline, facade, height, plan):
    """Rule cards: the shell checks, then the flat checks (first failing flat, else the first flat)."""
    out = []
    c = _centre(outline[:-1] if outline[0] == outline[-1] else outline)
    fac_len = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in facade)
    longest = max(facade, key=lambda s: math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1])) if facade else None
    fac_pt = ((longest[0][0] + longest[1][0]) / 2, (longest[0][1] + longest[1][1]) / 2) if longest else c
    out.append({"rule": "height", "title": "Clear height", "ok": height >= MIN_HEIGHT, "value": "%.2f m" % height,
                "limit": ">= 2,40 m", "cite": SHELL_CITE["height"], "at": c, "scope": "shop"})
    out.append({"rule": "facade", "title": "Façade with windows", "ok": fac_len >= 3.0, "value": "%.1f m" % fac_len,
                "limit": ">= 3 m", "cite": SHELL_CITE["facade"], "at": fac_pt, "scope": "shop"})
    req = plan.get("requested", 0)
    out.append({"rule": "density", "title": "Number of flats", "ok": plan["density_ok"],
                "value": "%d placed, %d allowed" % (plan.get("placed", 0), plan["density_cap"]), "limit": "(built m² / 80)",
                "cite": SHELL_CITE["density"], "at": c, "scope": "shop"})
    un_pl = plan.get("unplaced", [])
    out.append({"rule": "fit", "title": "Flats that fit", "ok": not un_pl and req > 0,
                "value": "%d of %d asked fit" % (plan.get("placed", 0), req) + ("; no room for %s" % (
                    ", ".join(sorted(set(x["type"].replace("bed", "-bed") for x in un_pl)))) if un_pl else ""),
                "limit": "", "cite": "NOMAD generator (Stage 6)", "at": fac_pt, "scope": "shop"})
    units = plan.get("units", [])
    if units:
        out.append(inside_card(outline, units))
        rooms_for = {"bedroom": ("bed", "bed_main"), "living": ("living",), "windows": ("living", "bed", "bed_main"), "bath": ("bath",),
                     "living_facade": ("living",), "hall": ("hall",)}
        order = []
        for un in units:
            for ch in un.get("checks", []):
                if ch["rule"] not in order and ch["rule"] not in ("height", "facade", "wet_height"):
                    order.append(ch["rule"])
        for rule in order:
            per = []                                   # (unit index, ok, text, cite)
            for i, un in enumerate(units):
                same = [x for x in un.get("checks", []) if x["rule"] == rule]
                if same:
                    bad = [x for x in same if not x["ok"]]
                    per.append((i, not bad, (bad or same)[0]["text"], same[0]["cite"]))
            if not per:
                continue
            n_ok = sum(1 for p in per if p[1])
            worst = [p for p in per if not p[1]] or per[:1]
            i = worst[0][0]
            un = units[i]
            kinds = rooms_for.get(rule, ())
            rm = [r for r in un["rooms"] if r["kind"] in kinds and len(r["pts"]) >= 3]
            rm_bad = [r for r in rm if not r.get("ok", True)]
            at = _centre((rm_bad or rm)[0]["pts"]) if rm else (_centre(un["outline"]) if len(un["outline"]) >= 3 else c)
            out.append({"rule": rule, "title": UNIT_TITLE.get(rule, rule), "ok": n_ok == len(per),
                        "value": ("%d of %d flats pass" % (n_ok, len(per))) if n_ok == len(per) else
                                 ("%d of %d flats pass; F%d: %s" % (n_ok, len(per), i + 1, worst[0][2])),
                        "limit": "", "cite": worst[0][3].split(" (")[0], "at": at, "scope": "flat"})
    return out


def _near_edge(x, y, poly, tol):
    n = len(poly)
    return any(_seg_dist(x, y, poly[i], poly[(i + 1) % n]) <= tol for i in range(n))


def inside_card(outline, units, tol=0.15):
    """NOMAD geometry check: every room corner must lie inside the shop outline (within 15 cm).
    A flat that does not is marked as failing ("outside")."""
    poly = outline[:-1] if outline[0] == outline[-1] else outline
    bad = []
    for i, un in enumerate(units):
        out_pts = [p for r in un["rooms"] for p in r["pts"] if not (_inside(p[0], p[1], poly) or _near_edge(p[0], p[1], poly, tol))]
        if out_pts:
            bad.append((i, out_pts[0]))
            un["ok"] = False
            un["fails"] = sorted(set(un.get("fails", []) + ["outside"]))
    at = bad[0][1] if bad else _centre(poly)
    return {"rule": "inside", "title": "Flats inside the shop", "ok": not bad,
            "value": ("%d of %d flats inside" % (len(units) - len(bad), len(units))) + ("; F%d crosses the outline" % (bad[0][0] + 1) if bad else ""),
            "limit": "", "cite": "NOMAD geometry check (not a law)", "at": at, "scope": "flat"}


def zoning_card(z, at):
    """Step 3: the zone of the shop's address (src/zoning/zoning.py; MUC zoning, Generalitat) and what it allows.
    z: {"zone", "pgm_key", "housing": YES / CHECK / NO, "why"}."""
    return {"rule": "zoning", "title": "Zoning", "ok": z["housing"] == "YES", "check": z["housing"] == "CHECK",
            "value": "%s%s: %s" % (z["zone"], (" (key %s)" % z["pgm_key"]) if z.get("pgm_key") else "", z["why"]),
            "limit": "housing on the ground floor", "cite": "PGM art. 225.7 (MPGM 1999); zone from the MUC (Generalitat)",
            "at": at, "scope": "shop"}


def verdict(plan, shell_cards):
    shell_ok = all(c["ok"] for c in shell_cards if c["scope"] == "shop" and c["rule"] in ("height", "facade"))
    passing = sum(1 for u in plan.get("units", []) if u.get("ok"))
    zone = [c for c in shell_cards if c["rule"] == "zoning"]
    if zone and not zone[0]["ok"] and not zone[0].get("check"):
        return "NO"                                        # the zone does not take housing: nothing else matters
    if not shell_ok or passing == 0:
        return "NO"
    if zone and zone[0].get("check"):
        return "PARTLY"                                    # the zone's own plan must confirm
    return "YES" if plan.get("proposal_ok") else "PARTLY"


def analyse(outline, facade, height, plan, lit_depth=LIT_DEPTH, cell=0.5, zoning=None):
    """Everything Stage 5 shows, in one dict (also written as JSON next to each sheet).
    Patios cut by Stage 6 (plan["patios"]) light the floor too and count as façade with windows."""
    light = list(facade)
    for pt in plan.get("patios", []):
        q = pt["pts"]
        light += [[list(q[i]), list(q[(i + 1) % len(q)])] for i in range(len(q))]
    day = daylight(outline, light, cell=cell, lit_depth=lit_depth)
    for pt in plan.get("patios", []):                       # patio floor is open air, not floor area
        q = pt["pts"]
        keep = [c for c in day["cells"] if not _inside((c[0] + c[2]) / 2, (c[1] + c[3]) / 2, q)]
        gone = [c for c in day["cells"] if c not in keep]
        for c in gone:
            day["area"][c[5]] = round(day["area"][c[5]] - day["cell"] ** 2, 1)
        day["cells"] = keep
    total = sum(day["area"].values()) or 1.0
    day["share"] = dict((k, round(v / total, 3)) for k, v in day["area"].items())
    cs = cards(outline, light, height, plan)
    if zoning:                                             # Step 3 first: can this address take housing at all?
        cs.insert(0, zoning_card(zoning, _centre(outline[:-1] if outline[0] == outline[-1] else outline)))
    v = verdict(plan, cs)
    units = plan.get("units", [])
    return {"verdict": v, "daylight": day, "cards": cs,
            "flats_placed": len(units), "flats_passing": sum(1 for u in units if u.get("ok")),
            "flats_asked": plan.get("requested", 0),
            "shop_m2": round(area(outline[:-1] if outline[0] == outline[-1] else outline), 1),
            "housing_m2": round(sum(u.get("area_m2", 0) for u in units), 1),
            "interventions": plan.get("interventions", []), "patio_m2": round(sum(p["area"] for p in plan.get("patios", [])), 1)}


def summary_text(res):
    d = res["daylight"]
    lines = ["VERDICT: %s  (%d of %d flats asked pass every rule)" % (res["verdict"], res["flats_passing"], res["flats_asked"]),
             "Shop %.0f m2: lit %.0f m2 (%.0f%%), service %.0f m2 (%.0f%%), dark %.0f m2 (%.0f%%); deepest point %.1f m from a window"
             % (res["shop_m2"], d["area"]["lit"], 100 * d["share"]["lit"], d["area"]["service"], 100 * d["share"]["service"],
                d["area"]["dark"], 100 * d["share"]["dark"], d["max_depth"]),
             "Lit band = %.1f m from a window (design assumption, not a law)" % d["lit_depth"], "Rule cards:"]
    for c in res["cards"]:
        lines.append("  [%s] %s: %s %s  - %s" % ("OK" if c["ok"] else "FAIL", c["title"], c["value"], c["limit"], c["cite"]))
    return "\n".join(lines)
