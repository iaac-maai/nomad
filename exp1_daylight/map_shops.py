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
OUT = HERE.parent / "outputs"


def draw(ax, buildings, shops, val, bbox, basemap, title, label_all):
    xmin, ymin, xmax, ymax = bbox
    b = buildings.cx[xmin:xmax, ymin:ymax]
    b.plot(ax=ax, color="#d9d6cf", edgecolor="#b5b0a6", linewidth=0.2, zorder=1)
    s = shops.cx[xmin:xmax, ymin:ymax]
    sc = ax.scatter(s.geometry.x, s.geometry.y, c=s["pred_mean_df"].clip(0.5, 3.0), cmap="RdYlBu_r",
                    vmin=0.5, vmax=3.0, s=14 if label_all else 7, edgecolor="black", linewidth=0.2, zorder=3)
    v = val.cx[xmin:xmax, ymin:ymax]
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
    args = ap.parse_args()

    shops = pd.read_csv(HERE / "shops_bcn_pred.csv")
    shops = gpd.GeoDataFrame(shops, geometry=gpd.points_from_xy(shops["lon"], shops["lat"]), crs=4326).to_crs(25831)

    val = pd.read_csv(HERE / "shops_validation.csv")
    sim_file = HERE / "results_shops.csv"
    sim = pd.read_csv(sim_file)[["id", "mean_df"]] if sim_file.exists() else pd.DataFrame(columns=["id", "mean_df"])
    val = val.merge(sim, on="id", how="left")
    val["sim"] = val["mean_df"].map(lambda x: "-" if pd.isna(x) else "%.2f" % x)
    val = val.merge(shops[["id", "geometry"]].rename(columns={"id": "shop_id"}), on="shop_id", how="left")
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
              "Predicted daylight factor of %d empty shops (v0)" % len(shops), label_all=False)
    fig.colorbar(sc, ax=ax, shrink=0.6, label="predicted mean DF (%)")
    fig.text(0.01, 0.01, credit, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "shops_map_catastro.png", dpi=220)
    plt.close(fig)
    print("saved outputs/shops_map_catastro.png")

    # 2. zoom around the validation shops
    vx0, vy0, vx1, vy1 = val.total_bounds
    zpad = 120
    fig, ax = plt.subplots(figsize=(10, 9))
    sc = draw(ax, b, shops, val, (vx0 - zpad, vy0 - zpad, vx1 + zpad, vy1 + zpad), args.basemap,
              "5 validation shops: model prediction vs Radiance simulation (DF %)", label_all=True)
    fig.colorbar(sc, ax=ax, shrink=0.6, label="predicted mean DF (%)")
    fig.text(0.01, 0.01, credit, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "shops_map_catastro_zoom.png", dpi=220)
    plt.close(fig)
    print("saved outputs/shops_map_catastro_zoom.png")


if __name__ == "__main__":
    main()
