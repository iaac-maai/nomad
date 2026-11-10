"""Nomad - the building of every empty premises, for the website (Find your shop: plans by floor and 3D).

Per parcel (14-character cadastral reference of the census premises): the building parts with their floors above
and below ground (Catastro INSPIRE buildings, data/barcelona/catastro/buildings.json.gz, src/building/catastro_buildings.py).
The floor-by-floor units of the Catastro Visor 3D (src/zoning/catastro_plans.py) were removed on 9 Nov 2026: not open data.
Coordinates in metres from the building's south-west corner, "origin" (EPSG:25831), 0,1 m.
Out: site/data/catastro/b_<first two characters of ref>.json ({ref: building}), 100 files
Run: .venv/Scripts/python src/zoning/catastro_site.py
"""
import gzip, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "data" / "catastro"
USE = {"1_residential": "housing", "2_agriculture": "agriculture", "3_industrial": "industry", "4_1_office": "offices",
       "4_2_retail": "retail", "4_3_publicServices": "public services"}


def local(pts_lists, x0, y0):
    return [[[round(x - x0, 1), round(y - y0, 1)] for x, y in pts] for pts in pts_lists]


def main():
    B = json.load(gzip.open(ROOT / "data" / "barcelona" / "catastro" / "buildings.json.gz", "rt", encoding="utf-8"))
    refs = sorted(set(r["ref"] for r in json.load(open(ROOT / "results" / "zoning" / "lookup.json", encoding="utf-8")) if r.get("ref")))
    OUT.mkdir(parents=True, exist_ok=True)
    index, size, bundles = {}, 0, {}
    for ref in refs:
        b = B.get(ref)
        info = {"ref": ref, "use": USE.get((b or {}).get("use"), (b or {}).get("use") or ""),
                "dwellings": int(float((b or {}).get("dwellings") or 0)), "units_n": int(float((b or {}).get("units") or 0))}
        if b:                                                       # Visor 3D floor-by-floor units removed (not open data)
            parts = [{"up": p.get("up") or 0, "down": p.get("down") or 0, "rings": [r[0] for r in p["poly"]]} for p in b["parts"]]
            allp = [q for p in parts for r in p["rings"] for q in r]
            if not allp:
                continue
            x0, y0 = min(q[0] for q in allp), min(q[1] for q in allp)
            out = dict(info, source="building", origin=[round(x0, 1), round(y0, 1)], address="",
                       parts=[{"up": p["up"], "down": p["down"], "pts": pts} for p in parts for pts in local(p["rings"], x0, y0)])
        else:
            continue
        bundles.setdefault(ref[:2], {})[ref] = out
        index[ref] = out["source"]
    for old in OUT.glob("*.json"):
        old.unlink()
    for key, d in bundles.items():                   # 100 files (the website holds at most a few hundred), by ref prefix
        txt = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
        (OUT / ("b_%s.json" % key)).write_text(txt, encoding="utf-8")
        size += len(txt)
    print("parcels %d: %d with units by floor, %d building only; %.1f MB" % (
        len(index), sum(v == "units" for v in index.values()), sum(v == "building" for v in index.values()), size / 1e6))


if __name__ == "__main__":
    main()
