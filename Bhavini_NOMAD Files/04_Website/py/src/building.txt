# -*- coding: utf-8 -*-
"""Nomad - whole buildings: an empty warehouse (nau), commercial or office building turned into homes.

A whole building is Decret 141/2012 Annex 4 Group B (total change of use): Annex 1 applies, with a 10 % reduction on
the patio surfaces (2.5.1) and a 2,40 m minimum clear height (3.5); unlike a shop (Group C), the building rules of Annex 1
section 2 apply too. NOMAD:
  storeys   a warehouse with room for two storeys of 2,40 m plus a floor slab gets a mezzanine (two levels of homes);
            a commercial or office building keeps its Catastro storeys
  patios    a building deeper than one row of flats and its hall gets patios cut through it (3 m circle, 2.5.1), each
            with a passage across to join the parts; the flats behind are lit from the patio
  floors    each part is laid out with real plans (plan3) and the same plan is stacked on every storey
  core      with more than one level, each street door becomes a core: a stair of two 1,00 m flights (CTE DB-SUA SUA 1
            Table 4.1) and a lift with a 1,00 x 1,25 m cabin (DB-SUA Annex A), the 1,50 m circle in front of it
            (Annex 1 2.2.2), and the community room when there are 8 homes or more (2.6)
  checks    Annex 1 section 2: accessible route (2.1), access through a common space and lift landing (2.2), stairs
            (2.3, CTE), lift and second lift (2.4.1, 2.4.2, CTE DB-SUA SUA 9), patios (2.5.1), community room (2.6)
Assumptions (not law), marked as such: floor slab 0,30 m; 0,20 m between the two flights; lift shaft 1,60 x 1,70 m;
3,0 m storeys in commercial and office buildings.
Plain Python (Grasshopper IronPython 2.7, browser): no f-strings, no shapely.
"""
import math

import layout
import plan2
import plan3

CITE = {
    "group_b": "Decret 141/2012 Annex 4 apartat 2, Group B (total change of use of a building)",
    "height": "Decret 141/2012 Annex 4 Group B: Annex 1 3.5 with a 2,40 m minimum clear height",
    "route": "Decret 141/2012 Annex 1 2.1 (an accessible route to every home)",
    "access": "Decret 141/2012 Annex 1 2.2.1 and 2.2.2 (access through a common space; 1,50 m circle in front of the lift)",
    "stairs": "Decret 141/2012 Annex 1 2.3; CTE DB-SUA SUA 1 4.2 (flights >= 1,00 m, going >= 28 cm, riser <= 17,5 cm)",
    "lift": "Decret 141/2012 Annex 1 2.4.1; CTE DB-SUA SUA 9 1.1.2 (lift when more than two storeys are climbed or more than 12 homes are off the entry floor)",
    "lift2": "Decret 141/2012 Annex 1 2.4.2 (a second lift by storeys and homes above the ground floor)",
    "patio": "Decret 141/2012 Annex 1 2.5.1 (patio lighting rooms: 3 m circle, 9 m², +1,80 m² per storey over 3; Group B: surfaces -10 %)",
    "community": "Decret 141/2012 Annex 1 2.6 (community room from 8 homes: 1,20 x 0,80 m, +0,05 m² per home over 12)",
}
MIN_H = 2.40                 # Annex 4 Group B (Annex 1 3.5 at 2,40 m)
SLAB = 0.30                  # floor slab of a new mezzanine (assumption)
STAIR_W = 1.00               # CTE DB-SUA SUA 1 Table 4.1 (residential)
CORE_W = 2 * STAIR_W + 0.20  # two flights and the gap between them (gap: assumption)
GOING, RISER = 0.28, 0.175   # CTE DB-SUA SUA 1 4.2.1
LIFT = (1.60, 1.70)          # lift shaft for a 1,00 x 1,25 m cabin (DB-SUA Annex A); shaft size: assumption
LANDING = 1.50               # Annex 1 2.2.2
PATIO_W = 3.0                # Annex 1 2.5.1: 3 m circle when it lights rooms
PASS = 1.50                  # passage across a patio (CTE DB-SUA Annex A: 1,50 m circle in the vestibule, route >= 1,20 m)
SECOND_LIFT = [(3, 32), (4, 28), (5, 26), (6, 24), (7, 21), (8, 16)]   # Annex 1 2.4.2: PB+n -> more than this many homes above PB
STOREY = {"commercial": 3.0, "office": 3.0}                            # m, assumption (Catastro gives no height)


