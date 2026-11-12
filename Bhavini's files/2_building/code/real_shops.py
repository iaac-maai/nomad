"""Nomad - NOMAD shells for Barcelona's real empty shops, from the Catastro buildings (catastro_buildings.py), the MUC
zoning (1_find_the_shops/code/zoning.py) and the 2024 census of ground-floor premises.

For each empty premises with a Catastro building:
  outline  the building's built ground floor: the union of its building parts with at least one floor above ground
           (parts with 0 floors above ground are courtyards / terraces and stay open)
  façade   each outline edge is tested 1,5 m outside its middle: in a street polygon (MUC "SX") = street façade;
           in open ground (no building, no street) still open 6 m out (PGM art. 225.7: 6 m deep) = façade to the inner block
           or a park, which the
           Barcelona rule also accepts for light (MPGM 2004 DA1 2.b: "façana a via pública o pati interior d'illa");
           against another building = party wall (no light)
  shared   how many premises of the census (active or empty) share the building: with more than one, the shell is the
           whole ground floor and the premises' own share needs the Catastro CAT file (area per premises)
  height   not in the Catastro: 3,0 m assumed (NOMAD's default; PGM art. 225.2 asks 3,70-4,00 m floor to floor for new
           ground floors along streets)
Out: 2_building/output/real_shops/shells.json (NOMAD shop format, local metres, y up) + summary.json
Run: .venv/Scripts/python 2_building/code/real_shops.py
"""
import gzip, json, math
from pathlib import Path
import pandas as pd
from shapely.geometry import Polygon, Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "2_building/output/real_shops"
HEIGHT = 3.0


def poly(rings_):
    ps = [Polygon(r[0], r[1:]).buffer(0) for r in rings_ if len(r[0]) >= 3]
    return unary_union(ps) if ps else None


def main():
    B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    census = pd.read_csv(ROOT / "0_shared_input/census/2024_CensComercial_BCN.csv", encoding="utf-8-sig", low_memory=False)
    census["ref14"] = census.Referencia_Cadastral.fillna("").str[:14]
    share = census.ref14.value_counts().to_dict()
    e = pd.read_csv(ROOT / "1_find_the_shops/output/zoning/empty_premises_zoning.csv")
    e["ref14"] = e.Referencia_Cadastral.fillna("").str[:14]
    e = e[e.ref14.isin(B.keys())].reset_index(drop=True)

    # every building footprint (for party walls) and every street polygon (for street façades)
    refs = list(B.keys())
    foots = [poly(B[r]["foot"]) for r in refs]
    keep = [i for i, g in enumerate(foots) if g is not None and not g.is_empty]
    btree = STRtree([foots[i] for i in keep])
    bref = [refs[i] for i in keep]
    Z = json.load(open(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson", encoding="utf-8"))["features"]
    streets = [shape(f["geometry"]).buffer(0) for f in Z if (f["properties"]["C_QUAL_MUC"] or "").startswith("SX")]
    stree = STRtree(streets)

    shells, rows = {}, []
    for ref in e.ref14.unique():
        b = B[ref]
        ground = poly([r for p in b["parts"] if (p["up"] or 0) >= 1 for r in p["poly"]]) or poly(b["foot"])
        if ground is None or ground.is_empty:
            continue
        if ground.geom_type == "MultiPolygon":
            ground = max(ground.geoms, key=lambda g: g.area)
        ground = ground.simplify(0.15, preserve_topology=True)
        ext = list(ground.exterior.coords)
        if ground.exterior.is_ccw:                          # walk clockwise so the outside is on the left of each edge
            ext = ext[::-1]
        street, opened = [], []
        for a, c in zip(ext[:-1], ext[1:]):
            L = math.hypot(c[0] - a[0], c[1] - a[1])
            if L < 0.8:
                continue
            nx, ny = -(c[1] - a[1]) / L, (c[0] - a[0]) / L     # left normal = outside for a clockwise ring
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            q, far = Point(mx + 1.5 * nx, my + 1.5 * ny), Point(mx + 6.0 * nx, my + 6.0 * ny)
            free = lambda p: not ground.contains(p) and not any(foots[keep[int(i)]].contains(p) for i in btree.query(p))
            if any(streets[int(i)].contains(q) for i in stree.query(q)):
                street.append((a, c))
            elif free(q) and free(far):                     # open ground at least 6 m deep (PGM art. 225.7), not a light well
                opened.append((a, c))
        x0, y0 = ground.bounds[0], ground.bounds[1]
        loc = lambda p: [round(p[0] - x0, 2), round(p[1] - y0, 2)]
        floors = max([p["up"] or 0 for p in b["parts"]] or [0])
        sl, ol = sum(math.dist(a, c) for a, c in street), sum(math.dist(a, c) for a, c in opened)
        mrr = ground.minimum_rotated_rectangle
        side = sorted(math.dist(mrr.exterior.coords[i], mrr.exterior.coords[i + 1]) for i in range(2))
        shells[ref] = {"ref": ref, "outline": [loc(p) for p in ext], "facade": [[loc(a), loc(c)] for a, c in street + opened],
                       "street": [[loc(a), loc(c)] for a, c in street], "origin_utm": [round(x0, 2), round(y0, 2)],
                       "height": HEIGHT, "floors": floors, "use": b["use"], "dwellings": b["dwellings"], "units": b["units"],
                       "premises_in_building": int(share.get(ref, 0))}
        rows.append({"ref": ref, "ground_m2": round(ground.area, 1), "street_facade_m": round(sl, 1), "open_facade_m": round(ol, 1),
                     "width_m": round(side[0], 1), "length_m": round(side[1], 1), "floors": floors, "use": b["use"],
                     "dwellings": b["dwellings"], "premises_in_building": int(share.get(ref, 0)),
                     "patios_inside": len(ground.interiors)})
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(shells, open(OUT / "shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    r = pd.DataFrame(rows)
    m = e.merge(r, left_on="ref14", right_on="ref", how="inner")
    m.drop(columns=["ref"]).to_csv(OUT / "empty_shops_buildings.csv", index=False, encoding="utf-8")
    one = m[m.premises_in_building == 1]
    summ = {"empty_premises": int(len(pd.read_csv(ROOT / "1_find_the_shops/output/zoning/empty_premises_zoning.csv"))),
            "matched_to_a_building": int(len(m)), "buildings": int(len(r)),
            "alone_in_building": int(len(one)), "sharing_the_ground_floor": int((m.premises_in_building > 1).sum()),
            "median_ground_m2": float(m.ground_m2.median()), "median_street_facade_m": float(m.street_facade_m.median()),
            "no_street_facade": int((m.street_facade_m < 0.5).sum()),
            "median_floors": float(m.floors.median()), "median_building_depth_m": float(m.length_m.median())}
    json.dump(summ, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
