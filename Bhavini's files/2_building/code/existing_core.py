"""Nomad - the building's existing common parts on the ground floor (portal, stair, lift), for the real shops.

A shop's shell (2_building/code/real_shops.py) is the building's whole ground floor, so it contains the building's own
portal and stair. Where the Catastro has a floor-by-floor plan (2_building/code/catastro_plans.py), its ground-floor "Local
COMUN" units are exactly those parts. They are added to the shell as "existing" (polygons in the shell's local metres):
the generator (7_floor_plans/code/plan3.py) never draws a flat or a hall over them, and uses the portal on the street as the
flats' entrance (Finch: "around existing circulation").
Out: 2_building/output/real_shops/shells.json updated in place (key "existing" on the shells that have a Catastro plan)
Run: .venv/Scripts/python 2_building/code/existing_core.py
"""
import json
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
FLOORS = ROOT / "private/catastro_visor_floors"
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True)


def main():
    p = ROOT / "2_building/output/real_shops/shells.json"
    S = json.load(open(p, encoding="utf-8"))
    n = 0
    for ref, s in S.items():
        f = FLOORS / (ref + ".json")
        s.pop("existing", None)
        if not f.exists():
            continue
        x0, y0 = s["origin_utm"]
        ex = []
        for ft in json.load(open(f, encoding="utf-8")).get("features") or []:
            pr, geo = ft["properties"], ft["geometry"]
            if pr.get("Planta") != 0 or not str(pr.get("Uso") or "").startswith(("COMUN", "COM.")):
                continue
            rings = [geo["coordinates"][0]] if geo["type"] == "Polygon" else [q[0] for q in geo["coordinates"]]
            for ring in rings:
                g = Polygon([TO_UTM.transform(x, y) for x, y in ring]).buffer(0)
                if g.is_empty or g.area < 1.0:
                    continue
                g = g if g.geom_type == "Polygon" else max(g.geoms, key=lambda q: q.area)
                ex.append([[round(x - x0, 2), round(y - y0, 2)] for x, y in list(g.exterior.coords)[:-1]])
        if ex:
            s["existing"] = ex
            n += 1
    json.dump(S, open(p, "w", encoding="utf-8"), separators=(",", ":"))
    print("shells with the building's existing portal / stair: %d" % n)


if __name__ == "__main__":
    main()
