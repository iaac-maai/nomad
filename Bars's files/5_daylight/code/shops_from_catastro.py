"""Nomad - empty Barcelona shops (Open Data BCN census) + Catastro buildings -> shop variants CSV.

Run in the "cadaster" conda environment (it needs geopandas), from the nomad repo root:
    python exp1_daylight/shops_from_catastro.py --data C:/Users/barsb/nomad-hypercadaster_ES/data --district Eixample
Options:
    --district Eixample      one district (name as in Nom_Districte); leave out for the whole city
    --all-premises           use every ground-floor premise, not only the empty ones
    --search 60              how far (m) to look across the street for the opposite building

Inputs (both made by hypercadaster_ES in its data folder):
    data/barcelona_data.pkl.gz                    Catastro buildings (barcelona.py)
    data/open_data/barcelona_ground_premises.csv  Open Data BCN ground-floor census (CC BY 4.0)
Output: exp1_daylight/shops_bcn.csv, one row per empty shop, same columns as variants.csv.

From data : empty / active status, address, district, cadastral reference, door point (census);
            width_m / depth_m = short / long side of the minimum rotated rectangle of the building
            footprint (v0: whole building, not the individual shop);
            floors = built area / footprint area (Catastro has no floor count in this merge);
            obs_dist_m = from the shop door, straight out of the street facade, to the first
            building hit (the building across the street; footprints under 50 m2 such as
            kiosks are skipped);
            obs_height_m = 5 m ground floor + 3 m per upper floor of that building.
Assumed   : floor_height_m 4.0, wwr 0.6, window head 3.9 m, lit_facades 1 ("assumed" column).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point

HERE = Path(__file__).resolve().parent
FLOOR_H, WWR, WIN_TARGET = 4.0, 0.6, 3.0
RANGES = {"depth_m": (8, 25), "width_m": (4, 12), "obs_dist_m": (8, 20), "obs_height_m": (12, 25)}


def outer(geom):
    """largest polygon of a (multi)polygon"""
    if geom.geom_type == "MultiPolygon":
        return max(geom.geoms, key=lambda p: p.area)
    return geom


def rect_sides(geom):
    rect = geom.minimum_rotated_rectangle
    xy = np.asarray(rect.exterior.coords)
    sides = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))[:2]
    return float(sides.min()), float(sides.max())


def height_from_floors(n):
    if n is None or not np.isfinite(n) or n < 1:
        return np.nan
    return 5.0 + 3.0 * (n - 1)