def levels_of(kind, floors, clear_h):
    """(levels of homes, storey height). A warehouse: one level, or two (a mezzanine) when two 2,40 m storeys and a slab
    fit in its clear height. Commercial / office: the Catastro storeys at 3,0 m."""
    if kind == "warehouse":
        if clear_h >= 2 * MIN_H + SLAB:
            return 2, round((clear_h + SLAB) / 2.0, 2)
        return 1, clear_h
    return max(1, int(floors or 1)), STOREY.get(kind, 3.0)


def core_depth(storey_h):
    """Depth of a core: landing in front of the lift + two flights for one storey + the half landing + the lift shaft."""
    risers = int(math.ceil(storey_h / RISER))
    flight = (int(math.ceil(risers / 2.0)) - 1) * GOING
    return round(LANDING + flight + STAIR_W + LIFT[1], 2)


# ---------- patios: split a deep building into parts ----------
def split(outline, facade, street, D=7.0, cw=1.2, min_back=6.0):
    """Cut patios across a building deeper than one row of flats and its hall. Returns (parts, patios, passages):
    parts = [{"outline", "facade", "street", "offset"}] (offset = metres from the street to this part's façade),
    patios / passages = world polygons."""
    fronts = plan2._fronts(outline, facade, street)
    if not fronts:
        return [{"outline": outline, "facade": facade, "street": street, "offset": 0.0}], [], []
    fr = fronts[0].frame
    loc = fronts[0].local
    us, vs = [p[0] for p in loc], [p[1] for p in loc]
    u0, u1, vmax = min(us) - 1.0, max(us) + 1.0, max(vs)
    band = D + cw
    cuts, v = [], 0.0
    while vmax - (v + band + PATIO_W) >= min_back:          # room behind the patio for another row of flats
        cuts.append((v + band, v + band + PATIO_W))
        v = v + band + PATIO_W
    if not cuts:
        return [{"outline": outline, "facade": facade, "street": street, "offset": 0.0}], [], []
    W = lambda q: [fr.to_world(p) for p in q]
    parts, patios, passages = [], [], []
    edges = [0.0] + [c for ab in cuts for c in ab] + [vmax + 1.0]
    for k in range(len(cuts) + 1):
        a, b = edges[2 * k], edges[2 * k + 1]
        q = layout.clip(loc, (u0, a - (1.0 if k == 0 else 0.0), u1, b))
        if len(q) < 3 or layout.area(q) < 20.0:
            continue
        if k == 0:
            parts.append({"outline": W(q), "facade": facade, "street": street, "offset": 0.0, "k": 0})
        else:
            seg = [(p, r) for p, r in zip(q, q[1:] + q[:1]) if abs(p[1] - a) < 1e-6 and abs(r[1] - a) < 1e-6]
            fac = [[fr.to_world(p), fr.to_world(r)] for p, r in seg]
            own = _street_in(fr, street, a, b)           # a second street here: this part gets its own street door
            if own:
                parts.append({"outline": W(q), "facade": own + fac, "street": own, "offset": 0.0, "k": k, "own_door": True})
            elif fac:
                parts.append({"outline": W(q), "facade": fac, "street": fac, "offset": a, "k": k})
    for k, (a, b) in enumerate(cuts):
        q = layout.clip(loc, (u0, a, u1, b))
        if len(q) < 3:
            continue
        qu = [p[0] for p in q]
        pu = max(qu) - PASS                                # the passage runs along one side of the patio
        pat = layout.clip(loc, (min(qu), a, pu, b))
        pas = layout.clip(loc, (pu, a, max(qu), b))
        if len(pat) >= 3:
            patios.append({"pts": W(pat), "area": round(layout.area(pat), 1), "side": PATIO_W, "kind": "patio cut through the building", "k": k + 1})
        if len(pas) >= 3:
            passages.append({"pts": W(pas), "width": PASS, "length": PATIO_W, "name": "passage across the patio", "k": k + 1})
    return parts, patios, passages


