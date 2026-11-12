# -*- coding: utf-8 -*-
"""Nomad Stage 6: better plans by the smallest intervention (plain Python: Grasshopper + Python 3).

Idea (from the team's slide "Pasul 5"): try the shop as it is; if the flats asked for do not all fit and
pass, add one intervention at a time and keep the variant that houses the most passing flats with the
fewest changes:
  0. as it is                     flats only along the existing façades (layout.generate)
  1. + patio(s) + shared corridor  cut a light patio in the dark interior; its sides become new façades
                                   for "back flats"; a shared corridor links the street to the patio.
Rules used (from the Nomad rulebook):
  patio      Decret 141/2012 Annex 1 2.5.1: a patio that lights rooms fits a 3 m circle and is >= 9 m²
             (up to 3 floors of patio height). Sides tried: 4,5 / 6,0 / 7,5 m.
  corridor   CTE DB-SUA Anejo A (itinerario accesible): clear width >= 1,20 m.
Assumptions (stated on every sheet): the patio can be cut through the roof of the ground floor (true for the
rear part of most deep Barcelona locales, which lies in the block interior with no floors above - check on
site); a room lit by a patio of that size counts as having a façade (to confirm with the authority);
every flat must touch the street or the corridor (access).
"""
import math
import layout

PATIO_SIDES = (4.5, 6.0, 7.5)
CORRIDOR_W = 1.20
CITE = {"patio": "Decret 141/2012 Annex 1 2.5.1 (3 m circle, >= 9 m²)",
        "corridor": "CTE DB-SUA Anejo A (accessible route >= 1,20 m)"}


def _inside(x, y, poly):
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def _main_frame(outline, facade):
    g = layout.facade_groups(facade)[0]
    fr = g["frame"]
    cx, cy = layout.centroid(outline)
    if (cx - fr.ox) * fr.vx + (cy - fr.oy) * fr.vy < 0:
        fr.vx, fr.vy = -fr.vx, -fr.vy
    spans = layout.facade_intervals(fr, g["segs"])
    return fr, spans


def _depth_profile(local, u):
    cuts = []
    n = len(local)
    for i in range(n):
        a, b = local[i - 1], local[i]
        if (a[0] - u) * (b[0] - u) <= 0 and a[0] != b[0]:
            t = (u - a[0]) / (b[0] - a[0])
            cuts.append(a[1] + t * (b[1] - a[1]))
    cuts = [c for c in cuts if c > 0.3]
    return min(cuts) if cuts else 0.0


def _poly_inside(pts, outline, margin=0.0):
    return all(_inside(x, y, outline) for x, y in pts)


def candidates(outline, facade):
    """Patio + corridor candidates in the main street frame: patio centred on a line into the shop."""
    poly = outline[:-1] if outline[0] == outline[-1] else outline
    fr, spans = _main_frame(poly, facade)
    local = [fr.to_local(p) for p in poly]
    us = [p[0] for p in local]
    out = []
    for P in PATIO_SIDES:
        for k in (0.5, 0.25, 0.75, 0.125, 0.875):
            u = min(us) + k * (max(us) - min(us))
            D = _depth_profile(local, u)
            v0 = layout.FRONT_MAX + 2.2 + 0.6                     # behind the street flats' lit + service bands
            if D < v0 + P + 5.0:                                  # room for flats behind the patio too
                continue
            v0 = max(v0, (D - P) / 2.0 - 1.0)                     # roughly centred in the dark zone
            rect = [(u - P / 2, v0), (u + P / 2, v0), (u + P / 2, v0 + P), (u - P / 2, v0 + P)]
            corr = [(u - CORRIDOR_W / 2, -0.5), (u + CORRIDOR_W / 2, -0.5), (u + CORRIDOR_W / 2, v0), (u - CORRIDOR_W / 2, v0)]
            patio_w = [fr.to_world(p) for p in rect]
            if not _poly_inside(patio_w, poly):
                continue
            out.append({"side": P, "kind": "patio", "u": round(u, 2), "patio": patio_w, "corridors": [[fr.to_world(p) for p in corr]],
                        "centre": fr.to_world((u, v0 + P / 2))})
    return out


BAND_DEPTHS = (3.6, 4.5)                                     # cross patio depth (fits the 3 m circle)
STREET_BAND = layout.FRONT_MAX + 2.2 + 0.3                     # depth the street flats use


