"""Nomad - test the rulebook on real floor plans: Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0).

45,000+ apartments and commercial units with every room, wall and window as geometry in metres.
For each unit we measure what Decret 141/2012 Annex 1 and the Barcelona MPGM 2004 ask for and say PASS/FAIL.
This is a stress test of the rules on real plans (Swiss buildings were not designed for Catalan rules),
not an accuracy score: the dataset has no "legal" labels.

Outputs (results/rule_tests/):
  sd_units.csv     one row per unit: measurements + one pass/fail column per rule
  sd_rooms.csv     one row per room: area, inscribed square/circle, window ratio
  sd_summary.json  pass rates per rule, for residential and commercial units
  sd_sample.json   300 units with room outlines + results, for the Grasshopper viewer
"""
import json, os, sys, time
import numpy as np
import pandas as pd
import shapely
from shapely import wkt
from shapely.strtree import STRtree

SRC = "data/datasets/swiss_dwellings/swiss-dwellings-v3.0.0/geometries.csv"
OUT = "results/rule_tests"

BEDROOM = {"BEDROOM", "ROOM"}
LIVING = {"LIVING_ROOM", "LIVING_DINING", "KITCHEN_DINING", "DINING"}
BATH = {"BATHROOM", "SANITARY_ROOMS", "TOILET"}
NOT_USEFUL = {"BALCONY", "LOGGIA", "TERRACE", "GARDEN", "SHAFT", "STAIRCASE", "ELEVATOR", "VOID", "OUTDOOR_VOID",
              "LIGHTWELL", "BASEMENT", "BASEMENT_COMPARTMENT", "GARAGE", "WINTERGARTEN", "CARPARK", "BIKE_STORAGE",
              "ARCADE", "PATIO", "COLD_STORAGE", "NOT_DEFINED", "OIL_TANK", "WATER_SUPPLY", "TECHNICAL_AREA"}

RULES = {
    "r_useful_36": "Decret 141/2012 Annex 1 3.1: superfície útil >= 36 m²",
    "r_useful_40": "MPGM 2004 Barcelona DA 1a 2.a: superfície útil >= 40 m²",
    "r_bedroom_6": "Decret 141/2012 Annex 1 3.8: every bedroom >= 6 m²",
    "r_bedroom_square": "Decret 141/2012 Annex 1 3.8: 2,00 m square in every bedroom (2,60 m in one if >= 3 bedrooms)",
    "r_living_circle": "Decret 141/2012 Annex 1 3.7.2: living/dining fits a 2,80 m circle",
    "r_windows_1_8": "Decret 141/2012 Annex 1 3.9.1: windows (0-2,5 m) >= 1/8 of each bedroom and living room",
    "r_height_250": "Decret 141/2012 Annex 1 3.5: clear height >= 2,50 m in main rooms",
    "r_bathrooms": "Decret 141/2012 Annex 1 3.11: >= 1 bathroom (>= 2 WC if >= 4 bedrooms)",
    "r_facade_s9": "Decret 141/2012 Annex 1 3.6.2 + MPGM 2004 DA1 2.b: façade >= max(S/9, 3 m) (proxy: total window width)",
}


def fits(poly, size, square=True):
    """Can a square of side `size` (or circle of diameter `size`) fit inside the room?
    Square: erode with a mitre join (exact for rooms whose walls are parallel to the square)."""
    if poly.is_empty or poly.area < size * size * 0.75:
        return False
    er = poly.buffer(-size / 2.0, join_style="mitre" if square else "round")
    return not er.is_empty and er.area > 1e-6


def window_area(win, elev, h):
    """Window glazing counted between 0 and 2,5 m above the floor (Decret 141 3.9.1)."""
    r = shapely.minimum_rotated_rectangle(win)
    xs, ys = r.exterior.coords.xy
    sides = sorted(np.hypot(np.diff(xs), np.diff(ys))[:2])
    width = sides[-1]
    top, bottom = min(elev + h, 2.5), max(elev, 0.0)
    return width, width * max(0.0, top - bottom)


