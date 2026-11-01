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
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NEW_VALIDATION = False
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


def lit_depth(df, d_target):
    """Area-equivalent depth (m) of the floor that reaches the EN 17037 target DF, from the
    per-sensor values Grasshopper saved (df_values). share x depth = metres of lit floor."""
    out = []
    for vals, depth in zip(df["df_values"], df["depth_m"]):
        try:
            v = np.array(json.loads(vals), float)
            out.append(round(float((v >= d_target).mean()) * depth, 2))
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.array(out)


ROOM_MIN_M = 2.8   # Decret 141/2012, Annex 1: the living room must fit a 2.80 m circle


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


def cross_mae(X, y, k=5):
    idx = np.random.default_rng(0).permutation(len(y))
    errs = []
    for f in range(k):
        te = idx[f::k]
        tr = np.setdiff1d(idx, te)
        m = make_model()
        m.fit(X[tr], y[tr])
        errs.append(np.abs(m.predict(X[te]) - y[te]))
    return float(np.concatenate(errs).mean())


def predict():
    train = add_features(pd.read_csv(HERE / "results.csv").dropna(subset=["mean_df"]))
    shops = add_features(pd.read_csv(HERE / "shops_bcn.csv"))
    model = make_model()
    model.fit(train[FEATURES].to_numpy(float), train["mean_df"].to_numpy(float))  # all 50 runs
    shops["pred_mean_df"] = model.predict(shops[FEATURES].to_numpy(float)).round(3)
    # v0 flag: a street under 8 m in the Eixample is suspicious unless it is a passage (PTGE)
    shops["check_street"] = ((shops["obs_dist_m"] < 8) &
                             ~shops["address"].astype(str).str.startswith("PTGE")).astype(int)
    print("streets to check by hand (under 8 m, not a passage): %d" % shops["check_street"].sum())

    # livable / needs a change / not livable, from the EN 17037 target DF for Barcelona.
    # A second model predicts the LIT DEPTH: how many metres of floor reach the target DF.
    th_file = HERE / "daylight_thresholds.json"
    if th_file.exists() and "df_values" in train.columns:
        th = json.loads(th_file.read_text(encoding="utf-8"))
        dt = th["D_target_pct"]
        train["lit_depth_m"] = lit_depth(train, dt)
        tr = train.dropna(subset=["lit_depth_m"])
        cv_mae = cross_mae(tr[FEATURES].to_numpy(float), tr["lit_depth_m"].to_numpy(float))
        m2 = make_model()
        m2.fit(tr[FEATURES].to_numpy(float), tr["lit_depth_m"].to_numpy(float))
        shops["lit_depth_m"] = np.clip(m2.predict(shops[FEATURES].to_numpy(float)), 0, shops["depth_m"]).round(2)
        shops["lit_floor_share"] = (shops["lit_depth_m"] / shops["depth_m"]).round(3)
        shops["daylight_class"] = np.select(
            [shops["lit_floor_share"] >= 0.5, shops["lit_depth_m"] >= ROOM_MIN_M],
            ["livable", "needs_change"], default="not_livable")
        print("\nlit depth = metres of floor at DF >= %.2f %% (EN 17037 300 lx, Barcelona)" % dt)
        print("   lit-depth model, 5-fold CV mean error: %.2f m (on %d simulations)" % (cv_mae, len(tr)))
        print("   classes: livable = lit over >= 50 % of the floor (EN 17037 target);")
        print("            needs_change = lit zone >= %.1f m (a living room fits, Decret 141); not_livable = less" % ROOM_MIN_M)
        for c in ["livable", "needs_change", "not_livable"]:
            k = int((shops["daylight_class"] == c).sum())
            print("   %-13s %4d shops (%.0f %%)" % (c, k, 100 * k / len(shops)))
        print("   lit depth: median %.1f m, shop depth: median %.1f m" % (
            shops["lit_depth_m"].median(), shops["depth_m"].median()))
    else:
        print("\nno daylight_thresholds.json or no df_values in results.csv: classes skipped")
    shops.to_csv(HERE / "shops_bcn_pred.csv", index=False, encoding="utf-8")

    n, inside = len(shops), int(shops["in_training_range"].sum())
    print("shops predicted: %d (inside training ranges: %d)" % (n, inside))
    print("predicted mean DF: median %.2f %%, below 1 %%: %d shops (%.0f %%)" % (
        shops["pred_mean_df"].median(), (shops["pred_mean_df"] < 1).sum(), 100 * (shops["pred_mean_df"] < 1).mean()))
    show = ["id", "address", "depth_m", "width_m", "obs_dist_m", "obs_height_m", "pred_mean_df"]
    print("\ndarkest 5:\n", shops.nsmallest(5, "pred_mean_df")[show].to_string(index=False))
    print("\nbrightest 5:\n", shops.nlargest(5, "pred_mean_df")[show].to_string(index=False))

    # 5 shops for the Grasshopper check: inside the ranges, spread from dark to bright.
    # Kept once made, because results_shops.csv belongs to these exact 5 shops.
    if (HERE / "shops_validation.csv").exists() and not NEW_VALIDATION:
        print("\nkept exp1_daylight/shops_validation.csv (use --new-validation to pick 5 new shops)")
    else:
        pick_validation(shops)
    draw_map(shops, n)


