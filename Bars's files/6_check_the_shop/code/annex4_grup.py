"""NOMAD - Decret 141/2012 Annex 4: is each empty shop's conversion Grup B, C (≤ 50 %) or D (> 50 %)?

Grup B = change of use of the whole building (here: the shop is >= 90 % of a building that holds no homes).
Shop = the census premises' non-housing constructions on the ground floor (record 14), plus its own basement when its
unit holds no homes. Building = the parcel's total built area (record 11), so both sides of the ratio use one scope.
A ratio above 102 % is reported as "unknown: data mismatch", never as a group.

Grup B / C / D come from the shop's built area ÷ the building's total built area, above and below ground ("canvi d'ús
d'un edifici (≤ 50% de la superfície construïda sobre o sota rasant)", DOGC 6245 p. 53451).

Data: the Catastro's alphanumeric data, CAT format, Barcelona urban (fixed width, 1000 characters a record; format
"Fichero informático de remisión de catastro", revision 16-11-2022):
  record 11 (finca): parcel (31,14) · built area total (306,7) · above ground (313,7) · below ground (320,7)
  record 14 (construction): parcel (31,14) · unit number, blank for common elements (51,4) · building unit / unidad
            constructiva (55,4) · floor (65,3) · door (68,3) · use code (71,3) · area (84,7)
  record 15 (unit / bien inmueble): parcel (31,14) · unit number (45,4) · floor (252,3) · door (255,3) · use (428,1) ·
            built area of its constructions (442,10)
The CAT file is downloaded by a registered user from the Sede Electrónica del Catastro and its licence forbids putting
the original file on the internet: it stays in nomad/02_Code/data/barcelona/catastro/cat/ (not in git). Only the
derived group and percentage go into the site (docs/ANNEX4.md).

Which space is the shop? The census (Open Data BCN, cens de locals en planta baixa 2024) gives the 14-character parcel,
"Planta" (always LOC) and "Porta". The candidates are the parcel's non-housing constructions on the ground floor
(record 14), grouped by unit, or by door inside an undivided building (one unit that also holds the homes):
  door      the census door matches a construction's door (record 14) or a unit's door (record 15)
  only      the parcel has exactly one candidate
  same      several candidates, and every one gives the same group (the % shown is the smallest, ratio_max the largest);
  unknown   no CAT parcel, no candidate, the Catastro records the ground floor as housing, a data mismatch (> 102 %),
            or candidates that give different groups
Building = the parcel (record 11), or, when the parcel holds several buildings (unidades constructivas) and the shop
sits in one that also has upper floors, that building (the sum of its records 14). Shop and building always use the
same scope. The alternative reading of "sobre o sota rasant" (above and below ground counted separately) is computed
too, to count the shops it would move (docs/OPEN_QUESTIONS.md).

Run from the repo root:
  python tools/annex4_grup.py --cat <08_900_U_YYYY-MM-DD.CAT.gz> --accessed YYYY-MM-DD [--census <csv>]
