"""Base map of the metropolitan area for the website: the MUC zones of the 36 AMB towns (cached by amb.py), merged into
residential / green / other as on Barcelona's map, plus each town's outline and centre. Out: app/data/amb_base.json."""
import glob, json, os
from collections import Counter
from shapely.geometry import Point, Polygon, shape
from shapely.ops import unary_union
from shapely.prepared import prep
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOL, MIN_AREA = 25.0, 3000

def kind(c):
    c = c or ""
    if c.startswith("SX"):
        return None
    if c.startswith(("SV", "N")):
        return "green"
    if c.startswith(("R", "M1", "M3", "SD")) or c == "M2":
        return "res"
    return "other"

def rings(g):
    out = []
    for p in (g.geoms if g.geom_type in ("MultiPolygon", "GeometryCollection") else [g]):
        if p.geom_type != "Polygon" or p.area < MIN_AREA:
            continue
        out.append([[round(x), round(y)] for x, y in p.exterior.coords])
        out += [[[round(x), round(y)] for x, y in h.coords] for h in p.interiors if Polygon(h).area > 20000]
    return out

A = json.load(open(os.path.join(ROOT, "app", "data", "amb.json"), encoding="utf-8"))
byine, seen = {}, set()                                                  # the files are cut by bounding box: rebuild each town from CODI_INE
for f in sorted(glob.glob(os.path.join(ROOT, "1_find_the_shops", "input", "amb", "zoning", "*.geojson"))):
    for x in json.load(open(f, encoding="utf-8"))["features"]:
        if x.get("geometry") and x.get("id") not in seen:
            seen.add(x.get("id"))
            byine.setdefault(str(x["properties"].get("CODI_INE")), []).append((shape(x["geometry"]).buffer(0).simplify(4), x["properties"].get("C_QUAL_MUC")))
groups, towns = {}, []
for ine, fs in byine.items():
    u = unary_union([g for g, _ in fs]).buffer(40).buffer(-40)
    v = prep(u)
    hit = Counter(p[4] for p in A["pts"] if v.contains(Point(p[0], p[1])))
    if not hit:
        continue                                                         # a neighbour outside the metropolitan area
    for g, c in fs:
        k = kind(c)
        if k:
            groups.setdefault(k, []).append(g)
    u = u.simplify(TOL); c = u.representative_point()
    towns.append({"town": hit.most_common(1)[0][0], "x": round(c.x), "y": round(c.y), "rings": rings(u)})
out = {k: rings(unary_union(v).simplify(TOL)) for k, v in groups.items()}
out["towns"] = towns
p = os.path.join(ROOT, "app", "data", "amb_base.json")
json.dump(out, open(p, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
print(len(towns), "towns,", {k: len(v) for k, v in out.items() if k != "towns"}, round(os.path.getsize(p) / 1e6, 2), "MB")
