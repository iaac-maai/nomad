"""Nomad - shop outlines from the Catastro ground-floor plans, for the empty premises NOMAD could not model.

Why: 2_building/code/real_shops.py only knows a building's whole ground floor. When other premises share it (or the
ground floor has no street façade) the shop's own outline is unknown, so 1_find_the_shops/code/avoid.py says "not modelled".
For buildings with a Catastro floor-by-floor plan (2_building/code/catastro_plans.py), every ground-floor unit is drawn:
  unit     the non-residential ground-floor unit (shop / local / office / industry; not common parts, homes, parking)
           nearest the census door point, at most 8 m from it (the door sits on the unit's street edge)
  façade   as real_shops.py: an edge whose point 1,5 m outside is in a street polygon (MUC "SX") = street façade; open
           ground still open 6 m out (PGM art. 225.7) = façade to the inner block; another unit or building = no light
  height   3,0 m assumed, as real_shops.py
Then NOMAD (same code as NOMAD.gh: zoning + Stage 5 check + Stage 6 circulation strategies) runs on the shops in a
zone that admits housing with at least 40 m² and 3 m of façade, asked 2 x 1-bed + 1 x 2-bed.
Out: 2_building/output/real_shops/catastro_shells.json, catastro_results.csv, catastro_summary.json
Run: .venv/Scripts/python 2_building/code/catastro_shops.py
"""
import csv, gzip, json, math, sys, time
from pathlib import Path
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon, Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ("rhino_grasshopper/code", "7_floor_plans/code", "6_check_the_shop/code", "2_building/code")]
import nomad_core as core  # noqa: E402
from real_shops import poly  # noqa: E402

OUT = ROOT / "2_building/output/real_shops"
FLOORS = ROOT / "private/catastro_visor_floors"
MIX = {"1bed": 2, "2bed": 1}
HEIGHT = 3.0
DOOR_MAX = 8.0
NOT_SHOP = ("COMUN", "V", "AAP", "A")        # common parts, dwellings, parking / storage: never the premises
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True)


def ground_units(ref):
    f = FLOORS / (ref + ".json")
    if not f.exists():
        return []
    g = json.load(open(f, encoding="utf-8"))
    out = []
    for ft in g.get("features") or []:
        p, geo = ft["properties"], ft["geometry"]
        if p.get("Planta") != 0 or geo["type"] not in ("Polygon", "MultiPolygon"):
            continue
        ring = geo["coordinates"][0] if geo["type"] == "Polygon" else max((q[0] for q in geo["coordinates"]), key=len)
        pg = Polygon([TO_UTM.transform(x, y) for x, y in ring]).buffer(0)
        if not pg.is_empty:
            out.append({"code": p.get("Uso") or "", "use": p.get("Descripcion") or "", "m2": p.get("Superficie"),
                        "poly": pg if pg.geom_type == "Polygon" else max(pg.geoms, key=lambda q: q.area)})
    return out


