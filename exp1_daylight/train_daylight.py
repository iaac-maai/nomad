"""Experiment 1, step 3: train the daylight predictor and compare it with the simple rule.

Model:    XGBoost (gradient-boosted trees) predicts the mean daylight factor of a floor
          from its parameters, without running a simulation.
Baseline: the light-band rule. The lit share of the floor is
          min(1, lit_facades * 2.5 * window head height / depth); a straight line then maps
          that share to a daylight factor. Does ML beat this rule?

Run from the repo root:
    python exp1_daylight/train_daylight.py
    python exp1_daylight/train_daylight.py --results exp1_daylight/results_FAKE.csv   # test run
Outputs: outputs/exp1_pred_vs_sim.png, outputs/exp1_importance.png, outputs/exp1_summary.md
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
FEATURES = ["depth_m", "width_m", "floor_height_m", "wwr", "win_height_m", "sill_m", "head_m",
            "lit_facades", "obs_dist_m", "obs_height_m", "obs_angle_deg", "lit_share"]


def make_model():
    try:
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=400, max_depth=3, learning_rate=0.05,
                            subsample=0.9, colsample_bytree=0.9, random_state=0), "XGBoost"
    except Exception:  # not installed, or (Mac) libomp missing
        from sklearn.ensemble import HistGradientBoostingRegressor
        if not getattr(make_model, "warned", False):
            print("xgboost not installed -> using scikit-learn gradient boosting instead")
            make_model.warned = True
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=400,
                                             min_samples_leaf=3, random_state=0), "Gradient boosting (sklearn)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "results.csv"))
    ap.add_argument("--target", default="mean_df", choices=["mean_df", "share_df2"])
    ap.add_argument("--test", type=float, default=0.2, help="share of variants kept for testing")
    args = ap.parse_args()

    res = pd.read_csv(args.results)
    df = res.copy()
    df = df.dropna(subset=[args.target])
    if len(df) < 15:
        raise SystemExit("Only %d simulated variants. Run at least 15 (50 is the plan)." % len(df))

    # two engineered features an architect would think of
    df["obs_angle_deg"] = np.degrees(np.arctan2(df["obs_height_m"], df["obs_dist_m"]))
    df["lit_share"] = np.minimum(1.0, df["lit_facades"] * 2.5 * df["head_m"] / df["depth_m"])

    X, y = df[FEATURES].to_numpy(float), df[args.target].to_numpy(float)
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(df))
    n_test = max(5, int(round(args.test * len(df))))
    test, train = idx[:n_test], idx[n_test:]

    model, model_name = make_model()
    model.fit(X[train], y[train])
    pred = model.predict(X[test])

    base = LinearRegression().fit(df[["lit_share"]].to_numpy()[train], y[train])
    base_pred = base.predict(df[["lit_share"]].to_numpy()[test])

    # 5-fold cross-validation on all data: more stable with only 50 samples
    cv_model, _ = make_model()
    cv_pred = cross_val_predict(cv_model, X, y, cv=KFold(5, shuffle=True, random_state=0))

    m = {
        "model": model_name, "target": args.target, "n_variants": int(len(df)),
        "n_train": int(len(train)), "n_test": int(len(test)),
        "test_r2_model": round(float(r2_score(y[test], pred)), 3),
        "test_mae_model": round(float(mean_absolute_error(y[test], pred)), 3),
        "test_r2_rule": round(float(r2_score(y[test], base_pred)), 3),
        "test_mae_rule": round(float(mean_absolute_error(y[test], base_pred)), 3),
        "cv5_r2_model": round(float(r2_score(y, cv_pred)), 3),
        "cv5_mae_model": round(float(mean_absolute_error(y, cv_pred)), 3),
    }

    OUT.mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    unit = "daylight factor (%)" if args.target == "mean_df" else "share of floor with DF >= 2 %"
    fig, ax = plt.subplots(figsize=(5.2, 5))
    lo, hi = float(min(y.min(), pred.min(), base_pred.min())), float(max(y.max(), pred.max(), base_pred.max()))
    ax.plot([lo, hi], [lo, hi], color="#999999", lw=1, label="perfect prediction")
    ax.scatter(y[test], base_pred, s=36, color="#E58C8C", label="light-band rule  R² %.2f" % m["test_r2_rule"])
    ax.scatter(y[test], pred, s=36, color="#2BA8A2", label="%s  R² %.2f" % (model_name, m["test_r2_model"]))
    ax.set_xlabel("simulated (Ladybug) " + unit)
    ax.set_ylabel("predicted " + unit)
    fake = "FAKE" in Path(args.results).name.upper()
    ax.set_title(("FAKE TEST DATA - " if fake else "") + "Daylight predictor v0: %d test variants" % len(test))
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "exp1_pred_vs_sim.png", dpi=200)

    # which parameters matter most (permutation importance on the full data)
    from sklearn.inspection import permutation_importance
    full, _ = make_model()
    full.fit(X, y)
    imp = permutation_importance(full, X, y, n_repeats=20, random_state=0).importances_mean
    order = np.argsort(imp)
    fig2, ax2 = plt.subplots(figsize=(5.2, 4))
    ax2.barh([FEATURES[k] for k in order], imp[order], color="#2BA8A2")
    ax2.set_xlabel("importance (drop in R² when shuffled)")
    ax2.set_title("What drives daylight in the model")
    fig2.tight_layout()
    fig2.savefig(OUT / "exp1_importance.png", dpi=200)

    lines = [
        "# Exp 4 (folder exp1_daylight) - daylight predictor v0: results" + ("  (FAKE TEST DATA - do not present)" if fake else ""),
        "",
        "| | %s | Light-band rule |" % model_name,
        "| --- | --- | --- |",
        "| R² on %d test variants | %.2f | %.2f |" % (len(test), m["test_r2_model"], m["test_r2_rule"]),
        "| Mean absolute error | %.2f | %.2f |" % (m["test_mae_model"], m["test_mae_rule"]),
        "| R² with 5-fold cross-validation (all %d) | %.2f | - |" % (len(df), m["cv5_r2_model"]),
        "",
        "Target: %s. Trained on %d variants, tested on %d it never saw." % (unit, len(train), len(test)),
    ]
    (OUT / "exp1_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "exp1_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print("\nSaved: outputs/exp1_pred_vs_sim.png, outputs/exp1_importance.png, outputs/exp1_summary.md")


if __name__ == "__main__":
    main()
