"""Nomad - "avoid" as an answer: which empty shops should NOT become homes, and why (review of 29 Oct 2026).

A NO is a result a city can use: "do not convert here, look elsewhere". Each of the 6,149 empty premises of the 2024
census gets one answer, the first reason that applies:
  1 not allowed      its zone does not admit ground-floor housing (Step 3: PGM art. 225.7 on the MUC map)
  2 not liveable     NOMAD fits no home that passes the rules, or Bars's daylight model predicts a dark floor
                     (mean daylight factor < 1 %; src/daylight/bars_daylight.py) - only for the 1,650 modelled shops
  3 keep it a shop   few shops left around it: everyday retail ("Comerç al detall") within 100 m in the lowest 10 % of
                     the city. Converting it would push the street towards housing only. This 10 % is a NOMAD design
                     choice (a relative measure), not a law.
  4 candidate        none of the above (for modelled shops: at least one home fits and daylight is not dark)
  5 not modelled     zone allows it and the street keeps shops, but NOMAD has no clean outline yet (shared ground floor ...)
Premises that share a ground floor are modelled from their own Catastro unit where the Catastro has a floor-by-floor
plan (src/building/catastro_shops.py, results/real_shops/catastro_results.csv).
Out: results/avoid/avoid.csv (one row per premises), results/avoid/summary.json
Run: .venv/Scripts/python src/check/avoid.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "avoid"
RADIUS, LOW = 100.0, 0.10


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(ROOT / "data" / "barcelona" / "census" / "2024_CensComercial_BCN.csv", low_memory=False, encoding="utf-8")
    active = c[c["Nom_Principal_Activitat"] == "Actiu"]
    retail = active[active["Nom_Sector_Activitat"].astype(str).str.startswith("Comer")]
    z = pd.read_csv(ROOT / "results" / "zoning" / "empty_premises_zoning.csv", low_memory=False)
    xy = z[["X_UTM_ETRS89", "Y_UTM_ETRS89"]].to_numpy(float)
    z["active_100m"] = [len(i) for i in cKDTree(active[["X_UTM_ETRS89", "Y_UTM_ETRS89"]].to_numpy(float)).query_ball_point(xy, RADIUS)]
    z["retail_100m"] = [len(i) for i in cKDTree(retail[["X_UTM_ETRS89", "Y_UTM_ETRS89"]].to_numpy(float)).query_ball_point(xy, RADIUS)]
    cut = float(np.quantile(z["retail_100m"], LOW))

    # NOMAD's answer for the modelled real shops (by building), and Bars's daylight
    nr = pd.read_csv(ROOT / "results" / "real_shops" / "nomad_results.csv", dtype={"ref": str})
    homes = dict(zip(nr["ref"], nr["most_homes"]))
    verdict = dict(zip(nr["ref"], nr["after"]))
    dl = pd.read_csv(ROOT / "results" / "daylight" / "real_shops_daylight.csv", dtype={"ref14": str})
    df = dict(zip(dl["ref14"], dl["pred_mean_df"]))
    lit = dict(zip(dl["ref14"], dl["lit_depth_m"]))
    ref14 = z["Referencia_Cadastral"].astype(str).str[:14]
    # premises sharing a ground floor, modelled from their own Catastro unit (src/building/catastro_shops.py)
    cr = ROOT / "results" / "real_shops" / "catastro_results.csv"
    cat = {r.id: r for r in pd.read_csv(cr, dtype={"ref": str, "id": str}).itertuples()} if cr.exists() else {}

    ans, why = [], []
    for k, r in z.iterrows():
        ref = ref14[k]
        h, d = homes.get(ref), df.get(ref)
        cu = cat.get(str(r["ID_Global"]))
        if h is None and cu is not None and r["housing"] != "NO":
            st = str(cu.status)
            if st == "modelled":
                h = int(cu.most_homes)
            elif "under 40" in st or "façade under 3" in st:
                h = 0
        if r["housing"] == "NO":
            ans.append("not allowed"); why.append("zone %s does not admit ground-floor housing" % r.get("pgm_key", ""))
        elif h is not None and (h == 0 or (isinstance(h, float) and np.isnan(h))):
            ans.append("not liveable"); why.append("no home that passes the rules fits" + (" in its Catastro unit (%s, %.0f m²)" % (cu.unit_use, cu.unit_m2) if cu is not None and ref not in homes else ""))
        elif d is not None and d < 1.0:
            ans.append("not liveable"); why.append("dark: predicted daylight factor %.1f %% (Bars's model)" % d)
        elif r["retail_100m"] <= cut:
            ans.append("keep it a shop"); why.append("only %d shops within 100 m (lowest 10 %% of the city)" % r["retail_100m"])
        elif h is not None:
            src = " in its Catastro unit (%s, %.0f m²)" % (cu.unit_use, cu.unit_m2) if cu is not None and ref not in homes else ""
            ans.append("candidate"); why.append("%d home%s fit%s; daylight %.1f %%" % (h, "" if h == 1 else "s", src, d) if d is not None else "%d home%s fit%s" % (h, "" if h == 1 else "s", src))
        else:
            ans.append("not modelled"); why.append("zone and street allow it; no clean outline yet (shared ground floor or no street façade)")
    z["answer"], z["why"] = ans, why
    z["homes"] = [homes.get(r) if r in homes else (int(cat[str(i)].most_homes) if str(i) in cat and cat[str(i)].status == "modelled" else None)
                  for r, i in zip(ref14, z["ID_Global"])]
    z["daylight_df"] = [df.get(r) for r in ref14]
    z["lit_depth_m"] = [lit.get(r) for r in ref14]
    cols = ["ID_Global", "Direccio_Unica", "Nom_Barri", "Nom_Districte", "X_UTM_ETRS89", "Y_UTM_ETRS89", "housing", "pgm_key",
            "active_100m", "retail_100m", "homes", "daylight_df", "lit_depth_m", "answer", "why"]
    z[[c_ for c_ in cols if c_ in z.columns]].to_csv(OUT / "avoid.csv", index=False, encoding="utf-8")
    s = {"premises": int(len(z)), "answers": z["answer"].value_counts().to_dict(), "retail_100m_cut": cut,
         "median_retail_100m": float(z["retail_100m"].median()),
         "by_district": {d: g["answer"].value_counts().to_dict() for d, g in z.groupby("Nom_Districte")}}
    json.dump(s, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: s[k] for k in ("premises", "answers", "retail_100m_cut", "median_retail_100m")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
