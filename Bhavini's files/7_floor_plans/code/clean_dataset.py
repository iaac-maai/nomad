"""Nomad - clean Swiss Dwellings into the inputs the floor-plan generator needs.

The generator's question is: "here is a shop (a shell), make it housing with this unit mix".
So from every COMMERCIAL unit in Swiss Dwellings we keep only what that question needs:
  outline  - one polygon: all the unit's rooms merged, small gaps closed, simplified to 10 cm
  facade   - the outline edges that have windows (where light and air can come in)
  height   - clear height of the space, and floor level
  area     - floor area inside the outline (m²)
A shell is dropped (with the reason written in the report) when it cannot become housing at all:
outline broken, under 40 m² (Barcelona minimum, MPGM 2004 DA1), clear height under 2,40 m (2,50 m for new build; 2,40 m for a change of use, Annex 4 group C)
(Decret 141 Annex 1 3.5) or less than 3 m of façade with windows (MPGM 2004 DA1 2.b).

Outputs: 7_floor_plans/output/clean/nomad_shells.json (kept shells), 7_floor_plans/output/clean/cleaning_report.csv (every unit, kept or why not)
"""
import json, os
import pandas as pd
import shapely
from shapely.ops import unary_union

SRC = "7_floor_plans/input/datasets/swiss_dwellings/swiss-dwellings-v3.0.0/geometries.csv"
OUT = "7_floor_plans/output/clean"


def load():
    cols = ["unit_id", "floor_id", "unit_usage", "entity_type", "entity_subtype", "geometry", "elevation", "height"]
    parts = []
    for ch in pd.read_csv(SRC, usecols=cols, chunksize=500_000):
        a = ch[(ch.entity_type == "area") & (ch.unit_usage == "COMMERCIAL")]
        w = ch[(ch.entity_type == "opening") & (ch.entity_subtype == "WINDOW")]
        parts += [a, w]
    df = pd.concat(parts, ignore_index=True)
    df["geom"] = shapely.from_wkt(df.geometry.values)
    return df


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    areas = df[df.entity_type == "area"]
    wins = df[df.entity_type == "opening"]
    win_by_floor = {f: list(g.geom) for f, g in wins.groupby("floor_id")}
    shells, report = [], []
    for uid, g in areas.groupby("unit_id"):
        row = {"unit_id": int(uid), "floor_id": int(g.floor_id.iloc[0]), "kept": False, "reason": ""}
        merged = unary_union([p.buffer(0.15, join_style="mitre") for p in g.geom]).buffer(-0.15, join_style="mitre")
        if merged.is_empty:
            row["reason"] = "no outline"
            report.append(row)
            continue
        parts = sorted(getattr(merged, "geoms", [merged]), key=lambda p: p.area, reverse=True)
        poly = parts[0].simplify(0.10)
        if not poly.is_valid or poly.geom_type != "Polygon":
            row["reason"] = "outline broken"
            report.append(row)
            continue
        area = poly.area
        height = float(g.height.median())
        floor_z = float(g.elevation.min())
        # façade = outline edges with a window within 0.5 m (window polygons sit inside the wall)
        coords = list(poly.exterior.coords)
        near = [w for w in win_by_floor.get(row["floor_id"], []) if w.distance(poly) < 0.6]
        facade, facade_len = [], 0.0
        for a, b in zip(coords[:-1], coords[1:]):
            edge = shapely.LineString([a, b])
            if edge.length >= 0.5 and any(w.distance(edge) < 0.5 for w in near):
                facade.append([list(a), list(b)])
                facade_len += edge.length
        row.update(area_m2=round(area, 1), height_m=round(height, 2), facade_m=round(facade_len, 1),
                   rooms=len(g), windows=len(near), parts=len(parts))
        if area < 40:
            row["reason"] = "under 40 m2 (MPGM 2004 DA1)"
        elif height < 2.4:
            row["reason"] = "clear height under 2,40 m (Decret 141/2012 Annex 4 group C, change of use)"
        elif facade_len < 3:
            row["reason"] = "under 3 m of facade with windows (MPGM 2004 DA1 2.b)"
        else:
            row["kept"] = True
            minx, miny = poly.bounds[0], poly.bounds[1]   # move to a local origin so numbers stay small
            shells.append({
                "shell_id": int(uid), "floor_id": row["floor_id"], "area_m2": round(area, 1),
                "height_m": round(height, 2), "floor_z": floor_z, "facade_m": round(facade_len, 1),
                "former_use": ", ".join(sorted(set(g.entity_subtype)))[:120],
                "outline": [[round(x - minx, 3), round(y - miny, 3)] for x, y in coords],
                "facade": [[[round(p[0] - minx, 3), round(p[1] - miny, 3)] for p in seg] for seg in facade],
            })
        report.append(row)
    rep = pd.DataFrame(report)
    rep.to_csv(f"{OUT}/cleaning_report.csv", index=False)
    with open(f"{OUT}/nomad_shells.json", "w", encoding="utf-8") as f:
        json.dump({"source": "Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0), commercial units",
                   "units": "metres, local origin per shell", "shells": shells}, f)
    print(f"commercial units: {len(rep)} | kept: {int(rep.kept.sum())}")
    print(rep[~rep.kept].reason.value_counts().to_string())
    k = rep[rep.kept]
    print(f"kept shells: area median {k.area_m2.median():.0f} m2 (min {k.area_m2.min():.0f}, max {k.area_m2.max():.0f}), "
          f"facade median {k.facade_m.median():.1f} m, height median {k.height_m.median():.2f} m")


if __name__ == "__main__":
    main()