def band_candidates(outline, facade):
    """Cross patios: a light patio across the width of the shop, a 1,20 m corridor along one side from the
    street to behind it, and back flats facing the patio like a second street. Repeated deeper (k = 0, 1, 2)."""
    poly = outline[:-1] if outline[0] == outline[-1] else outline
    fr, spans = _main_frame(poly, facade)
    local = [fr.to_local(p) for p in poly]
    us = [p[0] for p in local]
    out = []
    starts = []
    for P in BAND_DEPTHS:
        starts += [(P, 2.0)]                                   # patio right behind a 2 m shared entrance
        starts += [(P, STREET_BAND + k * (P + CORRIDOR_W + STREET_BAND)) for k in range(3)]
    for P, v0 in starts:
        if True:
            need = v0 + P + CORRIDOR_W + 5.5                   # gallery + back flats >= 5,5 m behind the patio
            run, best = [], []
            u = min(us) + 0.15
            while u <= max(us) - 0.15:                         # longest run of u where the shop is deep enough
                if _depth_profile(local, u) >= need:
                    run.append(u)
                else:
                    if len(run) > len(best):
                        best = run
                    run = []
                u += 0.25
            if len(run) > len(best):
                best = run
            if not best or best[-1] - best[0] < CORRIDOR_W + 6.5:
                continue
            ua, ub = best[0], best[-1]
            for left in (True, False):                          # corridor along either side wall
              cu0, cu1 = (ua, ua + CORRIDOR_W) if left else (ub - CORRIDOR_W, ub)
              pu0, pu1 = (cu1, ub) if left else (ua, cu0)
              rect = [(pu0, v0), (pu1, v0), (pu1, v0 + P), (pu0, v0 + P)]
              g0, g1 = v0 + P, v0 + P + CORRIDOR_W                # gallery along the back of the patio
              corr = [(cu0, -0.5), (cu1, -0.5), (cu1, g1), (cu0, g1)]
              gallery = [(pu0, g0), (pu1, g0), (pu1, g1), (pu0, g1)]
              patio_w = [fr.to_world(q) for q in rect]
              if not _poly_inside(patio_w, poly):
                  continue
              out.append({"side": P, "kind": "cross patio", "u": round((pu0 + pu1) / 2, 2), "v0": round(v0, 2),
                          "length": round(pu1 - pu0, 2), "patio": patio_w,
                          "corridors": [[fr.to_world(q) for q in corr], [fr.to_world(q) for q in gallery]],
                          "centre": fr.to_world(((pu0 + pu1) / 2, v0 + P / 2)),
                          "front_only": [[list(fr.to_world((pu0, g1))), list(fr.to_world((pu1, g1)))]]})
    return out


