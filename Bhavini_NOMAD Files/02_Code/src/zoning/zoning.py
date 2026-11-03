"""Nomad - Step 3 (Exp 5): the urban zoning of every empty ground-floor premises in Barcelona.

Inputs (official, open):
  census  Ajuntament de Barcelona, "Cens de locals en planta baixa destinats a activitat econòmica" 2024
          (Open Data BCN, CC BY 4.0): data/barcelona/census/2024_CensComercial_BCN.csv. Empty = sector "Locals buits ...".
  zoning  Mapa Urbanístic de Catalunya (MUC), layer "MUC Qualificació", Departament de Territori, Generalitat de
          Catalunya (served by Diputació de Barcelona: gissrv.diba.cat/arcgis/rest/services/CARTOBASE/MUC/MapServer/1;
          data of January 2023). Fetched once for Barcelona (CODI_INE 08019), 2,000 polygons per request, cached.
Each premises is matched to the zone polygon it stands in (point in polygon, EPSG:25831), then to the gate:
  PGM art. 225.7 (MPGM 1999): housing on a ground floor is admitted in the zones built along street lines
  (residential keys 12, 13, 14, 15 ...), with conditions; industrial zones and systems (streets, parks,
  facilities) do not take housing. The zone -> answer table is ZONE_RULES below, one line per zone name.
Run:   .venv/Scripts/python src/zoning/zoning.py [--fetch]
Out:   data/barcelona/zoning/muc_qualificacio_bcn.geojson (cache)
       results/zoning/empty_premises_zoning.csv, results/zoning/summary.json
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
CENSUS = ROOT / "data" / "barcelona" / "census" / "2024_CensComercial_BCN.csv"
CACHE = ROOT / "data" / "barcelona" / "zoning" / "muc_qualificacio_bcn.geojson"
OUT = ROOT / "results" / "zoning"
MUC = "https://gissrv.diba.cat/arcgis/rest/services/CARTOBASE/MUC/MapServer/1/query"


# zone name (D_QUAL_AJT, or its start) -> (PGM key, answer, why). YES = art. 225.7 admits housing on the ground floor
# (zones along street lines); CHECK = the zone's own plan decides; NO = not a residential zone.
ZONE_RULES = [
    ("Nucli Antic", "12", "YES", "casc antic, built along street lines: PGM art. 225.7"),
    ("Nucli antis", "12", "YES", "casc antic, built along street lines: PGM art. 225.7"),
    ("Densificació Urbana Intensiva", "13a", "YES", "built along street lines (e.g. Eixample): PGM art. 225.7"),
    ("Densificació Urbana Semiintensiva", "13b", "YES", "built along street lines: PGM art. 225.7"),
    ("Densificació urbana sobre", "13", "CHECK", "zone 13 over a system: check the plan"),
    ("Conservació est. urbana", "15", "YES", "conservation of the urban structure, along street lines: PGM art. 225.7"),
    ("Renovació urbana: rehabilitació", "14b", "YES", "urban renewal by rehabilitation: residential, along street lines"),
    ("Renovació urbana: transformació", "14a", "NO", "to become a street, park or facility"),
    ("Remodelació física", "14", "CHECK", "remodelling area: its own plan decides"),
    ("Ordenació en volumetria específica", "18", "CHECK", "specific volumetry: ground-floor use set by its plan (art. 225.6)"),
    ("Residencial en vol. esp.", "18", "CHECK", "specific volumetry inside 22@: its plan decides"),
    ("Volumetria especifica", "18", "CHECK", "specific volumetry over a facility: its plan decides"),
    ("Zona residencial sobre", "18", "CHECK", "housing over the railway: its plan decides"),
    ("Ordenació en edif. aïllada", "20", "CHECK", "isolated buildings: residential, but art. 225.7 covers street-line zones"),
    ("Ordenació en edificació aïllada", "20", "CHECK", "isolated buildings: residential, but art. 225.7 covers street-line zones"),
    ("Zona d'activitats @", "22@", "CHECK", "22@ activity zone: housing only where the 22@ plan allows it"),
    ("Zona industrial", "22a", "NO", "industrial zone"),
    ("Terciari", "", "NO", "port tertiary zone"),
    ("Habitatge dotacional", "", "NO", "public dwellings system (not a private conversion)"),
    ("Verd privat", "", "NO", "protected private green"),
]


def gate(name, code):
    for start, key, ans, why in ZONE_RULES:
        if (name or "").startswith(start):
            return key, ans, why
    if (code or "").startswith("S") or not code:
        return "", "NO", "urban system (street, park, facility, railway, port...)"
    # another town's own plan: the harmonised MUC code (A1 industrial, A2 tertiary, N non-urbanisable, R residential,
    # D development, M transformation / conservation)
    if code.startswith("A1"):
        return code, "NO", "industrial zone (MUC %s)" % code
    if code.startswith("A2"):
        return code, "NO", "tertiary zone (MUC %s)" % code
    if code.startswith("N"):
        return code, "NO", "non-urbanisable land (MUC %s)" % code
    if code.startswith("R"):
        return code, "CHECK", "residential zone of the town's own plan (MUC %s): its rules decide" % code
    return "", "CHECK", "zone not in NOMAD's table yet (MUC %s): its plan decides" % code


def fetch():
    feats, off = [], 0
    while True:
        q = {"where": "CODI_INE='08019'", "outFields": "OBJECTID,C_QUAL_MUC,D_QUAL_AJT", "returnGeometry": "true",
             "outSR": "25831", "resultOffset": str(off), "resultRecordCount": "2000", "orderByFields": "OBJECTID", "f": "geojson"}
        with urllib.request.urlopen(MUC + "?" + urllib.parse.urlencode(q), timeout=120) as r:
            page = json.load(r)
        got = page.get("features", [])
        feats += got
        print("  fetched", len(feats), flush=True)
        if len(got) < 2000:
            break
        off += 2000
        time.sleep(1.0)                                    # be polite to the server
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats, "source": MUC, "fetched": time.strftime("%Y-%m-%d"),
               "licence": "MUC, Departament de Territori, Generalitat de Catalunya"}, open(CACHE, "w", encoding="utf-8"))
    return feats


def load_zones():
    feats = json.load(open(CACHE, encoding="utf-8"))["features"] if CACHE.exists() else fetch()
    geoms, attrs = [], []
    for f in feats:
        if f.get("geometry"):
            geoms.append(shape(f["geometry"]).buffer(0))
            attrs.append(f["properties"])
    return geoms, attrs


def empty_premises():
    d = pd.read_csv(CENSUS, encoding="utf-8-sig", low_memory=False)
    e = d[d["Nom_Sector_Activitat"].str.startswith("Locals buits", na=False)].copy()
    return e[["ID_Global", "Nom_Activitat", "X_UTM_ETRS89", "Y_UTM_ETRS89", "Direccio_Unica", "Nom_Via", "Num_Policia_Inicial",
              "Nom_Barri", "Nom_Districte", "Referencia_Cadastral"]].reset_index(drop=True)


def zone_of(points, geoms, attrs):
    tree = STRtree(geoms)
    out = []
    for p in points:
        hit = None
        for i in tree.query(p, predicate="intersects"):
            hit = attrs[int(i)]
            break
        if hit is not None and (hit["C_QUAL_MUC"] or "").startswith("SX"):
            # the census point is the shop door, on the façade line: when it falls in the street, take the zone of
            # the building behind it (the nearest zone that is not a street, within 8 m)
            near = [(geoms[int(i)].distance(p), int(i)) for i in tree.query(p.buffer(8.0))
                    if not (attrs[int(i)]["C_QUAL_MUC"] or "").startswith("SX")]
            if near:
                hit = dict(attrs[min(near)[1]], near=True)
        if hit is None:                                      # on a street edge: nearest zone within 5 m
            i = tree.nearest(p)
            if geoms[int(i)].distance(p) <= 5.0:
                hit = dict(attrs[int(i)], near=True)
        out.append(hit)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download the zoning again")
    a = ap.parse_args()
    if a.fetch or not CACHE.exists():
        fetch()
    geoms, attrs = load_zones()
    e = empty_premises()
    pts = [Point(x, y) for x, y in zip(e.X_UTM_ETRS89, e.Y_UTM_ETRS89)]
    z = zone_of(pts, geoms, attrs)
    e["muc_code"] = [h["C_QUAL_MUC"] if h else "" for h in z]
    e["zone"] = [h["D_QUAL_AJT"] if h else "" for h in z]
    e["on_edge"] = [bool(h and h.get("near")) for h in z]
    g = [gate(h["D_QUAL_AJT"], h["C_QUAL_MUC"]) if h else ("", "CHECK", "no zone found within 5 m") for h in z]
    e["pgm_key"], e["housing"], e["why"] = zip(*g)
    OUT.mkdir(parents=True, exist_ok=True)
    e.to_csv(OUT / "empty_premises_zoning.csv", index=False, encoding="utf-8")
    # the same answers as a small JSON for NOMAD.gh (IronPython's csv cannot read accents): nomad_core.zoning_lookup
    look = [{"ref": r.Referencia_Cadastral if isinstance(r.Referencia_Cadastral, str) else "", "street": r.Nom_Via,
             "num": str(r.Num_Policia_Inicial).split(".")[0], "barri": r.Nom_Barri, "zone": r.zone, "pgm_key": r.pgm_key,
             "housing": r.housing, "why": r.why} for r in e.itertuples()]
    json.dump(look, open(OUT / "lookup.json", "w", encoding="utf-8"), ensure_ascii=False)
    eix = e[e.Nom_Districte == "Eixample"]
    summ = {"empty_premises": len(e), "zone_polygons": len(geoms), "matched": int((e.zone != "").sum()),
            "on_edge_nearest": int(e.on_edge.sum()),
            "housing": e.housing.value_counts().to_dict(),
            "by_key": e[e.housing == "YES"].pgm_key.value_counts().to_dict(),
            "eixample": {"empty": len(eix), "housing": eix.housing.value_counts().to_dict()},
            "by_district": {k: g_.housing.value_counts().to_dict() for k, g_ in e.groupby("Nom_Districte")},
            "top_zones": e.zone.value_counts().head(12).to_dict(),
            "sources": {"census": "Open Data BCN, cens-locals-planta-baixa-act-economica, 2024 (CC BY 4.0)",
                        "zoning": "MUC Qualificació, Departament de Territori (Generalitat), via " + MUC.rsplit("/query", 1)[0]}}
    json.dump(summ, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: summ[k] for k in ("empty_premises", "matched", "on_edge_nearest", "housing", "by_key", "eixample")},
                     ensure_ascii=False, indent=1))
