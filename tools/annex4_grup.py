"""NOMAD - Decret 141/2012 Annex 4: is each empty shop's conversion Grup C (≤ 50 %) or Grup D (> 50 %)?

Grup C / D = the shop's built area ÷ the building's total built area, above and below ground ("canvi d'ús d'un edifici
(≤ 50% de la superfície construïda sobre o sota rasant)", DOGC 6245 p. 53451).

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

Which unit is the shop? The census (Open Data BCN, cens de locals en planta baixa 2024) gives the 14-character parcel,
"Planta" (always LOC) and "Porta". For each empty premises, the candidates are the parcel's non-residential units with a
construction on the ground floor:
  door      a candidate on the ground floor whose door number equals the census door (the only such one)
  only      the parcel has exactly one candidate
  same      several candidates, and every one gives the same group (the percentage shown is the smallest-largest)
  unknown   no CAT parcel, no candidate, or candidates that give different groups
Building = the parcel (record 11), or, when the parcel holds several buildings (unidades constructivas), the shop's own
building (sum of its records 14). The alternative reading of "sobre o sota rasant" (above and below ground counted
separately) is computed too, to count the shops it would move (docs/OPEN_QUESTIONS.md).

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


def measure(p, cargo):
    """One unit as the shop -> numbers for the ratio."""
    own = [c for c in p["cons"] if c["unit"] == cargo]
    shop = sum(c["m2"] for c in own) or p["units"][cargo]["m2"]
    shop_below = sum(c["m2"] for c in own if below(c["floor"]))
    ucs = {c["uc"] for c in p["cons"] if c["uc"]}
    if len(ucs) > 1 and own:
        uc = Counter(c["uc"] for c in own).most_common(1)[0][0]
        inb = [c for c in p["cons"] if c["uc"] == uc]
        bldg, bldg_below, src = sum(c["m2"] for c in inb), sum(c["m2"] for c in inb if below(c["floor"])), "building"
    else:
        bldg, bldg_below, src = p["total"] or sum(c["m2"] for c in p["cons"]), p["below"], "parcel"
        if not p["total"]:
            bldg_below = sum(c["m2"] for c in p["cons"] if below(c["floor"]))
    if not bldg:
        return None
    ratio = shop / bldg
    above_r = (shop - shop_below) / (bldg - bldg_below) if bldg - bldg_below > 0 else 0
    below_r = shop_below / bldg_below if bldg_below > 0 else 0
    return {"cargo": cargo, "shop_m2": shop, "shop_below_m2": shop_below, "building_m2": bldg,
            "building_below_m2": bldg_below, "denominator": src, "ratio": ratio, "grup": "D" if ratio > 0.5 else "C",
            "grup_separately": "D" if max(above_r, below_r) > 0.5 else "C"}


def classify(P, ref, porta):
    """One census premises -> {grup, ratio, method, ...}."""
    p = P.get(ref)
    if p is None:
        return {"grup": "unknown", "method": "unknown", "why": "parcel not in the CAT file"}
    on_ground = {c["unit"] for c in p["cons"] if c["unit"] and ground(c["floor"])}
    cands = [k for k, u in p["units"].items() if u["use"] != "V" and (k in on_ground or ground(u["floor"]))]
    if not cands:
        return {"grup": "unknown", "method": "unknown", "why": "no non-residential unit on the ground floor"}
    by_door = [k for k in cands if porta and door(p["units"][k]["door"]) == door(porta)]
    if len(by_door) == 1:
        m = measure(p, by_door[0])
        return dict(m, method="door") if m else {"grup": "unknown", "method": "unknown", "why": "no built area"}
    ms = [m for m in (measure(p, k) for k in cands) if m]
    if not ms:
        return {"grup": "unknown", "method": "unknown", "why": "no built area"}
    if len(ms) == 1:
        return dict(ms[0], method="only")
    groups = {m["grup"] for m in ms}
    if len(groups) == 1:
        lo, hi = min(ms, key=lambda m: m["ratio"]), max(ms, key=lambda m: m["ratio"])
        return dict(lo, method="same", ratio_max=hi["ratio"], candidates=len(ms))
    return {"grup": "unknown", "method": "unknown", "candidates": len(ms),
            "why": f"{len(ms)} units could be this shop and they give different groups"}


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
    shops, detail = {}, []
    for r in rows:
        key = f"{r['ref']}|{r['x']}|{r['y']}"
        cs = census.get(key, [])
        res = [classify(P, r["ref"], c["Porta"]) for c in cs] or [classify(P, r["ref"], "")]
        g = {x["grup"] for x in res}
        out = res[0] if len(g) == 1 else {"grup": "unknown", "method": "unknown", "why": "premises at this point differ"}
        shops[key] = [out["grup"], round(100 * out["ratio"], 1) if "ratio" in out else None, out["method"],
                      round(100 * out["ratio_max"], 1) if "ratio_max" in out else None, out.get("why", "")]
        detail.append((r, out))
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
    for grp in ("C", "D", "unknown"):
        ex = [d for d in detail if d[1]["grup"] == grp]
        ex = ex[:: max(1, len(ex) // 5)][:5]
        md += [f"## Grup {grp}: 5 of {sum(1 for d in detail if d[1]['grup'] == grp)}", "",
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
