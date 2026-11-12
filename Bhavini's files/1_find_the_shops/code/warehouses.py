"""Nomad - whole buildings that could become homes: warehouses (naus), commercial and office buildings with no homes.

From the Catastro buildings (0_shared_input/catastro/buildings.json.gz): every building whose use is industrial, retail or
office and that holds no dwelling. For each:
  zone      the PGM zone at the building (1_find_the_shops/code/zoning.py): YES = zone admits housing, CHECK = its own plan decides
            (22@, 18, 20), NO = it does not (22a industrial, systems)
  in use?   a hint from the 2024 census of ground-floor premises: "empty premises" (a premises on this parcel is listed
            empty), "no active business" (none listed active), else "active business". The census only lists ground
            floors: this is a hint, not proof that the building is unused
  shell     footprint, street façades and façades to open ground (as 2_building/code/real_shops.py), storeys from Catastro
Out: 1_find_the_shops/output/warehouses/candidates.csv, 1_find_the_shops/output/warehouses/shells.json (buildings in a YES / CHECK zone with a façade),
     app/data/warehouses.json (the map layer)
Run: .venv/Scripts/python 1_find_the_shops/code/warehouses.py
"""
import gzip, json, math, sys
from pathlib import Path
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "1_find_the_shops/code"), str(ROOT / "2_building/code")]
import zoning as Z  # noqa: E402
from real_shops import poly  # noqa: E402

OUT = ROOT / "1_find_the_shops/output/warehouses"
KIND = {"3_industrial": "warehouse", "4_2_retail": "commercial", "4_1_office": "office"}
STOREY_H = {"warehouse": None, "commercial": 3.0, "office": 3.0}   # m; a warehouse's clear height is asked (Catastro has none)


def main():
    B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    cand = [r for r, b in B.items() if b["use"] in KIND and not b.get("dwellings")]
    refs = list(B.keys())
    foots = [poly(B[r]["foot"]) for r in refs]
    keep = [i for i, g in enumerate(foots) if g is not None and not g.is_empty]
    btree = STRtree([foots[i] for i in keep])
    zf = json.load(open(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson", encoding="utf-8"))["features"]
    streets = [shape(f["geometry"]).buffer(0) for f in zf if (f["properties"]["C_QUAL_MUC"] or "").startswith("SX")]
    stree = STRtree(streets)
    geoms, attrs = Z.load_zones()
    cen = pd.read_csv(Z.CENSUS, encoding="utf-8-sig", low_memory=False)
    cen["p14"] = cen["Referencia_Cadastral"].fillna("").astype(str).str[:14]
    active = set(cen[cen["Nom_Principal_Activitat"] == "Actiu"]["p14"])
    empty = set(cen[cen["Nom_Sector_Activitat"].str.startswith("Locals buits", na=False)]["p14"])
    addr = cen.drop_duplicates("p14").set_index("p14")[["Nom_Via", "Num_Policia_Inicial", "Nom_Barri", "Nom_Districte"]].to_dict("index")

    grounds, pts = {}, []
    for ref in cand:
        b = B[ref]
        g = poly([r for p in b["parts"] if (p["up"] or 0) >= 1 for r in p["poly"]]) or poly(b["foot"])
        if g is None or g.is_empty:
            continue
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda x: x.area)
        grounds[ref] = g.simplify(0.15, preserve_topology=True)
    order = list(grounds)
    zs = Z.zone_of([grounds[r].representative_point() for r in order], geoms, attrs)
    rows, shells = [], {}
    for ref, z in zip(order, zs):
        b, g = B[ref], grounds[ref]
        key, ans, why = Z.gate(z.get("D_QUAL_AJT"), z.get("C_QUAL_MUC")) if z else ("", "NO", "no zone found")
        status = "empty premises" if ref in empty else ("no active business" if ref not in active else "active business")
        kind = KIND[b["use"]]
        ext = list(g.exterior.coords)
        if g.exterior.is_ccw:
            ext = ext[::-1]
        street, opened = [], []
        for a, c in zip(ext[:-1], ext[1:]):
            L = math.hypot(c[0] - a[0], c[1] - a[1])
            if L < 0.8:
                continue
            nx, ny = -(c[1] - a[1]) / L, (c[0] - a[0]) / L
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            q, far = Point(mx + 1.5 * nx, my + 1.5 * ny), Point(mx + 6.0 * nx, my + 6.0 * ny)
            free = lambda p: not g.contains(p) and not any(foots[keep[int(i)]].contains(p) for i in btree.query(p))
            if any(streets[int(i)].contains(q) for i in stree.query(q)):
                street.append((a, c))
            elif free(q) and free(far):
                opened.append((a, c))
        floors = max([p["up"] or 0 for p in b["parts"]] or [1]) or 1
        below = max([p["down"] or 0 for p in b["parts"]] or [0])
        sl, ol = sum(math.dist(a, c) for a, c in street), sum(math.dist(a, c) for a, c in opened)
        c = g.representative_point()
        ad = addr.get(ref, {})
        row = {"ref": ref, "kind": kind, "x": round(c.x), "y": round(c.y), "zone": (z or {}).get("D_QUAL_AJT", ""), "key": key,
               "housing": ans, "why": why, "status": status, "built_m2": round(b.get("area") or 0), "ground_m2": round(g.area),
               "floors": floors, "below": below, "street_m": round(sl, 1), "open_m": round(ol, 1),
               "street": ad.get("Nom_Via", ""), "num": str(ad.get("Num_Policia_Inicial", "") or "").replace(".0", ""),
               "barri": ad.get("Nom_Barri", ""), "district": ad.get("Nom_Districte", "")}
        rows.append(row)
        if ans in ("YES", "CHECK") and sl + ol >= 3.0:
            x0, y0 = g.bounds[0], g.bounds[1]
            loc = lambda p: [round(p[0] - x0, 2), round(p[1] - y0, 2)]
            shells[ref] = {"ref": ref, "kind": kind, "outline": [loc(p) for p in ext], "facade": [[loc(a), loc(c)] for a, c in street + opened],
                           "street": [[loc(a), loc(c)] for a, c in street], "origin_utm": [round(x0, 2), round(y0, 2)],
                           "floors": floors, "storey_h": STOREY_H[kind], "use": b["use"], "zone": row["zone"], "housing": ans,
                           "why": why, "status": status, "built_m2": row["built_m2"]}
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "candidates.csv", index=False, encoding="utf-8")
    json.dump(shells, open(OUT / "shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    cols = ["x", "y", "ref", "kind", "zone", "key", "housing", "why", "status", "built_m2", "ground_m2", "floors", "street_m", "open_m",
            "street", "num", "barri", "district"]
    site = ROOT / "app/data"
    json.dump({"cols": cols, "rows": [[r[c] for c in cols] for r in rows], "shells": shells},
              open(site / "warehouses.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    unused = df[df.status != "active business"]
    print("buildings:", len(df), df.kind.value_counts().to_dict())
    print("not active and zone YES:", unused[unused.housing == "YES"].kind.value_counts().to_dict(),
          "CHECK:", unused[unused.housing == "CHECK"].kind.value_counts().to_dict())
    print("shells for the design flow:", len(shells), "| app/data/warehouses.json %.1f MB" % ((site / "warehouses.json").stat().st_size / 1e6))


if __name__ == "__main__":
    main()