def load():
    t = time.time()
    cols = ["apartment_id", "unit_id", "floor_id", "area_id", "unit_usage", "entity_type", "entity_subtype",
            "geometry", "elevation", "height"]
    parts = []
    for ch in pd.read_csv(SRC, usecols=cols, chunksize=500_000):
        parts.append(ch[(ch.entity_type == "area") | ((ch.entity_type == "opening") & (ch.entity_subtype == "WINDOW"))])
    df = pd.concat(parts, ignore_index=True)
    print(f"loaded {len(df):,} area/window rows in {time.time() - t:.0f}s", flush=True)
    return df


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    df["geom"] = shapely.from_wkt(df.geometry.values)
    areas = df[(df.entity_type == "area") & df.unit_id.notna()].copy()
    wins = df[df.entity_type == "opening"].copy()

    room_rows = []
    t = time.time()
    win_by_floor = {f: g for f, g in wins.groupby("floor_id")}
    for n, (fid, rooms) in enumerate(areas.groupby("floor_id")):
        w = win_by_floor.get(fid)
        tree = STRtree(list(w.geom.values)) if w is not None and len(w) else None
        for r in rooms.itertuples():
            g, st = r.geom, r.entity_subtype
            wa = ww = 0.0
            if tree is not None and (st in BEDROOM or st in LIVING or r.unit_usage != "RESIDENTIAL"):
                near = tree.query(g.buffer(0.45), predicate="intersects")
                floor_z = float(r.elevation) if pd.notna(r.elevation) else 0.0
                for i in near:
                    wr = w.iloc[int(i)]
                    # window elevation is from the building base: make it relative to this room's floor
                    sill = (float(wr.elevation) if pd.notna(wr.elevation) else floor_z) - floor_z
                    a_w, a_a = window_area(wr.geom, sill, float(wr.height or 0))
                    ww += a_w
                    wa += a_a
            room_rows.append({
                "unit_id": int(r.unit_id), "apartment_id": r.apartment_id, "floor_id": int(fid), "usage": r.unit_usage,
                "type": st, "area_m2": round(g.area, 2), "height_m": r.height,
                "square_200": fits(g, 2.0) if st in BEDROOM else None,
                "square_260": fits(g, 2.6) if st in BEDROOM else None,
                "circle_280": fits(g, 2.8, square=False) if (st in LIVING or st in BEDROOM) else None,
                "window_m2": round(wa, 2), "window_width_m": round(ww, 2),
                "wkt": g.wkt if n % 50 == 0 else None,   # keep outlines for a sample only
            })
        if n % 2000 == 0:
            print(f"  floors {n:,}  rooms {len(room_rows):,}  ({time.time() - t:.0f}s)", flush=True)
    rooms = pd.DataFrame(room_rows)
    rooms["window_ratio"] = rooms.window_m2 / rooms.area_m2.clip(lower=0.01)
    rooms.drop(columns=["wkt"]).to_csv(f"{OUT}/sd_rooms.csv", index=False)

    # ---- per unit ----
    def unit(g):
        useful = g[~g.type.isin(NOT_USEFUL)]
        beds, liv = g[g.type.isin(BEDROOM)], g[g.type.isin(LIVING)]
        main = pd.concat([beds, liv])
        S = useful.area_m2.sum()
        nb = len(beds)
        return pd.Series({
            "usage": g.usage.iloc[0], "apartment_id": g.apartment_id.iloc[0],
            "useful_m2": round(S, 1), "bedrooms": nb, "living_rooms": len(liv),
            "bathrooms": int(g.type.isin(BATH).sum()),
            "min_bedroom_m2": beds.area_m2.min() if nb else np.nan,
            "min_height_m": main.height_m.min() if len(main) else useful.height_m.min(),
            "window_width_m": round(g.window_width_m.sum(), 2),
            "worst_window_ratio": round(main.window_ratio.min(), 3) if len(main) else round(g.window_m2.sum() / max(S, 0.01), 3),
            "r_useful_36": S >= 36, "r_useful_40": S >= 40,
            "r_bedroom_6": bool((beds.area_m2 >= 6).all()) if nb else True,
            "r_bedroom_square": (bool(beds.square_200.all()) and (nb < 3 or bool(beds.square_260.any()))) if nb else True,
            # no room labelled living: the largest habitable room is the living candidate
            "r_living_circle": bool(liv.circle_280.any()) if len(liv) else (
                bool(beds.loc[beds.area_m2.idxmax(), "circle_280"]) if nb else False),
            "r_windows_1_8": bool((main.window_ratio >= 1 / 8).all()) if len(main) else (g.window_m2.sum() / max(S, .01) >= 1 / 8),
            "r_height_250": bool((main.height_m >= 2.5).all()) if len(main) else bool((useful.height_m >= 2.5).all()),
            "r_bathrooms": int(g.type.isin(BATH).sum()) >= (2 if nb >= 4 else 1),
            "r_facade_s9": g.window_width_m.sum() >= max(S / 9.0, 3.0),
        })

    t = time.time()
    units = rooms.groupby("unit_id").apply(unit, include_groups=False)
    rcols = list(RULES)
    units["passes"] = units[rcols].sum(axis=1)
    units["all_pass"] = units[rcols].all(axis=1)
    units.to_csv(f"{OUT}/sd_units.csv")
    print(f"units: {len(units):,} ({time.time() - t:.0f}s)", flush=True)

    summary = {"source": "Swiss Dwellings v3.0.0, Zenodo 7788422, CC BY 4.0", "rules": RULES, "by_usage": {}}
    for usage, g in units.groupby("usage"):
        summary["by_usage"][usage] = {
            "units": int(len(g)),
            "median_useful_m2": float(g.useful_m2.median()),
            "pass_rate": {k: round(float(g[k].mean()), 3) for k in rcols},
            "all_pass": round(float(g.all_pass.mean()), 3),
        }
    with open(f"{OUT}/sd_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    # ---- sample for Grasshopper: units whose floor kept outlines ----
    have = rooms[rooms.wkt.notna()]
    sample_ids = list(have.unit_id.drop_duplicates()[:300])
    sample = []
    for uid in sample_ids:
        u = units.loc[uid]
        rs = have[have.unit_id == uid]
        sample.append({
            "unit_id": int(uid), "usage": u.usage, "useful_m2": float(u.useful_m2), "bedrooms": int(u.bedrooms),
            "rules": {k: bool(u[k]) for k in rcols},
            "rooms": [{"type": r.type, "area": float(r.area_m2),
                       "ok": not ((r.type in BEDROOM and (r.area_m2 < 6 or r.square_200 is False))
                                  or ((r.type in BEDROOM or r.type in LIVING) and r.window_ratio < 1 / 8)),
                       "xy": [list(map(float, c)) for c in wkt.loads(r.wkt).exterior.coords]} for r in rs.itertuples()
                      if wkt.loads(r.wkt).geom_type == "Polygon"],
        })
    with open(f"{OUT}/sd_sample.json", "w", encoding="utf-8") as f:
        json.dump({"rules": RULES, "units": sample}, f, ensure_ascii=False)
    print(json.dumps(summary["by_usage"], indent=1))


if __name__ == "__main__":
    main()
