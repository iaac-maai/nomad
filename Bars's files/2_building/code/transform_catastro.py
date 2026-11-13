"""NOMAD - make the Catastro building data on the site clearly transformed data (Catastro INSPIRE licence v1.0, 2016:
public use of transformed data only; the original data must not go online untransformed). See docs/LICENCES.md.

data/catastro/b_*.json   per building: only the fields the site uses (use, dwellings, units_n, parts with up / down / pts);
                         outlines simplified (Douglas-Peucker, 0,5 m) and rounded to 0,5 m; every part is kept (its floors count).
                         Dropped: ref (the key already), source, origin, address.
data/warehouses.json     built and ground area rounded to 10 m², street and open façade lengths to 0,5 m; x / y are
                         already whole metres. Every column is used by the site, so none is dropped.
Run from the repo root after the shared source-building scripts:  python "Bars's files/2_building/code/transform_catastro.py"
Files already transformed (no 'origin' field) are left as they are, so running it twice changes nothing.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "Bars's files" / "app" / "data"
TOL, GRID = 0.5, 0.5


def rdp(pts, tol):
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    d = [abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / L if L else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
         for x, y in pts[1:-1]]
    i = max(range(len(d)), key=d.__getitem__) + 1
    return rdp(pts[:i + 1], tol)[:-1] + rdp(pts[i:], tol) if d[i - 1] > tol else [pts[0], pts[-1]]


def ring(pts):
    """simplify a closed ring (split at the point farthest from the first), snap to the grid, drop repeats"""
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return []
    k = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    simple = rdp(pts[:k + 1], TOL)[:-1] + rdp(pts[k:] + [pts[0]], TOL)[:-1]
    out = []
    for x, y in simple:
        q = [round(x / GRID) * GRID, round(y / GRID) * GRID]
        if not out or q != out[-1]:
            out.append(q)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out + [out[0]] if len(out) >= 3 else []


def main():
    before = after = pts0 = pts1 = 0
    for f in sorted((DATA / "catastro").glob("b_*.json")):
        raw = f.read_text(encoding="utf-8"); before += len(raw)
        data = json.loads(raw)
        if not any("origin" in b for b in data.values()):          # already transformed
            after += len(raw); continue
        out = {}
        for ref, b in data.items():
            parts = []
            for p in b.get("parts", []):
                r = ring([list(map(float, q)) for q in p["pts"]])
                pts0 += len(p["pts"]); pts1 += len(r)
                if not r:                                             # a sliver under the grid: keep a 0,5 m square, for its floors
                    x, y = (round(float(v) / GRID) * GRID for v in p["pts"][0])
                    r = [[x, y], [x + GRID, y], [x + GRID, y + GRID], [x, y + GRID], [x, y]]
                parts.append({"up": p.get("up") or 0, "down": p.get("down") or 0, "pts": r})
            out[ref] = {"use": b.get("use", ""), "dwellings": b.get("dwellings", 0), "units_n": b.get("units_n", 0), "parts": parts}
        txt = json.dumps(out, ensure_ascii=False, separators=(",", ":")); after += len(txt)
        f.write_text(txt, encoding="utf-8")
    print(f"catastro/b_*.json: {before / 1e6:.2f} -> {after / 1e6:.2f} MB, outline points {pts0:,} -> {pts1:,}")
    w = json.loads((DATA / "warehouses.json").read_text(encoding="utf-8"))
    c = {k: w["cols"].index(k) for k in ("built_m2", "ground_m2", "street_m", "open_m")}
    for r in w["rows"]:
        for k in ("built_m2", "ground_m2"):
            if r[c[k]] is not None:
                r[c[k]] = int(round(float(r[c[k]]) / 10) * 10)
        for k in ("street_m", "open_m"):
            if r[c[k]] is not None:
                r[c[k]] = round(float(r[c[k]]) * 2) / 2
    (DATA / "warehouses.json").write_text(json.dumps(w, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"warehouses.json: {len(w['rows']):,} buildings, areas to 10 m², façade lengths to 0,5 m")


if __name__ == "__main__":
    main()
