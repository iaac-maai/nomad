"""Nomad - map of the predicted daylight of empty shops on top of the Catastro buildings.

Run in the "cadaster" conda environment, from the nomad repo root (after predict_shops.py):
    python exp1_daylight/map_shops.py --data C:/Users/barsb/nomad-hypercadaster_ES/data
    python exp1_daylight/map_shops.py --data C:/Users/barsb/nomad-hypercadaster_ES/data --basemap
Reads : exp1_daylight/shops_bcn_pred.csv, exp1_daylight/shops_validation.csv,
        <data>/barcelona_data.pkl.gz (Catastro building footprints)
Writes: outputs/shops_map_catastro.png        whole district
        outputs/shops_map_catastro_zoom.png   zoom around the 5 validation shops
--basemap adds an Esri grey street map under the buildings (needs internet; skipped if it fails).
Credits to show on the slide: Catastro (Direccion General del Catastro) via hypercadaster_ES (EUPL-1.2);
Open Data BCN ground-floor census (CC BY 4.0); basemap Esri.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
CLASSES = [("not_livable", "#c0392b", "not livable: daylit zone under 2.8 m deep"),
           ("needs_change", "#f0a030", "needs a change: a living room fits in daylight"),
           ("livable", "#2e86c1", "a 36 m2 home fits in the daylit zone")]
OUT = HERE.parent / "outputs"


def draw(ax, buildings, shops, val, bbox, basemap, title, label_all):
    xmin, ymin, xmax, ymax = bbox
    b = buildings.cx[xmin:xmax, ymin:ymax]
    b.plot(ax=ax, color="#d9d6cf", edgecolor="#b5b0a6", linewidth=0.2, zorder=1)
    s = shops.cx[xmin:xmax, ymin:ymax]
    if "daylight_class" in s.columns:   # 3 classes from the EN 17037 thresholds
        for cls, col, name in CLASSES:
            part = s[s["daylight_class"] == cls]
            ax.scatter(part.geometry.x, part.geometry.y, color=col, s=16 if label_all else 9,
                       edgecolor="black", linewidth=0.2, zorder=3,
                       label="%s (%d)" % (name, int((shops["daylight_class"] == cls).sum())))
        ax.legend(loc="upper left", fontsize=8, frameon=True)
        sc = None
    else:
        sc = ax.scatter(s.geometry.x, s.geometry.y, c=s["pred_mean_df"].clip(0.5, 3.0), cmap="RdYlBu_r",
                        vmin=0.5, vmax=3.0, s=14 if label_all else 7, edgecolor="black", linewidth=0.2, zorder=3)
    v = val.cx[xmin:xmax, ymin:ymax] if not val.empty else val
    if not v.empty:
        ax.scatter(v.geometry.x, v.geometry.y, s=160, facecolor="none", edgecolor="black", linewidth=1.4, zorder=4)
        for _, r in v.iterrows():
            ax.annotate("%d  %s\npred %.2f | sim %s" % (r["id"], r["address"], r["pred_mean_df"], r["sim"]),
                        (r.geometry.x, r.geometry.y), xytext=(8, 8), textcoords="offset points",
                        fontsize=7 if label_all else 6, family="monospace", zorder=5,
                        bbox=dict(boxstyle="square,pad=0.2", fc="white", ec="black", lw=0.5))
    if basemap:
        try:
            import contextily as cx
            cx.add_basemap(ax, crs="EPSG:25831", source=cx.providers.Esri.WorldGrayCanvas, zorder=0)
        except Exception as e:
            print("basemap skipped:", e)
    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=11)
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="hypercadaster data folder")
    ap.add_argument("--basemap", action="store_true", help="add an Esri grey street map (internet)")
    ap.add_argument("--district", default="", help="only this district, e.g. Eixample (empty = all shops)")
    ap.add_argument("--show-validation", action="store_true", help="circle and label the 5 Grasshopper validation shops")
    ap.add_argument("--tag", default="", help="added to the file names, e.g. bcn -> shops_map_bcn.png")
    args = ap.parse_args()
    tag = ("_" + args.tag) if args.tag else ""

    shops = pd.read_csv(HERE / "shops_bcn_pred.csv")
    if args.district:
        shops = shops[shops["district"].astype(str).str.lower() == args.district.lower()]
        print("shops in %s: %d" % (args.district, len(shops)))
    shops = gpd.GeoDataFrame(shops, geometry=gpd.points_from_xy(shops["lon"], shops["lat"]), crs=4326).to_crs(25831)

    val = pd.read_csv(HERE / "shops_validation.csv") if args.show_validation else pd.DataFrame(columns=["id", "address"])
    sim_file = HERE / "results_shops.csv"
    sim = pd.read_csv(sim_file)[["id", "mean_df"]] if sim_file.exists() else pd.DataFrame(columns=["id", "mean_df"])
    val = val.merge(sim, on="id", how="left")
    val["sim"] = val["mean_df"].map(lambda x: "-" if pd.isna(x) else "%.2f" % x)
    # match by address: shop ids change when the shop list is rebuilt (e.g. for the whole city)
    val = val.merge(shops[["address", "geometry"]].drop_duplicates("address"), on="address", how="inner")
    val = gpd.GeoDataFrame(val, geometry="geometry", crs=25831)

    b = pd.read_pickle(Path(args.data) / "barcelona_data.pkl.gz")[["building_reference", "building_geometry"]]
    b = gpd.GeoDataFrame(b, geometry="building_geometry")
    b = b.set_crs(25831) if b.crs is None else b.to_crs(25831)
    pad = 150
    x0, y0, x1, y1 = shops.total_bounds
    b = b.cx[x0 - pad:x1 + pad, y0 - pad:y1 + pad]
    print("buildings drawn:", len(b), "| shops:", len(shops))

    OUT.mkdir(exist_ok=True)
    credit = "Catastro via hypercadaster_ES (EUPL-1.2) | Open Data BCN census (CC BY 4.0)" + (" | basemap Esri" if args.basemap else "")

    # 1. whole district
    fig, ax = plt.subplots(figsize=(10, 9))
    sc = draw(ax, b, shops, val, (x0 - pad, y0 - pad, x1 + pad, y1 + pad), args.basemap,
              ("Can these %d empty shops hold a daylit home? (EN 17037 + Decret 141, v0)" if "daylight_class" in shops.columns else "Predicted daylight factor of %d empty shops (v0)") % len(shops), label_all=False)
    if sc is not None:
        fig.colorbar(sc, ax=ax, shrink=0.6, label="predicted mean DF (%)")
    fig.text(0.01, 0.01, credit, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / ("shops_map_catastro%s.png" % tag), dpi=220)
    plt.close(fig)
    print("saved outputs/shops_map_catastro%s.png" % tag)
    if val.empty:
        return

    # 2. zoom around the validation shops
    vx0, vy0, vx1, vy1 = val.total_bounds
    zpad = 120
    fig, ax = plt.subplots(figsize=(10, 9))
    sc = draw(ax, b, shops, val, (vx0 - zpad, vy0 - zpad, vx1 + zpad, vy1 + zpad), args.basemap,
              "5 validation shops: model prediction vs Radiance simulation (DF %)", label_all=True)
    if sc is not None:
        fig.colorbar(sc, ax=ax, shrink=0.6, label="predicted mean DF (%)")
    fig.text(0.01, 0.01, credit, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / ("shops_map_catastro_zoom%s.png" % tag), dpi=220)
    plt.close(fig)
    print("saved outputs/shops_map_catastro_zoom%s.png" % tag)


if __name__ == "__main__":
    main()
