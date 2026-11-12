"""Nomad - second rule test: ResPlan (17,000 residential plans, CC BY 4.0, github.com/m-agour/ResPlan).

ResPlan geometry is in drawing units; each plan stores its real interior area (net_area, m²), so the
scale per plan is sqrt(area of 'inner' polygon / net_area). Windows have no height in ResPlan, so the
1/8 window rule (Decret 141 3.9.1) cannot be tested here; everything else is the same as the Swiss test.
The pickle is opened with a restricted loader that only allows shapely/numpy objects.
Outputs: 4_laws_and_rules/output/rule_tests/resplan_units.csv, 4_laws_and_rules/output/rule_tests/resplan_summary.json
"""
import json, math, pickle
import pandas as pd

SRC = "7_floor_plans/input/datasets/resplan/ResPlan.pkl"
OUT = "4_laws_and_rules/output/rule_tests"
RULES = {
    "r_useful_36": "Decret 141/2012 Annex 1 3.1: superfície útil >= 36 m²",
    "r_useful_40": "MPGM 2004 Barcelona DA 1a 2.a: superfície útil >= 40 m²",
    "r_bedroom_6": "Decret 141/2012 Annex 1 3.8: every bedroom >= 6 m²",
    "r_bedroom_square": "Decret 141/2012 Annex 1 3.8: 2,00 m square in every bedroom (2,60 m in one if >= 3 bedrooms)",
    "r_living_circle": "Decret 141/2012 Annex 1 3.7.2: living room fits a 2,80 m circle",
    "r_bathrooms": "Decret 141/2012 Annex 1 3.11: >= 1 bathroom (>= 2 if >= 4 bedrooms)",
    "r_facade_s9": "Decret 141/2012 Annex 1 3.6.2 + MPGM 2004 DA1 2.b: façade >= max(S/9, 3 m) (proxy: window width)",
}


class SafeLoader(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith(("shapely.", "numpy")) or module in ("builtins", "copyreg", "_codecs"):
            return super().find_class(module, name)
        raise pickle.UnpicklingError("blocked %s.%s" % (module, name))


def parts(g):
    if g is None or g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, "geoms") else [g]


def fits(poly, size, s, square=True):
    er = poly.buffer(-size * s / 2.0, join_style="mitre" if square else "round")
    return not er.is_empty and er.area > 1e-9


def main():
    with open(SRC, "rb") as f:
        plans = SafeLoader(f).load()
    rows = []
    for p in plans:
        S = float(p.get("net_area") or 0)
        inner = p.get("inner")
        if not S or inner is None or inner.is_empty:
            continue
        s = math.sqrt(inner.area / S)            # drawing units per metre
        beds = parts(p.get("bedroom"))
        liv = parts(p.get("living"))
        baths = parts(p.get("bathroom"))
        bed_m2 = [b.area / s ** 2 for b in beds]
        win_w = sum(max(w.minimum_rotated_rectangle.length / 2 - 0.0, 0) for w in parts(p.get("window"))) / s
        nb = len(beds)
        rows.append({
            "plan_id": p.get("id"), "useful_m2": round(S, 1), "bedrooms": nb, "bathrooms": len(baths),
            "min_bedroom_m2": round(min(bed_m2), 1) if bed_m2 else None, "window_width_m": round(win_w, 1),
            "r_useful_36": S >= 36, "r_useful_40": S >= 40,
            "r_bedroom_6": all(a >= 6 for a in bed_m2),
            "r_bedroom_square": all(fits(b, 2.0, s) for b in beds) and (nb < 3 or any(fits(b, 2.6, s) for b in beds)),
            "r_living_circle": any(fits(l, 2.8, s, square=False) for l in liv),
            "r_bathrooms": len(baths) >= (2 if nb >= 4 else 1),
            "r_facade_s9": win_w >= max(S / 9.0, 3.0),
        })
    df = pd.DataFrame(rows)
    df["all_pass"] = df[list(RULES)].all(axis=1)
    df.to_csv(f"{OUT}/resplan_units.csv", index=False)
    summary = {"source": "ResPlan (github.com/m-agour/ResPlan), CC BY 4.0", "rules": RULES, "plans": len(df),
               "median_useful_m2": float(df.useful_m2.median()),
               "pass_rate": {k: round(float(df[k].mean()), 3) for k in RULES}, "all_pass": round(float(df.all_pass.mean()), 3)}
    with open(f"{OUT}/resplan_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
