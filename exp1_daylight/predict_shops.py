"""Nomad - predict daylight for real Barcelona shops with the Experiment 1 model.

Run in the "ai-methods" environment, from the nomad repo root:
    python exp1_daylight/predict_shops.py
Reads : exp1_daylight/results.csv (the 50 Radiance runs) and exp1_daylight/shops_bcn.csv
Writes: exp1_daylight/shops_bcn_pred.csv     every shop with its predicted daylight factor
        exp1_daylight/shops_validation.csv   5 real shops for the Grasshopper check (ids 0-4)
        outputs/shops_bcn_map.png            map of the shops coloured by predicted daylight

Then, after simulating the 5 validation shops in Grasshopper (record to results_shops.csv):
    python exp1_daylight/predict_shops.py --compare
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
FEATURES = ["depth_m", "width_m", "floor_height_m", "wwr", "win_height_m", "sill_m", "head_m",
            "lit_facades", "obs_dist_m", "obs_height_m", "obs_angle_deg", "lit_share"]
VARIANT_COLS = ["id", "depth_m", "width_m", "floor_height_m", "wwr", "win_height_target_m", "obs_dist_m",
                "obs_height_m", "lit_facades", "win_height_m", "sill_m", "head_m"]


def add_features(df):
    df = df.copy()
    df["obs_angle_deg"] = np.degrees(np.arctan2(df["obs_height_m"], df["obs_dist_m"]))
    df["lit_share"] = np.minimum(1.0, df["lit_facades"] * 2.5 * df["head_m"] / df["depth_m"])
    return df


def make_model():
    try:
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=400, max_depth=3, learning_rate=0.05,
                            subsample=0.9, colsample_bytree=0.9, random_state=0)
    except Exception:
        from sklearn.ensemble import HistGradientBoostingRegressor
        print("xgboost not available -> scikit-learn gradient boosting")
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=400,
                                             min_samples_leaf=3, random_state=0)


def predict():
    train = add_features(pd.read_csv(HERE / "results.csv").dropna(subset=["mean_df"]))
    shops = add_features(pd.read_csv(HERE / "shops_bcn.csv"))
    model = make_model()
    model.fit(train[FEATURES].to_numpy(float), train["mean_df"].to_numpy(float))  # all 50 runs
    shops["pred_mean_df"] = model.predict(shops[FEATURES].to_numpy(float)).round(3)
    shops.to_csv(HERE / "shops_bcn_pred.csv", index=False, encoding="utf-8")

    n, inside = len(shops), int(shops["in_training_range"].sum())
    print("shops predicted: %d (inside training ranges: %d)" % (n, inside))
    print("predicted mean DF: median %.2f %%, below 1 %%: %d shops (%.0f %%)" % (
        shops["pred_mean_df"].median(), (shops["pred_mean_df"] < 1).sum(), 100 * (shops["pred_mean_df"] < 1).mean()))
    show = ["id", "address", "depth_m", "width_m", "obs_dist_m", "obs_height_m", "pred_mean_df"]
    print("\ndarkest 5:\n", shops.nsmallest(5, "pred_mean_df")[show].to_string(index=False))
    print("\nbrightest 5:\n", shops.nlargest(5, "pred_mean_df")[show].to_string(index=False))

    # 5 shops for the Grasshopper check: inside the ranges, spread from dark to bright
    pool = shops[shops["in_training_range"] == 1].sort_values("pred_mean_df")
    if len(pool) < 5:
        pool = shops.sort_values("pred_mean_df")
    pick = pool.iloc[np.linspace(0, len(pool) - 1, 5).round().astype(int)].copy()
    pick["shop_id"] = pick["id"]
    pick["id"] = range(5)
    pick[VARIANT_COLS + ["shop_id", "address", "pred_mean_df"]].to_csv(
        HERE / "shops_validation.csv", index=False, encoding="utf-8")
    print("\nsaved exp1_daylight/shops_validation.csv (ids 0-4) for Grasshopper")

    # map without a basemap (no tile server needed)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 7))
    sc = ax.scatter(shops["lon"], shops["lat"], c=shops["pred_mean_df"].clip(0, 4), s=4, cmap="RdYlBu_r")
    ax.set_aspect(1 / np.cos(np.radians(shops["lat"].mean())))
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Predicted daylight factor of %d Barcelona shops (v0)" % n, fontsize=11)
    fig.colorbar(sc, ax=ax, shrink=0.7, label="predicted mean DF (%)")
    fig.tight_layout()
    fig.savefig(OUT / "shops_bcn_map.png", dpi=200)
    print("saved outputs/shops_bcn_map.png")


def compare():
    val = pd.read_csv(HERE / "shops_validation.csv")
    sim = pd.read_csv(HERE / "results_shops.csv")[["id", "mean_df"]]
    m = val.merge(sim, on="id", how="inner")
    m["error"] = (m["pred_mean_df"] - m["mean_df"]).round(3)
    print(m[["id", "address", "depth_m", "width_m", "obs_dist_m", "obs_height_m", "pred_mean_df", "mean_df", "error"]]
          .to_string(index=False))
    print("\nmean absolute error on %d real shops: %.2f DF points" % (len(m), m["error"].abs().mean()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true")
    (compare if ap.parse_args().compare else predict)()