def _street_in(fr, street, a, b, min_len=3.0):
    """The pieces of the building's street façades between depths a and b of the main frame (a side street on a corner,
    or the street at the back of a building through the block), at least min_len long."""
    out = []
    for p, r in street:
        lp, lr = fr.to_local(p), fr.to_local(r)
        if lp[1] < 0.5 and lr[1] < 0.5:
            continue                                     # the main street itself
        (x0, y0), (x1, y1) = lp, lr
        if abs(y1 - y0) < 1e-6:
            if not (a - 0.5 <= y0 <= b + 0.5):
                continue
            q0, q1 = lp, lr
        else:
            t0 = max(0.0, min(1.0, (a - y0) / (y1 - y0)))
            t1 = max(0.0, min(1.0, (b - y0) / (y1 - y0)))
            q0 = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0)
            q1 = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
        if math.hypot(q1[0] - q0[0], q1[1] - q0[1]) >= min_len:
            out.append([fr.to_world(q0), fr.to_world(q1)])
    return out


# ---------- one layout of the whole building ----------
def _best(outline, facade, street, height, mix, sizes, weights, evac_max, lit=None):
    """plan3 on one part; the iteration with most legal homes."""
    keep = plan3.EVAC_MAX
    plan3.EVAC_MAX = evac_max
    try:
        _, its, _ = plan3.iterations(outline, facade, height, mix, street=street, sizes=sizes, weights=weights,
                                     lit_depth=lit or 5.5, lit_source="bars" if lit else None)
    finally:
        plan3.EVAC_MAX = keep
    its = [(n, p) for n, p, _ in its if p.get("units")]
    if not its:
        return None, None
    return max(its, key=lambda x: (x[1]["compliant"], len(x[1]["units"])))


def layouts(shell, mix, clear_h, sizes=None, weights=None):
    """The building's layouts: [(name, plan)]; each plan carries levels, storey_h, cores and the Group B checks."""
    kind = shell.get("kind", "warehouse")
    lv, sh = levels_of(kind, shell.get("floors"), clear_h)
    o, f, st = shell["outline"], shell["facade"], shell.get("street") or shell["facade"]
    keep = (plan3.LOBBY, plan3.DEPTHS, plan3.STRATEGIES, plan3.SHALLOW)
    if lv > 1:                                           # each street door becomes a stair + lift core: deep enough for it,
        plan3.LOBBY = CORE_W                             # and no passage layouts (a passage has no core)
        plan3.DEPTHS = tuple(d for d in plan3.DEPTHS if d + 1.2 >= core_depth(sh)) or (plan3.DEPTHS[-1],)
        plan3.STRATEGIES = [x for x in plan3.STRATEGIES if not x[1].get("through")]
        plan3.SHALLOW = ()
    out = []
    try:
        n0, p0 = _best(o, f, st, sh, mix, sizes, weights, plan3.EVAC_MAX, shell.get("lit_depth"))
        if p0:
            out.append(("whole floor, " + n0, p0))
        parts, patios, passages = split(o, f, st)
        if patios:
            plan = {"units": [], "corridors": [], "patios": patios, "existing": [], "interventions": [], "unplaced": []}
            used = 0                                     # a patio is kept only if the part behind it gets homes
            for pt in parts:
                n, p = _best(pt["outline"], pt["facade"], pt["street"], sh, mix, sizes, weights,
                             plan3.EVAC_MAX - pt["offset"] - PASS, shell.get("lit_depth"))
                if p and any(u.get("ok") for u in p["units"]):
                    plan["units"] += p["units"]
                    plan["corridors"] += p.get("corridors", [])
                    used = max(used, pt["k"])
            plan["patios"] = [x for x in patios if x["k"] <= used]
            patios = plan["patios"]
            plan["corridors"] += [x for x in passages if x["k"] <= used]
            plan["interventions"] = ["%d patio%s cut through the building (3 m wide, %s), each with a %.2f m passage across" % (
                len(patios), "" if len(patios) == 1 else "s", CITE["patio"].split(" (")[0], PASS)]
            if any(pt.get("own_door") and pt["k"] <= used for pt in parts):
                plan["interventions"].append("a second street door on the other street for the part behind the patio "
                                             "(every home within 25 m of a street door, CTE DB-SI SI 3)")
            plan["compliant"] = sum(1 for u in plan["units"] if u.get("ok"))
            plan["params"] = {"fill": False, "patios": True}
            if plan["units"] and patios:
                out.append(("patios cut through the building", plan))
    finally:
        plan3.LOBBY, plan3.DEPTHS, plan3.STRATEGIES, plan3.SHALLOW = keep
    for _, p in out:
        p["levels"], p["storey_h"], p["kind"] = lv, sh, kind
        p["cores"] = [c for c in p.get("corridors", []) if str(c.get("name", "")).startswith(("lobby", "the building"))]
        if lv > 1:
            for c in p["cores"]:
                c["name"] = "core: stair + lift"
        p["building_checks"] = checks(p, clear_h)
    return out


