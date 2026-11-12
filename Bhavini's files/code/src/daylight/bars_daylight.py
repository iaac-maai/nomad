"""Nomad - Bars's daylight model (Experiment 1, github.com/iaac-maai/nomad) applied to NOMAD's real Barcelona shops.

Bars simulated 50 ground-floor variants with Ladybug/Honeybee (Radiance daylight factor on a sensor grid) and trained
XGBoost to predict them (R² 0.80 on 10 unseen variants, rule of thumb 0.65). This script uses HIS training data
(external/bars-nomad/exp1_daylight/results.csv), HIS features, model settings and assumptions, unchanged:
  features    depth, width, floor height, window-to-wall ratio, window height / sill / head, lit façades,
              distance and height of the building across the street, obstruction angle, light-band share
  assumed     floor height 4.0 m, WWR 0.6, window 3.0 m tall from 0.9 m (head 3.9 m), as in his shops_from_catastro.py
  across      a ray straight out of the street façade, up to 60 m; first other building at >= 3 m;
              its height = 5 m ground floor + 3 m per upper floor (Catastro floors); nothing hit = 60 m, height 0
What NOMAD adds: the shop geometry comes from NOMAD's clean real-shop shells (results/real_shops/shells.json: the shop's
outline and its street façade from the MUC), so depth and width are measured from the street façade, not from a
rectangle around the building; lit façades = 2 when the shop has street façades facing two directions (a corner).
Two models are trained on his 50 runs: mean daylight factor (his target) and the share of the floor with DF >= 2 %
(his second target, "share_df2"). share x depth = the lit depth: how far from the window the floor still gets
DF >= 2 % - the liveable "blue spot" that the check uses instead of the fixed 5.5 m assumption.
Out: results/daylight/real_shops_daylight.csv, results/daylight/summary.json, results/daylight/lit_depth.json
Run: .venv/Scripts/python src/daylight/bars_daylight.py
"""
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
BARS = ROOT / "external" / "bars-nomad" / "exp1_daylight"
OUT = ROOT / "results" / "daylight"
FEATURES = ["depth_m", "width_m", "floor_height_m", "wwr", "win_height_m", "sill_m", "head_m",
            "lit_facades", "obs_dist_m", "obs_height_m", "obs_angle_deg", "lit_share"]      # Bars's list, same order
FLOOR_H, WWR, WIN_TARGET, SEARCH = 4.0, 0.6, 3.0, 60.0                                        # Bars's assumptions
RANGES = {"depth_m": (8, 25), "width_m": (4, 12), "obs_dist_m": (8, 20), "obs_height_m": (12, 25)}   # his training ranges


def add_features(df):                                            # copied from Bars's predict_shops.add_features
    df = df.copy()
    df["obs_angle_deg"] = np.degrees(np.arctan2(df["obs_height_m"], df["obs_dist_m"]))
    df["lit_share"] = np.minimum(1.0, df["lit_facades"] * 2.5 * df["head_m"] / df["depth_m"])
    return df


def make_model():                                                # Bars's settings
    from xgboost import XGBRegressor
    return XGBRegressor(n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=0)


def height_from_floors(n):
    return 5.0 + 3.0 * (n - 1) if n and n >= 1 else np.nan


def window():                                                    # Bars's window from his assumptions
    win_h = min(max(WIN_TARGET, WWR * FLOOR_H * 1.05), FLOOR_H - 0.3)
    sill = max(min(0.9, FLOOR_H - win_h - 0.1), 0.1)
    return round(win_h, 2), round(sill, 2), round(sill + win_h, 2)