def facade_ray(poly, door, length, is_built):
    """Ray from the shop door straight out of its STREET facade.

    Candidate facade segments are tried from the one nearest to the door. A segment is a
    street facade only if the point 1.5 m outside it is open ground (not inside any
    building); otherwise it is a party wall or a patio wall and the next segment is tried.
    Returns (start, ray, ok): ok = False when no free facade was found near the door.
    """
    ring = poly.exterior
    xy = np.asarray(ring.coords)
    cands = []
    for i in range(len(xy) - 1):
        seg = LineString(xy[i:i + 2])
        if seg.length >= 2.0:          # skip tiny corner pieces, their direction is noise
            cands.append((seg.distance(door), seg))
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    nearest = cands[0][0]
    fallback = None
    for d_door, seg in cands:
        if d_door > nearest + 8.0:     # only facades close to the door
            break
        (x1, y1), (x2, y2) = seg.coords
        t = np.array([x2 - x1, y2 - y1])
        n = np.array([-t[1], t[0]]) / np.hypot(*t)
        p0 = seg.interpolate(seg.project(door))
        if poly.contains(Point(p0.x + 0.5 * n[0], p0.y + 0.5 * n[1])):
            n = -n                     # make it point out of the building
        start = np.array([p0.x, p0.y])
        ray = LineString([start + 0.3 * n, start + length * n])
        if fallback is None:
            fallback = (start, ray, False)
        if not is_built(Point(*(start + 1.5 * n))):
            return start, ray, True
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="hypercadaster data folder")
    ap.add_argument("--district", default="", help="e.g. Eixample (empty = whole city)")
    ap.add_argument("--all-premises", action="store_true", help="also active shops, not only empty ones")
    ap.add_argument("--census", default="", help="ground-floor census CSV (default: <data>/open_data/barcelona_ground_premises.csv, the 2022 census)")
    ap.add_argument("--out", default=str(HERE / "shops_bcn.csv"))
    ap.add_argument("--search", type=float, default=60.0, help="max distance to the opposite building (m)")
    ap.add_argument("--min-area", type=float, default=50.0, help="ignore smaller footprints across the street (kiosks, metro exits)")
    args = ap.parse_args()
    data = Path(args.data)

    # ---- 1. Open Data BCN ground-floor census
    census = Path(args.census) if args.census else data / "open_data" / "barcelona_ground_premises.csv"
    prem = None
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            prem = pd.read_csv(census, low_memory=False, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    need = ["Codi_Principal_Activitat", "Referencia_Cadastral", "X_UTM_ETRS89", "Y_UTM_ETRS89", "Nom_Districte"]
    miss = [c for c in need if c not in prem.columns]
    if miss:
        print("columns in this file:", list(prem.columns))
        raise SystemExit("This census file has other column names (missing %s) - send this output to Claude." % miss)
    print("census file:", census.name, "| premises:", len(prem))
    if not args.all_premises:
        prem = prem[prem["Codi_Principal_Activitat"] == 0]  # 'Sense activitat Economica' = empty
        print("empty premises:", len(prem))
    if args.district:
        prem = prem[prem["Nom_Districte"].astype(str).str.lower() == args.district.lower()]
        print("in district %s: %d" % (args.district, len(prem)))
    prem = prem.dropna(subset=["Referencia_Cadastral", "X_UTM_ETRS89", "Y_UTM_ETRS89"])
    prem["building_reference"] = prem["Referencia_Cadastral"].astype(str).str.strip().str[:14]

    # ---- 2. Catastro buildings + estimated floors
    gdf = pd.read_pickle(data / "barcelona_data.pkl.gz")
    gdf = gdf[["building_reference", "building_area", "year_of_construction", "building_geometry"]]
    gdf = gpd.GeoDataFrame(gdf, geometry="building_geometry")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if gdf.crs is None:
        gdf = gdf.set_crs(25831)
    elif gdf.crs.to_epsg() != 25831:
        gdf = gdf.to_crs(25831)
    print("Catastro buildings:", len(gdf), "| CRS:", gdf.crs.to_string())
    gdf["building_reference"] = gdf["building_reference"].astype(str).str.strip().str[:14]
    gdf = gdf.drop_duplicates("building_reference").reset_index(drop=True)

    footprint = gdf.geometry.area
    ratio = pd.to_numeric(gdf["building_area"], errors="coerce") / footprint.where(footprint > 20)
    gdf["floors_est"] = ratio.round().clip(1, 20)
    gdf["height_est"] = gdf["floors_est"].map(height_from_floors)
    print("floors estimated for %d of %d buildings (median %.0f floors)" % (
        gdf["floors_est"].notna().sum(), len(gdf), gdf["floors_est"].median()))

    refs = set(prem["building_reference"])
    shop_b = gdf[gdf["building_reference"].isin(refs)]
    print("buildings with these shops found in the Catastro: %d of %d" % (len(shop_b), len(refs)))
    if shop_b.empty:
        print("example census refs:", list(refs)[:5])
        print("example Catastro refs:", gdf["building_reference"].head(5).tolist())
        raise SystemExit("No match between census and Catastro references - send this output to Claude.")
    pos = {ref: i for i, ref in enumerate(gdf["building_reference"])}

    sindex = gdf.sindex
    geoms = gdf.geometry.to_numpy()
    heights = gdf["height_est"].to_numpy()
    small = (gdf.geometry.area < args.min_area).to_numpy()   # kiosks, metro exits, sheds
    print("small structures ignored as opposite buildings (< %.0f m2): %d" % (args.min_area, small.sum()))
    height_fill = float(np.nanmedian(heights))

    # ---- 3. one row per shop: ray from the door across the street
    rows, n_noray, n_nohit, n_fill, n_wall = [], 0, 0, 0, 0

    def is_built(pt):
        return any(geoms[j].contains(pt) for j in sindex.query(pt, predicate="intersects"))
    for k, (_, p) in enumerate(prem[prem["building_reference"].isin(pos)].iterrows()):
        i = pos[p["building_reference"]]
        own = geoms[i]
        poly = outer(own)
        width, depth = rect_sides(own)
        door = Point(float(p["X_UTM_ETRS89"]), float(p["Y_UTM_ETRS89"]))
        ray = facade_ray(poly, door, args.search, is_built)
        if ray is None:
            n_noray += 1
            continue
        start, line, facade_ok = ray
        n_wall += 0 if facade_ok else 1
        p_start = Point(*start)

        # neighbours sharing a party wall are not "across the street"
        touching = set(sindex.query(own.buffer(1.0), predicate="intersects"))
        od, oh, no_opp = np.nan, np.nan, 0
        for j in sindex.query(line, predicate="intersects"):
            if j in touching or small[j]:
                continue
            d = p_start.distance(line.intersection(geoms[j]))
            if d >= 3.0 and (np.isnan(od) or d < od):
                od, oh = d, heights[j]
        if np.isnan(od):               # nothing across: square, park, wide avenue
            n_nohit += 1
            od, oh, no_opp = args.search, 0.0, 1
        elif np.isnan(oh):
            n_fill += 1
            oh = height_fill

        g = gdf.iloc[i]
        rows.append({
            "census_id": p["ID_Global"], "building_reference": p["building_reference"],
            "address": "%s %s" % (p.get("Nom_Via", ""), str(p.get("Num_Policia_Inicial", "")).replace(".0", "")),
            "district": p.get("Nom_Districte", ""), "neighbourhood": p.get("Nom_Barri", ""),
            "status": p.get("Nom_Sector_Activitat", ""),
            "floors": g["floors_est"], "year": g["year_of_construction"],
            "lon": p.get("Longitud", np.nan), "lat": p.get("Latitud", np.nan),
            "door_to_facade_m": round(door.distance(poly.exterior), 2),
            "depth_m": round(depth, 2), "width_m": round(width, 2),
            "street_facade_found": int(facade_ok),
            "obs_dist_m": round(od, 2), "obs_height_m": round(oh, 2), "no_opposite": no_opp,
        })
        if (k + 1) % 500 == 0:
            print("  ", k + 1, "shops done")

    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit("No shop rows produced - send this output to Claude.")
    print("skipped (no usable facade): %d | nothing across the street: %d | opposite height filled with median: %d"
          % (n_noray, n_nohit, n_fill))
    print("no free street facade near the door (ray kept from the nearest wall, check these): %d" % n_wall)

    h = FLOOR_H
    win_h = min(max(WIN_TARGET, WWR * h * 1.05), h - 0.3)
    sill = max(min(0.9, h - win_h - 0.1), 0.1)
    out["floor_height_m"], out["wwr"], out["win_height_target_m"] = FLOOR_H, WWR, WIN_TARGET
    out["lit_facades"] = 1
    out["win_height_m"], out["sill_m"], out["head_m"] = round(win_h, 2), round(sill, 2), round(sill + win_h, 2)
    out["assumed"] = "floor_height,wwr,window,lit_facades"

    inside = np.ones(len(out), bool)
    outside_cols = [[] for _ in range(len(out))]
    print("\ninside the Experiment 1 training range, per variable:")
    for c, (lo, hi) in RANGES.items():
        ok = out[c].between(lo, hi).to_numpy()
        print("   %-13s %4d of %d  (trained %g-%g)" % (c, ok.sum(), len(out), lo, hi))
        inside &= ok
        for r in np.where(~ok)[0]:
            outside_cols[r].append(c)
    out["in_training_range"] = inside.astype(int)
    out["out_of_range"] = [",".join(x) for x in outside_cols]
    out.insert(0, "id", range(len(out)))

    out.to_csv(args.out, index=False, encoding="utf-8")
    print("\nsaved %d shops to %s" % (len(out), args.out))
    print("inside ALL training ranges: %d (%.0f %%)" % (inside.sum(), 100 * inside.mean()))
    print(out[["depth_m", "width_m", "obs_dist_m", "obs_height_m", "floors", "door_to_facade_m"]]
          .describe().round(1).to_string())


if __name__ == "__main__":
    main()