def main():
    todo = pd.read_csv(ROOT / "1_find_the_shops/output/zoning/empty_premises_zoning.csv", dtype=str)
    todo["ref14"] = todo.Referencia_Cadastral.fillna("").str[:14]
    done = set(pd.read_csv(OUT / "nomad_results.csv", dtype={"ref": str})["ref"])     # modelled already from the whole building
    todo = todo[~todo.ref14.isin(done) & todo.ref14.map(lambda r: (FLOORS / (r + ".json")).exists())]
    print("not modelled premises with a Catastro plan:", len(todo), flush=True)

    B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    foots = [g for g in (poly(b["foot"]) for b in B.values()) if g is not None and not g.is_empty]
    btree = STRtree(foots)
    Z = json.load(open(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson", encoding="utf-8"))["features"]
    streets = [shape(f["geometry"]).buffer(0) for f in Z if (f["properties"]["C_QUAL_MUC"] or "").startswith("SX")]
    stree = STRtree(streets)

    shells, rows, progs = {}, [], core.data()["programs"]
    for _, r in todo.iterrows():
        units = ground_units(r.ref14)
        door = Point(float(r.X_UTM_ETRS89), float(r.Y_UTM_ETRS89))
        cand = [u for u in units if not any(u["code"] == c or u["code"].startswith(c + ".") for c in NOT_SHOP)]
        row = {"id": r.ID_Global, "ref": r.ref14, "address": "%s %s" % (r.Nom_Via, str(r.Num_Policia_Inicial).split(".")[0]),
               "barri": r.Nom_Barri, "district": r.Nom_Districte, "housing": r.housing}
        if r.housing == "NO":
            rows.append(dict(row, status="zone")); continue
        if not cand:
            rows.append(dict(row, status="no shop unit on the ground floor")); continue
        u = min(cand, key=lambda u: u["poly"].distance(door))
        if u["poly"].distance(door) > DOOR_MAX:
            rows.append(dict(row, status="door more than %.0f m from any shop unit" % DOOR_MAX)); continue
        g = u["poly"].simplify(0.15, preserve_topology=True)
        ext = list(g.exterior.coords)
        if g.exterior.is_ccw:                                   # clockwise: the outside is on the left of each edge
            ext = ext[::-1]
        others = [v["poly"] for v in units if v is not u]
        inside = lambda p: g.contains(p) or any(o.contains(p) for o in others) or any(foots[int(i)].contains(p) for i in btree.query(p))
        street, opened = [], []
        for a, c in zip(ext[:-1], ext[1:]):
            L = math.hypot(c[0] - a[0], c[1] - a[1])
            if L < 0.8:
                continue
            nx, ny = -(c[1] - a[1]) / L, (c[0] - a[0]) / L
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            q, far = Point(mx + 1.5 * nx, my + 1.5 * ny), Point(mx + 6.0 * nx, my + 6.0 * ny)
            if any(streets[int(i)].contains(q) for i in stree.query(q)):
                street.append((a, c))
            elif not inside(q) and not inside(far):
                opened.append((a, c))
        x0, y0 = g.bounds[0], g.bounds[1]
        loc = lambda p: [round(p[0] - x0, 2), round(p[1] - y0, 2)]
        sl, ol = sum(math.dist(a, c) for a, c in street), sum(math.dist(a, c) for a, c in opened)
        row.update(unit_use=u["use"], unit_code=u["code"], unit_m2=round(g.area, 1), street_facade_m=round(sl, 1), open_facade_m=round(ol, 1))
        key = r.ref14 + "_" + r.ID_Global
        shells[key] = {"ref": r.ref14, "id": r.ID_Global, "outline": [loc(p) for p in ext], "facade": [[loc(a), loc(c)] for a, c in street + opened],
                       "street": [[loc(a), loc(c)] for a, c in street], "origin_utm": [round(x0, 2), round(y0, 2)], "height": HEIGHT,
                       "unit_use": u["use"], "unit_code": u["code"]}
        if r.housing != "YES" or g.area < 40 or sl + ol < 3:
            rows.append(dict(row, status="outline found; " + ("zone" if r.housing != "YES" else "under 40 m²" if g.area < 40 else "façade under 3 m")))
            continue
        shop = {"ok": True, "outline": shells[key]["outline"], "facade": shells[key]["facade"], "street": shells[key]["street"],
                "height": HEIGHT, "name": "BCN_" + r.ref14, "source": "%s (Catastro %s, ground-floor unit)" % (row["address"], r.ref14), "image": None}
        core.add_zoning(shop, r.ref14)
        try:
            t = time.time()
            before, its, _ = core.generator().iterations(shop["outline"], shop["facade"], HEIGHT, MIX, progs, street=shop["street"])
            after = max([p for _, p, _ in its] or [before], key=lambda p: (p["proposal_ok"], p["compliant"]))   # as core.run
            cell = 0.25 if g.area < 400 else 0.5
            b, a = [core.flags.analyse(shop["outline"], shop["facade"], HEIGHT, p, cell=cell, zoning=shop.get("zoning")) for p in (before, after)]
            row.update(status="modelled", as_is=b["verdict"], as_is_passing=b["flats_passing"], after=a["verdict"],
                       after_passing=a["flats_passing"], most_homes=max([p["compliant"] for _, p, _ in its] or [0]),
                       seconds=round(time.time() - t, 1))
        except Exception as ex:
            row.update(status="error: %s" % str(ex)[:100])
        rows.append(row)
        if len(rows) % 50 == 0:
            print("  %d / %d" % (len(rows), len(todo)), flush=True)
    json.dump(shells, open(OUT / "catastro_shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "catastro_results.csv", index=False, encoding="utf-8")
    m = d[d.status == "modelled"]
    summ = {"not_modelled_with_catastro_plan": int(len(d)), "outline_found": int(d.status.str.startswith(("outline", "modelled")).sum()),
            "modelled": int(len(m)), "status": d.status.str.split(";").str[0].value_counts().to_dict(),
            "as_is": m.as_is.value_counts().to_dict() if len(m) else {}, "after": m.after.value_counts().to_dict() if len(m) else {},
            "homes_as_asked_after": int(m.after_passing.sum()) if len(m) else 0, "most_homes": int(m.most_homes.sum()) if len(m) else 0,
            "shops_with_a_home": int((m.most_homes > 0).sum()) if len(m) else 0}
    json.dump(summ, open(OUT / "catastro_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