def shop_geometry(s):
    """depth (m) perpendicular to the longest street façade edge, width = street façade length, façade directions."""
    o = np.asarray(s["origin_utm"], float)
    poly = Polygon(s["outline"])
    edges = [(np.asarray(a, float), np.asarray(b, float)) for a, b in s["street"]]
    if not edges or not poly.is_valid or poly.area < 1:
        return None
    lens = [float(np.hypot(*(b - a))) for a, b in edges]
    a, b = edges[int(np.argmax(lens))]
    t = (b - a) / np.hypot(*(b - a))
    n = np.array([-t[1], t[0]])
    mid = (a + b) / 2
    if poly.contains(Point(*(mid + 0.5 * n))):
        n = -n                                                   # n points out to the street
    xy = np.asarray(poly.exterior.coords)
    depth = float(np.max((xy - a) @ (-n)))                       # how far the shop reaches back from the façade line
    dirs = set()
    for (p, q), L in zip(edges, lens):
        if L >= 2.0:
            ang = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180
            dirs.add(round(ang / 30))
    lit = 2 if len({d % 6 for d in dirs}) >= 2 and sum(lens) - max(lens) >= 3.0 else 1
    return {"depth_m": round(depth, 2), "width_m": round(sum(lens), 2), "lit_facades": lit,
            "start_utm": (o + mid).tolist(), "normal": n.tolist(), "poly_utm": [(x + o[0], y + o[1]) for x, y in xy]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    train = add_features(pd.read_csv(BARS / "results.csv").dropna(subset=["mean_df"]))
    print("Bars's simulations:", len(train), "variants")
    m_df, m_sh = make_model(), make_model()
    m_df.fit(train[FEATURES].to_numpy(float), train["mean_df"].to_numpy(float))
    m_sh.fit(train[FEATURES].to_numpy(float), train["share_df2"].to_numpy(float))

    S = json.load(open(ROOT / "results" / "real_shops" / "shells.json", encoding="utf-8"))
    keep = pd.read_csv(ROOT / "results" / "real_shops" / "clean_shops.csv", dtype=str)
    keep = keep[keep["nomad_runs"].astype(str).str.lower() == "true"].drop_duplicates("ref14")
    B = json.load(gzip.open(ROOT / "data" / "barcelona" / "catastro" / "buildings.json.gz", "rt", encoding="utf-8"))
    polys, heights, refs = [], [], []
    for ref, b in B.items():
        for p in b.get("parts", []):
            if p.get("up", 0) < 1:
                continue
            for ring in p["poly"]:
                try:
                    g = Polygon(ring[0])
                except Exception:
                    continue
                if g.is_valid and g.area > 2:
                    polys.append(g); heights.append(height_from_floors(p["up"])); refs.append(ref)
    tree = STRtree(polys)
    print("Catastro building parts:", len(polys))

    win_h, sill, head = window()
    rows = []
    for _, r in keep.iterrows():
        s = S.get(r["ref14"])
        if not s:
            continue
        g = shop_geometry(s)
        if not g:
            continue
        st, n = np.asarray(g["start_utm"]), np.asarray(g["normal"])
        ray = LineString([st + 0.3 * n, st + SEARCH * n])
        p0 = Point(*st)
        od, oh = np.nan, np.nan
        for j in tree.query(ray, predicate="intersects"):
            if refs[j] == r["ref14"]:
                continue                                         # its own building is not across the street
            d = p0.distance(ray.intersection(polys[j]))
            if d >= 3.0 and (np.isnan(od) or d < od):
                od, oh = d, heights[j]
        no_opp = int(np.isnan(od))
        if no_opp:
            od, oh = SEARCH, 0.0
        rows.append({"ref14": r["ref14"], "address": r["Direccio_Unica"], "district": r["Nom_Districte"], "barri": r["Nom_Barri"],
                     "x": float(r["X_UTM_ETRS89"]), "y": float(r["Y_UTM_ETRS89"]),
                     "depth_m": g["depth_m"], "width_m": g["width_m"], "lit_facades": g["lit_facades"],
                     "obs_dist_m": round(od, 2), "obs_height_m": round(oh, 2), "no_opposite": no_opp,
                     "floor_height_m": FLOOR_H, "wwr": WWR, "win_height_m": win_h, "sill_m": sill, "head_m": head})
    df = add_features(pd.DataFrame(rows))
    X = df[FEATURES].to_numpy(float)
    df["pred_mean_df"] = m_df.predict(X).round(3)
    df["pred_share_df2"] = np.clip(m_sh.predict(X), 0, 1).round(3)
    df["lit_depth_m"] = (df["pred_share_df2"] * df["depth_m"]).round(2)
    inside = np.ones(len(df), bool)
    for c, (lo, hi) in RANGES.items():
        inside &= df[c].between(lo, hi).to_numpy()
    df["in_training_range"] = inside.astype(int)
    df["band"] = pd.cut(df["pred_mean_df"], [-1, 1, 2, 99], labels=["dark (DF < 1 %)", "some daylight (1-2 %)", "well lit (DF >= 2 %)"]).astype(str)
    df.to_csv(OUT / "real_shops_daylight.csv", index=False, encoding="utf-8")
    json.dump({r.ref14: {"df": r.pred_mean_df, "share": r.pred_share_df2, "lit_depth": r.lit_depth_m, "in_range": int(r.in_training_range)}
               for r in df.itertuples()}, open(OUT / "lit_depth.json", "w"), separators=(",", ":"))
    summ = {"shops": len(df), "in_training_range": int(df["in_training_range"].sum()),
            "median_pred_df": float(df["pred_mean_df"].median()), "bands": df["band"].value_counts().to_dict(),
            "median_lit_depth_m": float(df["lit_depth_m"].median()), "median_depth_m": float(df["depth_m"].median()),
            "median_obs_dist_m": float(df["obs_dist_m"].median()), "no_opposite": int(df["no_opposite"].sum()),
            "source": "Bars Babila, iaac-maai/nomad exp1_daylight (50 Ladybug/Honeybee runs, XGBoost)"}
    json.dump(summ, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