def checks(plan, clear_h):
    """Annex 1 section 2 for a whole building (Group B) -> [{rule, ok, text, cite}]."""
    lv, sh = plan["levels"], plan["storey_h"]
    homes_floor = sum(1 for u in plan["units"] if u.get("ok"))
    homes = homes_floor * lv
    above = homes_floor * (lv - 1)
    cores = max(1, len(plan.get("cores", [])))
    out = []
    clear = sh - (SLAB if lv > 1 else 0.0)
    out.append(("height", clear >= MIN_H - 1e-6, "clear height %.2f m per level (%d level%s)" % (clear, lv, "" if lv == 1 else "s"), "height"))
    if lv > 1:
        need_lift = (lv - 1) > 2 or above > 12
        out.append(("lift", True, "lift in every core%s" % ("" if need_lift else " (only space for it is required here)"), "lift"))
        out.append(("access", True, "core %.2f m wide: 1,50 m circle in front of the lift" % CORE_W, "access"))
        out.append(("route", True, "accessible route: street door, core and lift to every home", "route"))
        cd = core_depth(sh)
        room = min([c.get("length", 0) for c in plan.get("cores", [])] or [0])
        out.append(("stairs", room >= cd - 1e-6 or not plan.get("cores"), "stair of two 1,00 m flights: core %.1f m deep, needs %.1f m" % (room, cd), "stairs"))
        lim = [m for p_, m in SECOND_LIFT if p_ == lv - 1]
        two = (lv - 1) >= 9 or (lim and above / float(cores) > lim[0])
        out.append(("lift2", not two, "%d homes above the ground floor per core: %s" % (int(above / cores), "needs a second lift" if two else "one lift is enough"), "lift2"))
    else:
        out.append(("route", True, "every home on the entry level: accessible route from the street", "route"))
    for pt in plan.get("patios", []):
        need = (9.0 + 1.80 * max(0, lv - 3)) * 0.9
        ok = pt["side"] >= PATIO_W - 1e-6 and pt["area"] >= need - 1e-6
        out.append(("patio", ok, "patio %.1f m² and %.1f m wide (needs %.1f m², 3 m)" % (pt["area"], pt["side"], need), "patio"))
    if homes >= 8:
        need = 1.20 * 0.80 + 0.05 * max(0, homes / float(cores) - 12)
        if lv > 1:
            spare = min([(c.get("length", 0) - core_depth(sh)) * CORE_W for c in plan.get("cores", [])] or [0])
        else:
            spare = min([(c.get("length", 0) - LANDING) * c.get("width", 0) for c in plan.get("cores", [])] or [0])
        out.append(("community", spare >= need - 1e-6, "community room %.2f m² in the core (%.1f m² free)" % (need, max(0, spare)), "community"))
    return [{"rule": r, "ok": bool(ok), "text": t, "cite": CITE[c]} for r, ok, t, c in out]
