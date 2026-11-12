"""Nomad - real Barcelona buildings from the Catastro (Dirección General del Catastro, INSPIRE Buildings, open data).

Source: https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/08/08900-BARCELONA/A.ES.SDGC.BU.08900.zip
(49.7 MB zip, 1.15 GB of GML inside) in 0_shared_input/catastro/raw/. Read straight from the zip, never unpacked.
  building.gml      one Building per cadastral parcel: reference (14 characters, the key used by the census of premises),
                    footprint, current use, number of units and dwellings, gross floor area (m²)
  buildingpart.gml  the parts of each building: outline + floors above and below ground (a part with 0 floors above
                    ground is a courtyard or terrace)
Out: 0_shared_input/catastro/buildings.json.gz (every building, EPSG:25831, coordinates to 1 cm)
Run: .venv/Scripts/python 2_building/code/catastro_buildings.py
"""
import gzip, json, re, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "0_shared_input/catastro/raw/A.ES.SDGC.BU.08900.zip"
OUT = ROOT / "0_shared_input/catastro/buildings.json.gz"

RE_ID = re.compile(r'gml:id="ES\.SDGC\.BU\.([0-9A-Z]{14})(?:_part(\d+))?"')
RE_POS = re.compile(r"<gml:(exterior|interior)>\s*<gml:LinearRing>\s*<gml:posList[^>]*>([^<]+)</gml:posList>")
FIELD = {k: re.compile(r"<bu-ext2d:%s[^>]*>([^<]*)</bu-ext2d:%s>" % (k, k)) for k in
         ("currentUse", "numberOfBuildingUnits", "numberOfDwellings", "numberOfFloorsAboveGround", "numberOfFloorsBelowGround")}
RE_AREA = re.compile(r"<bu-ext2d:value uom=\"m2\">([0-9.]+)</bu-ext2d:value>")


def features(name):
    """Yield the text of each feature in one GML file of the zip, reading it in pieces."""
    with zipfile.ZipFile(ZIP) as z, z.open(name) as f:
        buf = ""
        while True:
            chunk = f.read(8 << 20)
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            parts = buf.split("</gml:featureMember>")
            buf = parts.pop()
            yield from parts


def rings(txt):
    """Polygon rings as [[exterior], [hole], ...] per patch (a new patch starts at each exterior)."""
    polys = []
    for kind, pos in RE_POS.findall(txt):
        v = [float(x) for x in pos.split()]
        ring = [[round(v[i], 2), round(v[i + 1], 2)] for i in range(0, len(v) - 1, 2)]
        if kind == "exterior":
            polys.append([ring])
        elif polys:
            polys[-1].append(ring)
    return polys


def num(m):
    try:
        return int(float(m.group(1))) if m and m.group(1).strip() else None
    except ValueError:
        return None


def main():
    bld = {}
    for t in features("A.ES.SDGC.BU.08900.building.gml"):
        m = RE_ID.search(t)
        if not m:
            continue
        a = RE_AREA.search(t)
        bld[m.group(1)] = {"use": (FIELD["currentUse"].search(t) or [None, ""])[1], "units": num(FIELD["numberOfBuildingUnits"].search(t)),
                           "dwellings": num(FIELD["numberOfDwellings"].search(t)), "area": float(a.group(1)) if a else None,
                           "foot": rings(t), "parts": []}
    print("buildings:", len(bld), flush=True)
    n = 0
    for t in features("A.ES.SDGC.BU.08900.buildingpart.gml"):
        m = RE_ID.search(t)
        if not m or m.group(1) not in bld:
            continue
        bld[m.group(1)]["parts"].append({"up": num(FIELD["numberOfFloorsAboveGround"].search(t)),
                                         "down": num(FIELD["numberOfFloorsBelowGround"].search(t)), "poly": rings(t)})
        n += 1
    print("building parts:", n, flush=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(bld, f, separators=(",", ":"))
    print("saved", OUT, round(OUT.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
