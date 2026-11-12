"""Nomad - Exp 1 on real scans: turn the CubiCasa5K test split into a test set like data/datasets/test_plans.

CubiCasa5K (Kalervo et al. 2019, CC BY-NC-SA 4.0, zenodo.org/records/2613548): 5,000 real Finnish floor-plan
scans, each with a hand-drawn answer (model.svg: rooms, walls, doors, windows as polygons).
Only test.txt is used: our wall model (floorplan-to-3d) was trained on train.txt and tuned on val.txt.

For each test plan:
  image   = F1_scaled.png (the scan, resized by CubiCasa to the SVG's coordinates), copied as <id>.png
  answer  = the flat as NOMAD reads it: all visible indoor rooms ("Space", not Outdoor/Balcony/Terrace/Porch/Garage)
            plus the walls between them (rooms + all walls joined, shrunk by one wall thickness), not the outer
            walls; the largest piece, holes filled. Floors hidden in the SVG (display:none) are skipped.
CubiCasa gives no metric scale, so a nominal 50 px = 1 m is used for both the answer and the reading
("scale given"): overlap and area error are then pure outline accuracy. Façade length is not graded.

Run:  python src/building/make_cubicasa_test.py [--limit N]
Out:  data/datasets/test_plans_cubicasa/<id>.png + truth.json (+ answer previews in _answers/)
"""
import argparse, json, shutil, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "datasets" / "cubicasa5k" / "raw"
OUT = ROOT / "data" / "datasets" / "test_plans_cubicasa"
NS = "{http://www.w3.org/2000/svg}"
PX_PER_M = 50.0                                   # nominal (CubiCasa has no metric scale)
OUTSIDE = frozenset(("Outdoor", "Balcony", "Terrace", "Porch", "Garden", "CarPort", "Garage"))


def _hidden(el):
    st = (el.get("style") or "").replace(" ", "")
    return el.get("display") == "none" or el.get("visibility") == "hidden" or "display:none" in st or "visibility:hidden" in st


def _pts(el):
    if el.tag == NS + "polygon":
        c = [float(v) for v in (el.get("points") or "").replace(",", " ").split()]
        return list(zip(c[0::2], c[1::2]))
    if el.tag == NS + "rect":
        x, y, w, h = (float(el.get(k, 0)) for k in ("x", "y", "width", "height"))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return None


def collect(el, tokens, out):
    """Visible polygons of each kind: the first polygon under a "Space" group is the room outline;
    polygons under "Wall" (but not Door / Window) are walls."""
    if _hidden(el):
        return
    own = el.get("class")
    t = tokens | (frozenset(own.split()) if own else frozenset())
    p = _pts(el)
    if p and len(p) >= 3:
        if "Space" in t and "Wall" not in t and "Door" not in t and "Window" not in t:
            if not (t & OUTSIDE):                          # balconies, terraces, porches, garages are not the flat
                out["space"].append(p)
        elif "Wall" in t and "Door" not in t and "Window" not in t:
            out["wall"].append(p)
    for ch in el:
        collect(ch, t, out)


def answer(svg):
    out = {"space": [], "wall": []}
    collect(ET.parse(svg).getroot(), frozenset(), out)
    spaces = [Polygon(p).buffer(0) for p in out["space"]]
    spaces = [s for s in spaces if s.area > 1]
    if not spaces:
        return None, 0
    walls = [w for w in (Polygon(p).buffer(0) for p in out["wall"]) if w.area > 1]
    thick = float(np.median([2 * w.area / max(w.length, 1e-9) for w in walls])) if walls else 8.0
    # rooms + every wall as one shape, small cracks closed; its outer edge, shrunk by one wall thickness, is the
    # flat without its outer walls (rooms + partitions), which is what NOMAD reads. Thick (log) walls stay joined.
    whole = unary_union(spaces + walls).buffer(2.0, join_style=2).buffer(-2.0, join_style=2)
    parts = list(whole.geoms) if isinstance(whole, MultiPolygon) else [whole]
    big = Polygon(max(parts, key=lambda g: g.area).exterior)
    # keep only what lies next to an indoor room (walls around a porch must not pull the porch back in)
    inner = big.buffer(-thick, join_style=2).intersection(unary_union(spaces).buffer(thick * 1.2, join_style=2))
    if inner.is_empty:
        return None, 0
    if isinstance(inner, MultiPolygon):
        inner = max(inner.geoms, key=lambda g: g.area)
    return Polygon(inner.exterior), len([p for p in parts if p.area > 0.05 * big.area])


def main(limit=None):
    ids = [l.strip().strip("/") for l in (SRC / "cubicasa5k" / "test.txt").read_text().splitlines() if l.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_answers").mkdir(exist_ok=True)
    truth, skipped = {}, []
    for k, rel in enumerate(ids[:limit]):
        d = SRC / "cubicasa5k" / rel
        img, svg = d / "F1_scaled.png", d / "model.svg"
        sid = rel.replace("/", "_")
        if not (img.exists() and svg.exists()):
            skipped.append((sid, "missing files"))
            continue
        try:
            poly, n_parts = answer(svg)
        except Exception as e:                       # broken SVGs exist in CubiCasa
            skipped.append((sid, "svg: %s" % e))
            continue
        if poly is None:
            skipped.append((sid, "no rooms"))
            continue
        shutil.copy2(img, OUT / (sid + ".png"))
        xs, ys = poly.exterior.xy
        y1 = max(ys)
        outline_m = [[round(x / PX_PER_M, 3), round((y1 - y) / PX_PER_M, 3)] for x, y in zip(xs, ys)]
        truth[sid] = {"px_per_m": PX_PER_M, "area_m2": round(poly.area / PX_PER_M ** 2, 1), "facade_m": 0.0,
                      "outline_m": outline_m, "pieces": n_parts, "source": "CubiCasa5K " + rel}
        if k < 12:                                   # a few answers drawn on their scans, to check the alignment
            im = Image.open(img).convert("RGB")
            ImageDraw.Draw(im).line(list(zip(xs, ys)), fill=(220, 40, 40), width=4)
            im.thumbnail((900, 900))
            im.save(OUT / "_answers" / (sid + ".png"))
    json.dump(truth, open(OUT / "truth.json", "w"), indent=1)
    json.dump(skipped, open(OUT / "skipped.json", "w"), indent=1)
    print("test plans:", len(truth), "| skipped:", len(skipped))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    main(ap.parse_args().limit)
