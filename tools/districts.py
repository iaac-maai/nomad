"""NOMAD - Barcelona's 10 official district boundaries for the site, and how many places change district with them.

Source: Open Data BCN, "Unitats administratives de la ciutat de Barcelona" (BarcelonaCiutat_Districtes.csv,
geometry in ETRS89 / UTM 31N, the same coordinates as the site's data), CC BY 4.0, Ajuntament de Barcelona.
Writes nomad/04_Website/data/districts.json: each district's rings, simplified to 1 m (the page finds a place's district
by point in polygon). Before, an empty shop took the census's district and a building with no census address took the
district of the nearest census shop; the script counts the places that change.

Run from the repo root:  python tools/districts.py [BarcelonaCiutat_Districtes.csv]   (downloads it when no file is given)
"""
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "nomad" / "04_Website" / "data"
URL = ("https://opendata-ajuntament.barcelona.cat/data/dataset/808daafa-d9ce-48c0-925a-fa5afdb1ed41/resource/"
       "576bc645-9481-4bc4-b8bf-f5972c20df3f/download")
TOL = 1.0                                                       # m, simplification


def rings_of(wkt):
    """POLYGON / MULTIPOLYGON WKT -> list of rings [[x, y], ...] (outer rings and holes; even-odd inside test)."""
    return [[[float(a) for a in p.split()] for p in ring.split(",")] for ring in re.findall(r"\(([^()]+)\)", wkt)]


def simplify(pts, tol):
    if len(pts) < 4:
        return pts
    def rdp(a, b):
        (x1, y1), (x2, y2) = pts[a], pts[b]
        L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1e-9
        i, dm = 0, 0.0
        for k in range(a + 1, b):
            d = abs((y2 - y1) * pts[k][0] - (x2 - x1) * pts[k][1] + x2 * y1 - y2 * x1) / L
            if d > dm:
                i, dm = k, d
        return rdp(a, i)[:-1] + rdp(i, b) if dm > tol else [pts[a], pts[b]]
    sys.setrecursionlimit(100000)
    # a closed ring starts and ends on the same point: split it at the point farthest from the start
    k = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    if k in (0, len(pts) - 1):
        return pts
    return rdp(0, k)[:-1] + rdp(k, len(pts) - 1)


def inside(x, y, rings):
    c = False
    for r in rings:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i - 1], r[i]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


def dist(x, y, rings):
    best = 1e18
    for r in rings:
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i - 1], r[i]
            dx, dy = x2 - x1, y2 - y1
            t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
            best = min(best, ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5)
    return best


def district(x, y, D):
    """-> (name, how): inside a district, or (outside every boundary) the nearest one within 300 m."""
    for d in D:
        if inside(x, y, d["rings"]):
            return d["name"], "inside"
    name, m = min(((d["name"], dist(x, y, d["rings"])) for d in D), key=lambda t: t[1])
    return (name, f"nearest, {m:.0f} m outside") if m <= 300 else ("", f"{m:.0f} m outside every district")


def rows(path):
    j = json.loads((SITE / path).read_text(encoding="utf-8"))
    return [dict(zip(j["cols"], r)) for r in j["rows"]]


def main():
    csv.field_size_limit(10 ** 9)
    text = (Path(sys.argv[1]).read_text(encoding="utf-8-sig") if len(sys.argv) > 1
            else urllib.request.urlopen(URL, timeout=120).read().decode("utf-8-sig"))
    full = [{"name": r["nom_districte"], "rings": rings_of(r["geometria_etrs89"])} for r in csv.DictReader(io.StringIO(text))]
    out = {"about": "Barcelona's 10 districts (official boundaries), simplified to 1 m. Built by tools/districts.py.",
           "source": "Ajuntament de Barcelona, Open Data BCN: Unitats administratives de la ciutat (BarcelonaCiutat_Districtes.csv), CC BY 4.0",
           "crs": "EPSG:25831",
           "districts": [{"name": d["name"], "rings": [[[round(x, 1), round(y, 1)] for x, y in simplify(r, TOL)] for r in d["rings"]]}
                         for d in full]}
    (SITE / "districts.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    simp = out["districts"]
    # before: the census district for a shop; for a building, its own or the nearest census shop's (page's nearDistrict)
    P, W = rows("premises.json"), [r for r in rows("warehouses.json") if r.get("status") != "active business"]
    grid = {}
    for r in P:
        if r.get("district"):
            grid.setdefault((r["x"] // 250, r["y"] // 250), []).append(r)
    def near(x, y):
        best, bd = None, 1e18
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for r in grid.get((x // 250 + dx, y // 250 + dy), []):
                    d = (r["x"] - x) ** 2 + (r["y"] - y) ** 2
                    if d < bd:
                        best, bd = r, d
        return best["district"] if best else ""
    places = [("shop", r, r.get("district") or "") for r in P] + [("building", r, r.get("district") or near(r["x"], r["y"])) for r in W]
    changed, hows, nodist_before, examples, simp_diff = 0, {}, 0, [], 0
    for kind, r, before in places:
        after, how = district(r["x"], r["y"], full)
        hows[how.split(",")[0].split(" m ")[0] if how != "inside" else "inside"] = hows.get(how.split(",")[0] if how != "inside" else "inside", 0) + 1
        nodist_before += not before
        simp_diff += district(r["x"], r["y"], simp)[0] != after
        if after != before:
            changed += 1
            if len(examples) < 12:
                examples.append(f"{kind:8} {r.get('street') or ''} {r.get('num') or ''} ({r['ref']}): {before or '(no district)'} -> {after or '(none)'} [{how}]")
    print(f"{len(places)} places ({len(P)} shops, {len(W)} buildings not in use)")
    print(f"no district before: {nodist_before}")
    print(f"district changed: {changed}")
    print("how found now:", {k: v for k, v in hows.items()})
    print(f"simplified (1 m) boundaries give a different district for {simp_diff} places")
    print("\n".join(examples))
    print(f"wrote {SITE / 'districts.json'} ({(SITE / 'districts.json').stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
