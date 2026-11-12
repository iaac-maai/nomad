"""Nomad - the metropolitan area (AMB, 36 towns): warehouses, commercial and office buildings with no homes, and what
their zone allows, so the opportunity is shown beyond Barcelona (critic C, 29 Oct review).

Sources (open data, as for Barcelona):
  Catastro INSPIRE Buildings, one zip per town, links from the Catastro's own index
    https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/08/ES.SDGC.BU.atom_08.xml (1_find_the_shops/input/amb/catastro/atom_08.xml)
    read straight from each zip (2_building/code/catastro_buildings.py), only the buildings with no homes kept, zip deleted
  MUC zoning (Generalitat de Catalunya, served by the Diputació de Barcelona), queried by each town's bounding box
  Zone answer: 1_find_the_shops/code/zoning.py gate (the PGM 1976 zone names most AMB towns share; another town's own plan or an
  unknown zone name = CHECK; systems = NO). There is no census of empty premises outside Barcelona: in-use is unknown.
The 36 towns: the members of the Àrea Metropolitana de Barcelona.
Out: 1_find_the_shops/input/amb/candidates.csv, 1_find_the_shops/input/amb/towns.csv, app/data/amb.json
Run: .venv/Scripts/python 1_find_the_shops/code/amb.py
"""
import csv, gzip, json, math, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "1_find_the_shops/code"), str(ROOT / "2_building/code")]
import zoning as Z  # noqa: E402
import catastro_buildings as CB  # noqa: E402

D = ROOT / "1_find_the_shops/input/amb"
TOWNS = [("08015", "BADALONA", "Badalona"), ("08312", "BADIA DEL VALLES", "Badia del Vallès"), ("08252", "BARBERA DEL VALLES", "Barberà del Vallès"),
         ("08900", "BARCELONA", "Barcelona"), ("08020", "BEGUES", "Begues"), ("08053", "CASTELLBISBAL", "Castellbisbal"),
         ("08055", "CASTELLDEFELS", "Castelldefels"), ("08266", "CERDANYOLA DEL VALLES", "Cerdanyola del Vallès"), ("08067", "CERVELLO", "Cervelló"),
         ("08071", "CORBERA DE LLOBREGAT", "Corbera de Llobregat"), ("08072", "CORNELLA DE LLOBREGAT", "Cornellà de Llobregat"),
         ("08076", "ESPLUGUES DE LLOBREGAT", "Esplugues de Llobregat"), ("08088", "GAVA", "Gavà"),
         ("08100", "L HOSPITALET DE LLOBREGAT", "L'Hospitalet de Llobregat"), ("08122", "MOLINS DE REI", "Molins de Rei"),
         ("08124", "MONTCADA I REIXAC", "Montcada i Reixac"), ("08125", "MONTGAT", "Montgat"), ("08156", "PALLEJA", "Pallejà"),
         ("08313", "LA PALMA DE CERVELLO", "La Palma de Cervelló"), ("08157", "EL PAPIOL", "El Papiol"), ("08168", "EL PRAT DE LLOBREGAT", "El Prat de Llobregat"),
         ("08179", "RIPOLLET", "Ripollet"), ("08193", "SANT ADRIA DE BESOS", "Sant Adrià de Besòs"), ("08195", "SANT ANDREU DE LA BARCA", "Sant Andreu de la Barca"),
         ("08199", "SANT BOI DE LLOBREGAT", "Sant Boi de Llobregat"), ("08203", "SANT CLIMENT DE LLOBREGAT", "Sant Climent de Llobregat"),
         ("08204", "SANT CUGAT DEL VALLES", "Sant Cugat del Vallès"), ("08210", "SANT FELIU DE LLOBREGAT", "Sant Feliu de Llobregat"),
         ("08216", "SANT JOAN DESPI", "Sant Joan Despí"), ("08219", "SANT JUST DESVERN", "Sant Just Desvern"),
         ("08263", "SANT VICEN DELS HORTS", "Sant Vicenç dels Horts"), ("08244", "SANTA COLOMA DE CERVELLO", "Santa Coloma de Cervelló"),
         ("08245", "SANTA COLOMA DE GRAMENET", "Santa Coloma de Gramenet"), ("08282", "TIANA", "Tiana"),
         ("08289", "TORRELLES DE LLOBREGAT", "Torrelles de Llobregat"), ("08302", "VILADECANS", "Viladecans")]