Writes nomad/04_Website/data/annex4_grup.json (site) and nomad/02_Code/results/annex4/spotcheck.md (local, with m²).
"""
import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "nomad" / "02_Code" / "data" / "barcelona" / "census" / "2024_CensComercial_BCN.csv"
PREMISES = ROOT / "nomad" / "04_Website" / "data" / "premises.json"
OUT = ROOT / "nomad" / "04_Website" / "data" / "annex4_grup.json"
SPOT = ROOT / "nomad" / "02_Code" / "results" / "annex4" / "spotcheck.md"
GROUND = {"00", "0", "000", "BJ", "PB", "BX", "LO", "LC", "LOC"}
BELOW_WORDS = {"SS", "SO", "ST", "SM", "SOT"}


def f(rec, start, length):                                     # a field by the spec's 1-based position
    return rec[start - 1:start - 1 + length]


def num(s):
    s = s.strip()
    return int(s) if s.isdigit() else 0


def below(planta):
    p = planta.strip().upper()
    return p.startswith("-") or p in BELOW_WORDS


def ground(planta):
    return planta.strip().upper() in GROUND


def door(s):
    s = s.strip().lstrip("0")
    return s


def parse(lines):
    """CAT records -> {parcel: {"total", "above", "below", "cons": [...], "units": {cargo: {...}}}}"""
    P = defaultdict(lambda: {"total": 0, "above": 0, "below": 0, "cons": [], "units": {}})
    for rec in lines:
        rec = rec.rstrip("\r\n")
        t = rec[:2]
        if t == "11":
            p = P[f(rec, 31, 14)]
            p["total"], p["above"], p["below"] = num(f(rec, 306, 7)), num(f(rec, 313, 7)), num(f(rec, 320, 7))
        elif t == "14":
            P[f(rec, 31, 14)]["cons"].append({"unit": f(rec, 51, 4).strip(), "uc": f(rec, 55, 4).strip(),
                                             "floor": f(rec, 65, 3), "door": f(rec, 68, 3), "use": f(rec, 71, 3).strip(),
                                             "m2": num(f(rec, 84, 7))})
        elif t == "15":
            P[f(rec, 31, 14)]["units"][f(rec, 45, 4).strip()] = {"floor": f(rec, 252, 3), "door": f(rec, 255, 3),
                                                                 "use": f(rec, 428, 1).strip(), "m2": num(f(rec, 442, 10))}
    return P


def open_cat(path):
    op = gzip.open if str(path).lower().endswith(".gz") else open
    with op(path, "rt", encoding="latin-1", newline="") as fh:
        return parse(fh)


def nonres(c):
    """A construction that is not housing and not a common element (the shop's own space)."""
    return bool(c["unit"]) and bool(c["use"]) and not c["use"].upper().startswith("V")


def building_area(p, cons):
    """The building of these constructions: the parcel (record 11, or the sum of its constructions when record 11 has
    none), or, when the parcel holds several unidades constructivas and the shop sits in one that also has upper
    floors (a separate building), that one."""
    ucs = {c["uc"] for c in p["cons"] if c["uc"]}
    own = {c["uc"] for c in cons if c["uc"]}
    if len(ucs) > 1 and len(own) == 1:
        uc = next(iter(own))
        inb = [c for c in p["cons"] if c["uc"] == uc]
        if any(not ground(c["floor"]) and not below(c["floor"]) for c in inb):
            return sum(c["m2"] for c in inb), sum(c["m2"] for c in inb if below(c["floor"])), "building"
    tot = p["total"] or sum(c["m2"] for c in p["cons"])
    blw = p["below"] if p["total"] else sum(c["m2"] for c in p["cons"] if below(c["floor"]))
    return tot, blw, "parcel"


def shop_area(p, cons):
    """The shop = these ground-floor constructions, plus the below-ground non-housing constructions of the same units
    when those units hold no housing (a shop's own basement). In an undivided building (one unit that also holds the
    homes) only the ground-floor constructions count, never the whole unit."""
    units = {c["unit"] for c in cons}
    own_below = [c for c in p["cons"] if c["unit"] in units and below(c["floor"]) and nonres(c) and c not in cons
                 and not any(d["unit"] == c["unit"] and not nonres(d) for d in p["cons"])]
    return sum(c["m2"] for c in cons) + sum(c["m2"] for c in own_below), sum(c["m2"] for c in own_below)


def result(p, cons, method, extra=None):
    bldg, bldg_below, scope = building_area(p, cons)
    if not bldg:
        return {"grup": "unknown", "method": "unknown", "why": "no built area"}
    shop, shop_below = shop_area(p, cons)
    ratio = shop / bldg
    if ratio > 1.02:
        return {"grup": "unknown", "method": "unknown", "why": "data mismatch: shop larger than the building",
                "shop_m2": shop, "building_m2": bldg, "building_below_m2": bldg_below}
    above_r = (shop - shop_below) / (bldg - bldg_below) if bldg - bldg_below > 0 else 0
    below_r = shop_below / bldg_below if bldg_below > 0 else 0
    whole = ratio >= 0.9 and not any(c["use"].upper().startswith("V") for c in p["cons"])   # no homes: the whole building
    grup = "B" if whole else ("D" if ratio > 0.5 else "C")
    sep = "B" if whole else ("D" if max(above_r, below_r) > 0.5 else "C")
    out = {"cargo": ",".join(sorted({c["unit"] for c in cons})), "shop_m2": shop, "shop_below_m2": shop_below,
           "building_m2": bldg, "building_below_m2": bldg_below, "denominator": scope, "ratio": min(ratio, 1.0),
           "grup": grup, "grup_separately": sep, "method": method}
    out.update(extra or {})
    return out


def classify(P, ref, porta):
    """One census premises -> {grup, ratio, method, ...}.
    Candidates are the parcel's non-housing constructions on the ground floor (record 14), grouped by unit, or by door
    inside an undivided building. door = the census door matches; only = one candidate; same = several candidates
    that all give the same group."""
    p = P.get(ref)
    if p is None:
        return {"grup": "unknown", "method": "unknown", "why": "parcel not in the CAT file"}
    g = [c for c in p["cons"] if ground(c["floor"]) and nonres(c)]
    if not g:
        why = ("the Catastro records the ground floor as housing" if any(ground(c["floor"]) for c in p["cons"])
               else "no construction on the ground floor")
        return {"grup": "unknown", "method": "unknown", "why": why}
    if porta and door(porta):
        by_door = [c for c in g if door(c["door"]) == door(porta)]
        if not by_door:                                         # the door may be on the unit (record 15) only
            units = {k for k, u in p["units"].items() if door(u["door"]) == door(porta)}
            by_door = [c for c in g if c["unit"] in units]
        if by_door:
            return result(p, by_door, "door")
    groups = defaultdict(list)                                  # candidates: by unit, or by door in a mixed unit
    for c in g:
        mixed = any(d["unit"] == c["unit"] and not nonres(d) for d in p["cons"])
        groups[(c["unit"], door(c["door"]) if mixed else "")].append(c)
    cands = list(groups.values())
    if len(cands) == 1:
        return result(p, cands[0], "only")
    ms = [result(p, c, "same", {"candidates": len(cands)}) for c in cands]
    ms = [m for m in ms if m["grup"] != "unknown"]
    hi = result(p, g, "same", {"candidates": len(cands)})        # all the ground-floor non-housing space together
    if ms and len(ms) == len(cands) and all(m["grup"] == ms[0]["grup"] for m in ms):
        lo = min(ms, key=lambda m: m["ratio"])
        out = dict(lo, ratio_max=max(m["ratio"] for m in ms))
        if hi["grup"] == "C" and out["grup"] == "C":
            out["why"] = "even all the ground-floor non-housing space together is <= 50 %"
        return out
    return {"grup": "unknown", "method": "unknown", "candidates": len(cands),
            "why": f"{len(cands)} spaces could be this shop and they give different groups"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cat", required=True, help="the Barcelona urban CAT file (.CAT or .CAT.gz)")
    ap.add_argument("--accessed", required=True, help="date the CAT file was downloaded, YYYY-MM-DD (the licence asks for it)")
    ap.add_argument("--census", default=str(CENSUS))
    a = ap.parse_args()
    P = open_cat(a.cat)
    prem = json.loads(PREMISES.read_text(encoding="utf-8"))
    rows = [dict(zip(prem["cols"], r)) for r in prem["rows"]]
    census = {}
    with open(a.census, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["Nom_Sector_Activitat"].startswith("Locals buits") and r["Referencia_Cadastral"]:
                key = f"{r['Referencia_Cadastral']}|{round(float(r['X_UTM_ETRS89']))}|{round(float(r['Y_UTM_ETRS89']))}"
                census.setdefault(key, []).append(r)
    shops, detail, seen = {}, [], set()
    for r in rows:
        key = f"{r['ref']}|{r['x']}|{r['y']}"
        cs = census.get(key, [])
        res = [classify(P, r["ref"], c["Porta"]) for c in cs] or [classify(P, r["ref"], "")]
        g = {x["grup"] for x in res}
        out = res[0] if len(g) == 1 else {"grup": "unknown", "method": "unknown", "why": "premises at this point differ"}
        shops[key] = [out["grup"], round(100 * out["ratio"], 1) if "ratio" in out else None, out["method"],
                      round(100 * out["ratio_max"], 1) if "ratio_max" in out else None, out.get("why", "")]
        if key not in seen:
            seen.add(key); detail.append((r, out))
    counts = Counter(v[0] for v in shops.values())
    methods = Counter(v[2] for v in shops.values())
    moved = sum(1 for _, o in detail if o.get("grup_separately") and o["grup_separately"] != o["grup"])
    src = (f"Derived by NOMAD from data of the Dirección General del Catastro (alphanumeric data, CAT format, Barcelona), "
           f"accessed on {a.accessed}. Not Catastro information: a NOMAD estimate.")
    OUT.write_text(json.dumps({"about": "Decret 141/2012 Annex 4 group of each empty shop: [grup, % of the building's "
                                        "built area, how the unit was found, largest % when several units fit, why unknown]. "
                                        "Built by tools/annex4_grup.py.",
                               "source": src, "accessed": a.accessed, "counts": counts, "methods": methods,
                               "moved_if_counted_separately": moved, "shops": shops},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # local spot-check list (m² are Catastro figures: kept out of git and off the site)
    md = [f"# Annex 4 group per shop: spot check", "", src, "",
          f"Shops: {len(shops)} · " + " · ".join(f"Grup {k}: {v}" for k, v in sorted(counts.items())),
          "How the unit was found: " + " · ".join(f"{k}: {v}" for k, v in methods.most_common()),
          f"Would change group if above and below ground were counted separately: {moved}", ""]
    for grp in ("B", "C", "D", "unknown"):
        ex = [d for d in detail if d[1]["grup"] == grp]
        ex = ex[:: max(1, len(ex) // 5)][:5]
        md += [f"## Grup {grp}: {len(ex)} of {sum(1 for d in detail if d[1]['grup'] == grp)}", "",
               "| Shop | Ref | Shop m² | Building m² (below) | % | Unit | Found by / why |", "|---|---|---:|---:|---:|---|---|"]
        for r, o in ex:
            md.append(f"| {r['street']} {r['num']} | {r['ref']} | {o.get('shop_m2', '')} | {o.get('building_m2', '')} "
                      f"({o.get('building_below_m2', '')}) | {round(100 * o['ratio'], 1) if 'ratio' in o else ''} | "
                      f"{o.get('cargo', '')} | {o['method']}{': ' + o['why'] if o.get('why') else ''} |")
        md.append("")
    SPOT.parent.mkdir(parents=True, exist_ok=True)
    SPOT.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:7]))
    print(f"\nwrote {OUT} and {SPOT}")


if __name__ == "__main__":
    main()