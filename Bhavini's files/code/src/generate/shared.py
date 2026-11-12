# -*- coding: utf-8 -*-
"""Nomad - shared-space housing ("allotjaments amb espais comuns complementaris", ACEC): many small homes around shared
rooms, the fast, small-unit route the critics asked for (temporary / emergency housing, 29 Oct review).

The law (all in the rulebook):
  Llei 18/2007 art. 3.p and 18 bis (DL 50/2020)  a home with a private space smaller than other homes plus shared rooms;
      the private space + its share of the shared rooms may not be less than the minimum for a full home (18 bis.2); in a
      building in horizontal property the whole set is one private element (18 bis.3) - a ground-floor shop already is
  Llei 18/2007 DT 10a (Circular 8 AHC)  private space >= 24 m² useful; shared rooms >= 6 m² per home, each >= 6 m² with a
      2,45 m circle, with natural light and ventilation (Decret 141/2012 Annex 1 3.9); private + shared >= 36 m²; the
      community room (Annex 1 2.6) is not required; laundry may be in a shared room
  MPGM 2004 DA1 2.a  Barcelona: 40 m² useful per home - applied here to private + share (the stricter reading of 18 bis.2,
      to confirm with the city)
  MPGM 2004 DA2 (its memoria)  density limits may be exceeded for homes for groups needing social attention, with small
      programmes of one or two people: the density card becomes "check" instead of "fails"
  TRLU art. 34.5 quater  "allotjament temporal de protecció" is only allowed on public land zoned for facilities: it is
      NOT a route for a private shop, so NOMAD does not offer it
How: plan3 lays out real studios (private space >= 24 m²) as small as the library allows; then the fewest studios with
the most light become the shared living room and kitchen, until every home has its share. Plain Python.
"""
import plan3

CITE = {
    "private": "Llei 18/2007 DT 10a (DL 50/2020; Circular 8 AHC): private space >= 24 m² useful",
    "share": "Llei 18/2007 DT 10a: shared rooms >= 6 m² per home, each >= 6 m² with a 2,45 m circle, lit (Decret 141/2012 Annex 1 3.9)",
    "total": "Llei 18/2007 art. 18 bis.2 with MPGM 2004 DA1 2.a (40 m² per home in Barcelona)",
    "density": "MPGM 2004 DA2: density may be exceeded for homes for groups needing social attention (to confirm with the city)",
}
PRIVATE_MIN, SHARE_MIN, TOTAL_MIN, CIRCLE = 24.0, 6.0, 40.0, 2.45
SHARED_NAMES = {"living": "shared living room", "kitchen": "shared kitchen", "bed_main": "shared room", "bed": "shared room",
                "bath": "shared bath and laundry", "hall": "shared hall", "storage": "shared storage"}


def convert(plan):
    """Turn the fewest, best-lit studios of a plan into shared rooms until every remaining home has private + share >= 40 m²
    and share >= 6 m². Adds the checks; returns the plan (homes = the private units left)."""
    units = [u for u in plan.get("units", []) if u.get("ok")]
    if not units:
        return plan
    lit = lambda u: sum(r["area"] for r in u["rooms"] if r.get("on_facade"))
    order = sorted(units, key=lambda u: (-lit(u), -u["area_m2"]))
    shared, homes = [], list(units)
    if len(units) < 2 or all(u["area_m2"] >= TOTAL_MIN for u in units):
        return plan                                      # nothing to share: the homes are full homes already
    def enough(homes, have):                             # shares are proportional to private area (DT 10a.2)
        tot = sum(x["area_m2"] for x in homes) or 1.0
        return all(have * x["area_m2"] / tot >= max(SHARE_MIN, TOTAL_MIN - x["area_m2"]) - 1e-6 for x in homes)
    while len(homes) > 1:
        if enough(homes, sum(u["area_m2"] for u in shared)):
            break
        u = next(x for x in order if x in homes)
        homes.remove(u)
        shared.append(u)
    have = sum(u["area_m2"] for u in shared)
    need = sum(max(SHARE_MIN, TOTAL_MIN - u["area_m2"]) for u in homes)
    for u in shared:
        u["type"], u["shared"] = "shared rooms", True
        for r in u["rooms"]:
            r["name"] = SHARED_NAMES.get(r["kind"], "shared " + r["kind"])
        circle = max([r.get("clear", 0) for r in u["rooms"]] or [0])
        u["checks"] = [{"rule": "share_room", "ok": circle >= CIRCLE - 1e-6 and lit(u) > 0, "cite": CITE["share"],
                        "text": "shared rooms %.1f m², %.2f m circle, on the façade" % (u["area_m2"], circle)}]
        u["ok"] = u["checks"][0]["ok"]
    for u in homes:
        share = have * u["area_m2"] / max(sum(x["area_m2"] for x in homes), 1e-6)     # proportional to private area (DT 10a.2)
        u["share_m2"] = round(share, 1)
        u["checks"] = [c for c in u["checks"] if c["rule"] != "useful"] + [
            {"rule": "private", "ok": u["area_m2"] >= PRIVATE_MIN - 1e-6, "cite": CITE["private"], "text": "private %.1f m²" % u["area_m2"]},
            {"rule": "share", "ok": share >= SHARE_MIN - 1e-6, "cite": CITE["share"], "text": "share of the shared rooms %.1f m²" % share},
            {"rule": "total", "ok": u["area_m2"] + share >= TOTAL_MIN - 1e-6, "cite": CITE["total"],
             "text": "private + share %.1f m² (>= %d in Barcelona)" % (u["area_m2"] + share, TOTAL_MIN)}]
        u["ok"] = all(c["ok"] for c in u["checks"])
        u["fails"] = sorted(set(c["rule"] for c in u["checks"] if not c["ok"]))
    plan["units"] = homes + shared + [u for u in plan.get("units", []) if not u.get("ok") and u not in shared and u not in homes]
    plan["shared_m2"] = round(have, 1)
    plan["homes_shared"] = len(homes)
    plan["compliant"] = sum(1 for u in homes if u["ok"])
    plan["interventions"] = list(plan.get("interventions", [])) + [
        "shared-space housing (Llei 18/2007 art. 18 bis): %d small homes and %.0f m² of shared living rooms and kitchens on the façade (%.0f m² needed)"
        % (len(homes), have, need)]
    plan["scheme"] = "shared"
    return plan


def iterations(outline, facade, height, mix, street=None, existing=None, weights=None, lit_depth=5.5, lit_source=None, patios=None):
    """plan3's layouts with studios only, as many as fit, then each turned into shared-space housing."""
    keep = plan3.USEFUL_MIN[0]
    plan3.USEFUL_MIN[0] = PRIVATE_MIN
    plan3.SMALL[0] = True
    try:
        n = max(2, sum(mix.values()) if mix else 2)
        before, its, tried = plan3.iterations(outline, facade, height, {"studio": n}, street=street, sizes={"studio": 28.0},
                                              existing=existing, weights=weights, lit_depth=lit_depth, lit_source=lit_source,
                                              patios=patios)
    finally:
        plan3.USEFUL_MIN[0] = keep
        plan3.SMALL[0] = False
    out = []
    for name, p, m in its:
        p = convert(p)
        p["params"] = dict(p.get("params", {}), fill=True)
        out.append(("shared-space homes, " + name, p, m))
    return before, out, tried