KIND = {"3_industrial": "warehouse", "4_2_retail": "commercial", "4_1_office": "office"}


def town_buildings(code, name):
    """(all buildings count, homes count, {ref: candidate}) for one town, from its Catastro zip (deleted after reading)."""
    cache = D / "catastro" / ("%s.json.gz" % code)
    if cache.exists():
        return json.load(gzip.open(cache, "rt", encoding="utf-8"))
    if code == "08900":                                         # Barcelona: already read (2_building/code/catastro_buildings.py)
        B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
        cand = dict((r, b) for r, b in B.items() if b["use"] in KIND and not b.get("dwellings"))
        out = {"n": len(B), "res": sum(1 for b in B.values() if b.get("dwellings")), "cand": cand}
    else:
        z = D / "catastro" / ("A.ES.SDGC.BU.%s.zip" % code)
        url = "https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/08/%s-%s/A.ES.SDGC.BU.%s.zip" % (code, urllib.parse.quote(name), code)
        subprocess.run(["curl", "-s", "-f", "-o", str(z), url], check=True, timeout=600)   # Windows curl (Python SSL fails on some public hosts)
        CB.ZIP = z
        n, res, cand = 0, 0, {}
        for t in CB.features("A.ES.SDGC.BU.%s.building.gml" % code):
            m = CB.RE_ID.search(t)
            if not m:
                continue
            n += 1
            use = (CB.FIELD["currentUse"].search(t) or [None, ""])[1]
            dw = CB.num(CB.FIELD["numberOfDwellings"].search(t))
            res += bool(dw)
            if use in KIND and not dw:
                a = CB.RE_AREA.search(t)
                cand[m.group(1)] = {"use": use, "area": float(a.group(1)) if a else None, "foot": CB.rings(t), "parts": []}
        for t in CB.features("A.ES.SDGC.BU.%s.buildingpart.gml" % code):
            m = CB.RE_ID.search(t)
            if m and m.group(1) in cand:
                cand[m.group(1)]["parts"].append({"up": CB.num(CB.FIELD["numberOfFloorsAboveGround"].search(t)),
                                                  "down": CB.num(CB.FIELD["numberOfFloorsBelowGround"].search(t))})
        z.unlink()                                              # keep only what NOMAD uses (no zips after reading)
        out = {"n": n, "res": res, "cand": cand}
    with gzip.open(cache, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    return out


def zones(bbox, code):
    """MUC zones in a bounding box (EPSG:25831), cached per town."""
    cache = D / "zoning" / ("%s.geojson" % code)
    if cache.exists():
        feats = json.load(open(cache, encoding="utf-8"))["features"]
    else:
        feats, off = [], 0
        while True:
            q = {"geometry": "%f,%f,%f,%f" % bbox, "geometryType": "esriGeometryEnvelope", "inSR": "25831", "spatialRel": "esriSpatialRelIntersects",
                 "outFields": "OBJECTID,C_QUAL_MUC,D_QUAL_AJT,CODI_INE", "returnGeometry": "true", "outSR": "25831",
                 "resultOffset": str(off), "resultRecordCount": "2000", "orderByFields": "OBJECTID", "f": "geojson"}
            with urllib.request.urlopen(Z.MUC + "?" + urllib.parse.urlencode(q), timeout=180) as r:
                page = json.load(r)
            got = page.get("features", [])
            feats += got
            if len(got) < 2000:
                break
            off += 2000
            time.sleep(1.0)
        cache.parent.mkdir(parents=True, exist_ok=True)
        json.dump({"type": "FeatureCollection", "features": feats, "source": Z.MUC, "fetched": time.strftime("%Y-%m-%d")},
                  open(cache, "w", encoding="utf-8"))
    geoms, attrs = [], []
    for f in feats:
        if f.get("geometry"):
            geoms.append(shape(f["geometry"]).buffer(0))
            attrs.append(f["properties"])
    return geoms, attrs


def main():
    (D / "catastro").mkdir(parents=True, exist_ok=True)
    trows, crows, pts = [], [], []
    for code, cname, name in TOWNS:
        t0 = time.time()
        tb = town_buildings(code, cname)
        cand = tb["cand"]
        polys = {}
        for ref, b in cand.items():
            g = MultiPolygon([Polygon(r[0], r[1:]) for r in b["foot"] if len(r[0]) >= 3]).buffer(0)
            if not g.is_empty:
                polys[ref] = g
        cnt = {"warehouse": 0, "commercial": 0, "office": 0}
        ans = {"YES": 0, "CHECK": 0, "NO": 0}
        m2 = {"YES": 0.0, "CHECK": 0.0}
        if polys:
            xs = [g.bounds for g in polys.values()]
            bbox = (min(b[0] for b in xs) - 50, min(b[1] for b in xs) - 50, max(b[2] for b in xs) + 50, max(b[3] for b in xs) + 50)
            geoms, attrs = zones(bbox, code)
            refs = list(polys)
            zs = Z.zone_of([polys[r].representative_point() for r in refs], geoms, attrs) if geoms else [None] * len(refs)
            for ref, z in zip(refs, zs):
                b = cand[ref]
                key, a, why = Z.gate(z.get("D_QUAL_AJT"), z.get("C_QUAL_MUC")) if z else ("", "NO", "no zone found")
                kind = KIND[b["use"]]
                floors = max([p["up"] or 0 for p in b["parts"]] or [1]) or 1
                cnt[kind] += 1
                ans[a] += 1
                p = polys[ref].representative_point()
                crows.append({"town": name, "ref": ref, "kind": kind, "zone": (z or {}).get("D_QUAL_AJT", ""), "muc": (z or {}).get("C_QUAL_MUC", ""),
                              "housing": a, "why": why, "built_m2": round(b["area"] or 0), "ground_m2": round(polys[ref].area), "floors": floors,
                              "x": round(p.x), "y": round(p.y)})
                if a in ("YES", "CHECK"):
                    m2[a] += b["area"] or 0
                    pts.append([round(p.x), round(p.y), kind[0], a[0], name, round(b["area"] or 0)])
        trows.append({"town": name, "code": code, "buildings": tb["n"], "with_homes": tb["res"], "no_homes_warehouse": cnt["warehouse"],
                      "no_homes_commercial": cnt["commercial"], "no_homes_office": cnt["office"], "zone_yes": ans["YES"], "zone_check": ans["CHECK"],
                      "zone_no": ans["NO"], "yes_built_m2": round(m2["YES"]), "check_built_m2": round(m2["CHECK"])})
        print("%-28s %6d buildings, %4d candidates (YES %d, CHECK %d) %.0fs" % (name, tb["n"], len(cand), ans["YES"], ans["CHECK"], time.time() - t0), flush=True)
    for fn, rows in (("towns.csv", trows), ("candidates.csv", crows)):
        with open(D / fn, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    json.dump({"towns": trows, "pts": pts, "cols": ["x", "y", "kind", "housing", "town", "built_m2"]},
              open(ROOT / "app/data/amb.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    tot = lambda k: sum(t[k] for t in trows)
    print("AMB: %d buildings; with no homes: %d warehouses, %d commercial, %d office; zone admits housing %d, plan decides %d, no %d"
          % (tot("buildings"), tot("no_homes_warehouse"), tot("no_homes_commercial"), tot("no_homes_office"), tot("zone_yes"), tot("zone_check"), tot("zone_no")))


if __name__ == "__main__":
    main()