def pick_validation(shops):
    pool = shops[shops["in_training_range"] == 1].sort_values("pred_mean_df")
    if len(pool) < 5:
        pool = shops.sort_values("pred_mean_df")
    pick = pool.iloc[np.linspace(0, len(pool) - 1, 5).round().astype(int)].copy()
    pick["shop_id"] = pick["id"]
    pick["id"] = range(5)
    pick[VARIANT_COLS + ["shop_id", "address", "pred_mean_df"]].to_csv(
        HERE / "shops_validation.csv", index=False, encoding="utf-8")
    print("\nsaved exp1_daylight/shops_validation.csv (ids 0-4) for Grasshopper")


def draw_map(shops, n):
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
    th_file = HERE / "daylight_thresholds.json"
    sim_all = pd.read_csv(HERE / "results_shops.csv")
    if th_file.exists() and "df_values" in sim_all.columns:
        dt = json.loads(th_file.read_text(encoding="utf-8"))["D_target_pct"]
        # predict from the SAME inputs Grasshopper simulated (shops_validation.csv),
        # not from today's shops_bcn.csv, whose street widths may have been corrected since
        train = add_features(pd.read_csv(HERE / "results.csv").dropna(subset=["mean_df"]))
        train["lit_depth_m"] = lit_depth(train, dt)
        train = train.dropna(subset=["lit_depth_m"])
        m2 = make_model()
        m2.fit(train[FEATURES].to_numpy(float), train["lit_depth_m"].to_numpy(float))
        v2 = add_features(val)
        v2["lit_pred_m"] = np.clip(m2.predict(v2[FEATURES].to_numpy(float)), 0, v2["depth_m"]).round(2)
        s2 = sim_all[["id", "df_values"]].merge(v2[["id", "address", "depth_m", "lit_pred_m"]], on="id")
        s2["lit_sim_m"] = lit_depth(s2, dt)
        s2["lit_error_m"] = (s2["lit_pred_m"] - s2["lit_sim_m"]).round(2)
        print("\nlit depth (m of floor at DF >= %.2f %%):" % dt)
        print(s2[["id", "address", "depth_m", "lit_pred_m", "lit_sim_m", "lit_error_m"]].to_string(index=False))
        print("mean absolute error: %.2f m" % s2["lit_error_m"].abs().mean())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--new-validation", action="store_true", help="pick 5 new validation shops (overwrites the old ones)")
    args = ap.parse_args()
    NEW_VALIDATION = args.new_validation
    (compare if args.compare else predict)()
