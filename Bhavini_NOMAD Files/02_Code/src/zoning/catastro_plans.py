"""Nomad - Step 3 extra: the Catastro ground-floor plan of every empty premises' parcel.

Catastro's 3D viewer (Sede Electrónica del Catastro, Visor 3D) embeds, for buildings with detailed data (FXCC
floor sketches), every unit of every floor as a polygon with its use and built area. This script reads that for
the parcel (14-character cadastral reference) of each empty ground-floor premises in results/zoning/lookup.json,
keeps the ground floor (Planta 0) and the number of floors, and writes one small file per parcel for the website:
  site/data/catastro/<ref>.json   {"ref", "address", "floors", "units": [{"use", "code", "m2", "pts": [[x, y], ...]}]}
                                  (pts in metres, origin at the south-west corner of the ground floor, y north)
  results/zoning/catastro_plans.json   per parcel: has data or not, units on the ground floor, floors
Not an official API: one page per parcel, 1.5 s apart, resumable (parcels already fetched are skipped).
Source: Dirección General del Catastro (Sede Electrónica del Catastro). Run: .venv/Scripts/python src/zoning/catastro_plans.py [limit]
"""
import json, math, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "data" / "catastro"
SUMMARY = ROOT / "results" / "zoning" / "catastro_plans.json"
RAW = ROOT / "data" / "barcelona" / "catastro" / "floors"          # every floor as Catastro gives it (lon/lat), for shop outlines
URL = "https://www1.sedecatastro.gob.es/Cartografia/FXCC/Visor3D.aspx"
HEAD = {"User-Agent": "NOMAD student project (IAAC Barcelona); one request per 1.5 s"}
PAUSE = 1.5


def fetch(ref):
    t = requests.get(URL, params={"del": 8, "mun": 900, "refcat": ref, "final": ""}, headers=HEAD, timeout=60).text
    m = re.search(r"var edificio3D_geojson=(\{.*?\});var UrlFacade", t, re.S)
    return json.loads(m.group(1)) if m else None


def ground_floor(g):
    feats = g.get("features") or []
    ground = [f for f in feats if f["properties"].get("Planta") == 0 and f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
    if not ground:
        return None
    rings = []
    for f in ground:
        c = f["geometry"]["coordinates"]
        rings.append(c[0] if f["geometry"]["type"] == "Polygon" else max((p[0] for p in c), key=len))
    lon0 = min(p[0] for r in rings for p in r)
    lat0 = min(p[1] for r in rings for p in r)
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110574.0          # degrees -> metres, fine at a building's size
    units = []
    for f, r in zip(ground, rings):
        p = f["properties"]
        units.append({"use": p.get("Descripcion", ""), "code": p.get("Uso", ""), "m2": p.get("Superficie"),
                      "pts": [[round((x - lon0) * kx, 2), round((y - lat0) * ky, 2)] for x, y in r]})
    floors = sorted(set(f["properties"].get("Planta") for f in feats if f["properties"].get("Planta") is not None))
    return {"ref": g["localizacion"]["ReferenciaCatastral"], "address": g["localizacion"].get("Direccion1", ""),
            "floors": len([k for k in floors if k >= 0]), "basements": len([k for k in floors if k < 0]), "units": units}


def main(limit=None):
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {}
    refs = sorted(set(r["ref"] for r in json.load(open(ROOT / "results" / "zoning" / "lookup.json", encoding="utf-8")) if r.get("ref")))
    first = set()                                     # the shops NOMAD could not model yet go first (src/check/avoid.py)
    av = ROOT / "results" / "avoid" / "avoid.csv"
    if av.exists():
        import csv
        ids = set(r["ID_Global"] for r in csv.DictReader(open(av, encoding="utf-8")) if r.get("answer") == "not modelled")
        first = set((r.get("Referencia_Cadastral") or "")[:14] for r in csv.DictReader(open(ROOT / "results" / "zoning" / "empty_premises_zoning.csv", encoding="utf-8"))
                    if r.get("ID_Global") in ids)
    todo = sorted((r for r in refs if r not in summary), key=lambda r: r not in first)[: limit or None]
    print("parcels %d, done %d, to do %d" % (len(refs), len(summary), len(todo)), flush=True)
    for k, ref in enumerate(todo, 1):
        try:
            g = fetch(ref)
            plan = ground_floor(g) if g else None
            if plan:                                      # the website's files are built by src/zoning/catastro_site.py
                (RAW / (ref + ".json")).write_text(json.dumps(g, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            summary[ref] = {"plan": bool(plan), "units": len(plan["units"]) if plan else 0, "floors": plan["floors"] if plan else None}
        except Exception as e:                        # network hiccup: leave it for the next run
            print(ref, "error", e, flush=True)
        if k % 50 == 0 or k == len(todo):
            SUMMARY.write_text(json.dumps(summary, indent=0), encoding="utf-8")
            n = sum(1 for v in summary.values() if v["plan"])
            print("%d / %d fetched, %d with a ground-floor plan" % (len(summary), len(refs), n), flush=True)
        time.sleep(PAUSE)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