def _touches(poly_a, poly_b, tol=0.35):
    """True when two polygons come within tol of each other (vertex-to-edge)."""
    def d(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-12
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
    for P, Q in ((poly_a, poly_b), (poly_b, poly_a)):
        for p in P:
            for i in range(len(Q)):
                if d(p, Q[i], Q[(i + 1) % len(Q)]) <= tol:
                    return True
    return False


def _plan_with(outline, facade, height, mix, programs, size, patios):
    """Run the generator with these patios (+ their corridors) cut in."""
    blocked, extra = [], []
    for c in patios:
        blocked += [c["patio"]] + c["corridors"]
        pts = c["patio"]
        segs = c.get("front_only") or [[list(pts[i]), list(pts[(i + 1) % 4])] for i in range(4)]
        for seg in segs:
            extra.append((seg, c["centre"]))
    plan = None
    for small_first in (False, True):                        # big flats first, or small flats first: keep the better
        p = layout.generate(outline, facade, height, mix, programs, size, blocked=blocked, extra_fronts=extra, small_first=small_first)
        if plan is None or (p["compliant"], -len(p["unplaced"])) > (plan["compliant"], -len(plan["unplaced"])):
            plan = p
    # access: a patio flat must touch a corridor or another flat that touches the street (no locked-in flats)
    for u in plan["units"]:
        if u.get("on_patio") and len(u["outline"]) >= 3:
            ok = any(_touches(u["outline"], q) for c in patios for q in c["corridors"])
            if not ok:
                u["ok"] = False
                u["fails"] = sorted(set(u.get("fails", []) + ["access"]))
                u.setdefault("checks", []).append({"rule": "access", "ok": False, "text": "no door to the street or corridor",
                                                   "cite": "NOMAD access check (not a law)"})
    plan["compliant"] = sum(1 for u in plan["units"] if u["ok"])
    plan["proposal_ok"] = plan["requested"] > 0 and not plan["unplaced"] and plan["compliant"] == plan["requested"] and plan["density_ok"]
    plan["patios"] = [{"side": c["side"], "kind": c["kind"], "pts": c["patio"],
                       "area": round(layout.area(c["patio"]), 1)} for c in patios]
    plan["corridors"] = [{"pts": q, "width": CORRIDOR_W} for c in patios for q in c["corridors"]]
    plan["interventions"] = (["%s (%s m²) - %s" % (", ".join(c["kind"] for c in patios),
                                                    " + ".join("%.0f" % layout.area(c["patio"]) for c in patios), CITE["patio"]),
                              "shared corridor %.2f m wide - %s" % (CORRIDOR_W, CITE["corridor"])] if patios else [])
    return plan


def _score(plan):
    return (1 if plan["proposal_ok"] else 0, plan["compliant"], -len(plan.get("patios", [])),
            -sum(p["area"] for p in plan.get("patios", [])))     # fewest, then smallest patios win a tie


def improve(outline, facade, height, mix, programs, size="typical", max_patios=3):
    """Best plan: as it is, or with 1..max_patios patios + corridors. Returns (best, before, tried)."""
    before = _plan_with(outline, facade, height, mix, programs, size, [])
    best, chosen, tried = before, [], 1
    if before["proposal_ok"]:
        best["stage6"] = "as it is: no change needed"
        return best, before, tried
    for _ in range(max_patios):
        step_best = None
        for c in candidates(outline, facade) + band_candidates(outline, facade):
            if any(_overlaps(c, o) for o in chosen):
                continue
            p = _plan_with(outline, facade, height, mix, programs, size, chosen + [c])
            tried += 1
            if step_best is None or _score(p) > _score(step_best[0]):
                step_best = (p, c)
        if step_best is None or step_best[0]["compliant"] <= best["compliant"]:
            break                                            # one more patio no longer helps: stop
        best, chosen = step_best[0], chosen + [step_best[1]]
        if best["proposal_ok"]:
            break
    best["stage6"] = ("as it is: no intervention helped" if not chosen else
                      "%d patio%s + corridor: %d -> %d passing flats" % (len(chosen), "s" if len(chosen) > 1 else "",
                                                                         before["compliant"], best["compliant"]))
    return best, before, tried


def _overlaps(c1, c2):
    """Two patios too close: they need a band of flats (>= 5,5 m) between them."""
    if c1.get("kind") == "cross patio" and c2.get("kind") == "cross patio":
        return abs(c1["v0"] - c2["v0"]) < c1["side"] + 5.5
    d = math.hypot(c1["centre"][0] - c2["centre"][0], c1["centre"][1] - c2["centre"][1])
    return d < (c1["side"] + c2["side"]) / 2.0 + 7.0


def most_homes(outline, facade, height, programs, size="compact", patios=True):
    """Iteration "most homes": as many flats as fit and pass every rule. Tries k x 1-bed and k x studio
    (k = 1 .. the Barcelona density cap), with the Stage 6 changes allowed; keeps the most passing homes
    (a tie goes to 1-beds, the bigger flat). Returns (plan, before, tried)."""
    cap = int(math.ceil(layout.area(outline) / 0.9 / 80.0 - 1e-9))
    best, tried = None, 0
    for t in ("1bed", "studio"):
        last = 0
        for k in range(1, max(cap, 1) + 1):
            if patios:
                p, before, n = improve(outline, facade, height, {t: k}, programs, size)
            else:
                p = before = _plan_with(outline, facade, height, {t: k}, programs, size, [])
                n = 1
            tried += n
            key = (p["compliant"], 1 if t == "1bed" else 0)
            if best is None or key > best[0]:
                best = (key, p, before)
            if p["compliant"] < k - 1 or p["compliant"] <= last and k > last + 2:
                break                                       # more flats asked no longer fit: stop
            last = max(last, p["compliant"])
    plan = best[1]
    plan["stage6"] = "most homes: %d flats (%s)" % (plan["compliant"], plan.get("stage6", ""))
    return plan, best[2], tried
