# -*- coding: utf-8 -*-
"""Nomad unit-mix simulation: how many dwellings of each type fit in a space, and which rules pass.

Works in Grasshopper (IronPython 2.7) and normal Python 3, so: no f-strings, no type hints.
Every rule number comes from the Nomad rulebook (4_laws_and_rules/output/rulebook.jsonl) and carries its citation.

Inputs (all metres / m²):
  built_area     built floor area available for housing (m², all floors together)
  floors         number of floors
  facade_length  façade length per floor that can give light and air (street + interior block patio), m
  efficiency     useful area / built area (walls, circulation, shafts), e.g. 0.80
  mix            dict type -> share, e.g. {"studio": 1, "1bed": 2, "2bed": 2, "3bed": 1}
  unit_area      dict type -> useful area per unit (m²) that the owner wants
"""
import math

# ---- rules (value, citation) -------------------------------------------------------------------------
RULES = {
    "min_useful_cat": (36.0, "Decret 141/2012, Annex 1, 3.1 (superfície útil interior no inferior a 36 m²)"),
    "min_useful_bcn": (40.0, "MPGM 2004 Barcelona, Disposició addicional primera 2.a (superfície útil mínima de 40 m²)"),
    "min_facade_bcn": (3.0, "MPGM 2004 Barcelona, Disposició addicional primera 2.b (3 m en contacte amb la façana)"),
    "facade_ratio": (9.0, "Decret 141/2012, Annex 1, 3.6.2 (perímetre de façana L >= S/9)"),
    "density_module": (80.0, "MPGM 2004 Barcelona, art. 318 / guia Ajuntament 2025 (nombre d'habitatges = superfície construïda / 80 m², per excés)"),
    "min_bedroom": (6.0, "Decret 141/2012, Annex 1, 3.8 (l'habitació mínima serà de 6 m²)"),
    "studio_room": (8.0, "Decret 141/2012, Annex 1, 3.1 (estança única: ha de permetre compartimentar una habitació de 8 m²)"),
    "min_height": (2.50, "Decret 141/2012, Annex 1, 3.5 (alçada lliure mínima 2,50 m)"),
    "window_ratio": (1.0 / 8.0, "Decret 141/2012, Annex 1, 3.9.1 (obertures >= 1/8 de la superfície útil)"),
}

BEDROOMS = {"studio": 0, "1bed": 1, "2bed": 2, "3bed": 3, "4bed": 4}
# Max occupants: Decret 141/2012 art. 4.1 (2 persons per bedroom of >= 8 m²; studio: 2 persons)
def max_occupants(bedrooms):
    return 2 if bedrooms == 0 else 2 * bedrooms


def rule(key):
    return RULES[key][0]


def min_area_for(t):
    """Legal minimum useful area for a unit type in Barcelona (the stricter of Catalonia and Barcelona)."""
    return max(rule("min_useful_cat"), rule("min_useful_bcn"))


def facade_needed(area):
    """Façade length one unit needs: the longer of S/9 (Decret 141) and 3 m (Barcelona)."""
    return max(area / rule("facade_ratio"), rule("min_facade_bcn"))


def max_dwellings(built_area):
    """MPGM 2004 art. 318: built area divided by 80 m², rounded up ('per excés')."""
    return int(math.ceil(built_area / rule("density_module") - 1e-9))


def solve(built_area, floors, facade_length, efficiency, mix, unit_area, floor_height=3.0):
    """Find the largest number of dwellings that keeps the chosen mix and passes every rule.

    Returns a dict with counts per type, the limiting rule, and a list of checks (ok, text, citation).
    """
    types = [t for t in ["studio", "1bed", "2bed", "3bed", "4bed"] if mix.get(t, 0) > 0]
    useful_total = built_area * efficiency
    facade_total = facade_length * floors
    cap = max_dwellings(built_area)
    shares = dict((t, float(mix[t])) for t in types)
    s = sum(shares.values()) or 1.0

    best, limit = dict((t, 0) for t in types), "no types chosen"
    for n in range(1, cap + 1):
        # distribute n units over types by share (largest remainder method)
        raw = dict((t, n * shares[t] / s) for t in types)
        cnt = dict((t, int(math.floor(raw[t]))) for t in types)
        rest = n - sum(cnt.values())
        for t in sorted(types, key=lambda k: raw[k] - cnt[k], reverse=True)[:rest]:
            cnt[t] += 1
        area = sum(cnt[t] * unit_area[t] for t in types)
        fac = sum(cnt[t] * facade_needed(unit_area[t]) for t in types)
        if area > useful_total + 1e-9:
            limit = "useful area (%.0f m² available)" % useful_total
            break
        if fac > facade_total + 1e-9:
            limit = "façade length (%.1f m available, S/9 and 3 m per dwelling)" % facade_total
            break
        best = cnt
        limit = "density (max %d dwellings = %.0f m² / 80 m²)" % (cap, built_area)

    checks = []
    for t in types:
        a = unit_area[t]
        checks.append((a >= min_area_for(t), "%s: %.0f m² useful >= %.0f m²" % (t, a, min_area_for(t)), RULES["min_useful_bcn"][1]))
        b = BEDROOMS[t]
        if b:
            # rough room budget: living+kitchen+bath need about 20 m²; the rest must give >= 6 m² per bedroom
            per_bed = (a - 20.0) / b
            checks.append((per_bed >= rule("min_bedroom"),
                           "%s: about %.1f m² per bedroom after 20 m² living/kitchen/bath (>= 6 m²)" % (t, per_bed),
                           RULES["min_bedroom"][1]))
    total = sum(best.values())
    checks.append((total <= cap, "%d dwellings <= density limit %d" % (total, cap), RULES["density_module"][1]))
    checks.append((floor_height >= rule("min_height") + 0.30,
                   "floor-to-floor %.2f m leaves >= 2,50 m clear (assuming 0,30 m slab)" % floor_height,
                   RULES["min_height"][1]))
    return {
        "counts": best, "total": total, "limit": limit, "density_cap": cap,
        "useful_used": sum(best[t] * unit_area[t] for t in types), "useful_total": useful_total,
        "facade_used": sum(best[t] * facade_needed(unit_area[t]) for t in types), "facade_total": facade_total,
        "occupants": sum(best[t] * max_occupants(BEDROOMS[t]) for t in types),
        "checks": checks,
    }


def report(res):
    lines = ["Nomad unit mix", "Dwellings: %d (limit: %s)" % (res["total"], res["limit"])]
    for t, n in res["counts"].items():
        lines.append("  %-6s x %d" % (t, n))
    lines.append("Useful area used %.0f / %.0f m²" % (res["useful_used"], res["useful_total"]))
    lines.append("Façade used %.1f / %.1f m" % (res["facade_used"], res["facade_total"]))
    lines.append("Max occupants (Decret 141 art. 4): %d" % res["occupants"])
    for ok, txt, cite in res["checks"]:
        lines.append("%s %s  [%s]" % ("PASS" if ok else "FAIL", txt, cite))
    return "\n".join(lines)


if __name__ == "__main__":
    r = solve(built_area=600, floors=1, facade_length=30, efficiency=0.80,
              mix={"studio": 1, "1bed": 2, "2bed": 2, "3bed": 0},
              unit_area={"studio": 40, "1bed": 50, "2bed": 65, "3bed": 85})
    print(report(r))
