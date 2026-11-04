"""Nomad - the website's daylight data (Exp 4, folder exp1_daylight), from Bars's current results.

Nothing is typed in: thresholds, counts, the number of simulations and the validation error are read
or recomputed from exp1_daylight/.
Reads : exp1_daylight/daylight_thresholds.json   EN 17037 D_target / D_minimum for Barcelona (TMYx weather file)
        exp1_daylight/results.csv                 the Radiance simulations
        exp1_daylight/shops_bcn_pred.csv          every empty shop of the 2024 census, with its predicted lit depth
        exp1_daylight/shops_validation.csv + results_shops.csv   the 5 real shops checked in Radiance
Writes: Bhavini_NOMAD Files/04_Website/data/daylight.json
Run from the nomad repo root, in the "ai-methods" environment:
    python "Bhavini_NOMAD Files/02_Code/src/app/daylight_site.py"
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
EXP = REPO / "exp1_daylight"
OUT = REPO / "Bhavini_NOMAD Files" / "04_Website" / "data" / "daylight.json"
sys.path.insert(0, str(EXP))
import predict_shops as ps  # noqa: E402  (Bars's script: the same features, lit-depth rule and model)

CLASS = {"livable": "L", "needs_change": "C", "not_livable": "N"}


def validation_mae(d_target):
    """Mean absolute error (m) of the predicted lit depth on the 5 real shops simulated in Radiance:
    the same steps as `python exp1_daylight/predict_shops.py --compare`."""
    val = pd.read_csv(EXP / "shops_validation.csv")
    sim = pd.read_csv(EXP / "results_shops.csv")
    train = ps.add_features(pd.read_csv(EXP / "results.csv").dropna(subset=["mean_df"]))
    train["lit_depth_m"] = ps.lit_depth(train, d_target)
    train = train.dropna(subset=["lit_depth_m"])
    model = ps.make_model()
    model.fit(train[ps.FEATURES].to_numpy(float), train["lit_depth_m"].to_numpy(float))
    v = ps.add_features(val)
    v["lit_pred_m"] = np.clip(model.predict(v[ps.FEATURES].to_numpy(float)), 0, v["depth_m"]).round(2)
    s = sim[["id", "df_values"]].merge(v[["id", "depth_m", "lit_pred_m"]], on="id")
    s["lit_sim_m"] = ps.lit_depth(s, d_target)
    return len(s), round(float((s["lit_pred_m"] - s["lit_sim_m"]).round(2).abs().mean()), 2)


def main():
    th = json.loads((EXP / "daylight_thresholds.json").read_text(encoding="utf-8"))
    sims = pd.read_csv(EXP / "results.csv").dropna(subset=["mean_df"])
    shops = pd.read_csv(EXP / "shops_bcn_pred.csv", dtype={"building_reference": str})
    n_val, mae = validation_mae(th["D_target_pct"])

    by_key = {}                                    # "REF14|STREET NUM" -> [[lon, lat, lit_m, share, class, check], ...]
    for r in shops.itertuples(index=False):
        if pd.isna(r.lit_depth_m) or r.daylight_class not in CLASS:
            continue
        by_key.setdefault("%s|%s" % (r.building_reference, r.address), []).append(
            [round(float(r.lon), 6), round(float(r.lat), 6), round(float(r.lit_depth_m), 2),
             round(float(r.lit_floor_share), 3), CLASS[r.daylight_class], int(r.check_street)])

    counts = shops["daylight_class"].value_counts().to_dict()
    data = {
        "about": "Exp 4 (folder exp1_daylight): Bars's daylight model. Built by 02_Code/src/app/daylight_site.py",
        "simulations": int(len(sims)), "simulator": "Radiance (Ladybug/Honeybee)", "model": "XGBoost",
        "thresholds": {"method": "EN 17037", "weather": th["source"],
                       "D_target_pct": th["D_target_pct"], "D_minimum_pct": th["D_minimum_pct"]},
        "classes": {"home_min_m2": ps.HOME_MIN_M2, "room_min_m": ps.ROOM_MIN_M},
        "validation": {"shops": n_val, "lit_depth_mae_m": mae},
        "census": "Cens de locals en planta baixa 2024, Ajuntament de Barcelona, Open Data BCN (CC BY 4.0)",
        "counts": {"shops": int(len(shops)), "districts": int(shops["district"].nunique()),
                   "livable": int(counts.get("livable", 0)), "needs_change": int(counts.get("needs_change", 0)),
                   "not_livable": int(counts.get("not_livable", 0)), "check_street": int(shops["check_street"].sum())},
        "assumed": {k: float(shops[k].mode()[0]) for k in ("floor_height_m", "wwr", "head_m", "lit_facades")},
        "cols": ["lon", "lat", "lit_m", "share", "class", "check"],
        "shops": by_key,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("saved %s: %d simulations, %d shops (%d addresses), D_target %.2f %%, validation %d shops, %.2f m"
          % (OUT.relative_to(REPO), data["simulations"], data["counts"]["shops"], len(by_key),
             th["D_target_pct"], n_val, mae))
    print("classes:", {k: data["counts"][k] for k in ("livable", "needs_change", "not_livable")},
          "| streets to check:", data["counts"]["check_street"])


if __name__ == "__main__":
    main()
