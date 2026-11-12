"""Nomad - training set for NOMAD's plan AI: real flats as pictures, for a model that fills a flat's space with rooms.

From the plan library (7_floor_plans/code/build_library.py: Swiss Dwellings, CC BY 4.0; build_resplan.py: ResPlan, CC BY 4.0):
15,545 real flats, squared, windows on the front (y = 0, and y = D for flats lit at the back too), their entrance and their
rooms. Each flat, and its mirror, becomes:
  condition  the flat's rectangle W x D, which sides have windows, the entrance point, the number of bedrooms
  answer     a picture, 0,25 m per pixel, every pixel coloured by what it is: outside, wall, living, bedroom 1,
             bedroom, kitchen, bath, hall, storage
Flats bigger than the picture (20 x 20 m) are left out.
Out: 7_floor_plans/output/ai/plan_set.npz (Y pictures + condition table)
Run: python 7_floor_plans/code/plan_data.py
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "7_floor_plans/output/ai"
PX = 0.25                    # metres per pixel
N = 80                       # pixels: 20 x 20 m
CLASSES = ["outside", "wall", "living", "bed_main", "bed", "kitchen", "bath", "hall", "storage"]
CID = dict((k, i) for i, k in enumerate(CLASSES))


def raster(f):
    """The answer picture of one flat (window side at row 0)."""
    im = Image.new("L", (N, N), CID["outside"])
    d = ImageDraw.Draw(im)
    W, D = f["W"], f["D"]
    d.rectangle([0, 0, int(round(W / PX)) - 1, int(round(D / PX)) - 1], fill=CID["wall"])
    for r in sorted(f["rooms"], key=lambda r: -r["area"]):
        d.polygon([(p[0] / PX, p[1] / PX) for p in r["pts"]], fill=CID.get(r["kind"], CID["storage"]))
    return np.array(im, dtype=np.uint8)


def mirror(f):
    W = f["W"]
    g = dict(f)
    g["rooms"] = [dict(r, pts=[[W - p[0], p[1]] for p in r["pts"]]) for r in f["rooms"]]
    if f.get("entrance"):
        g["entrance"] = dict(f["entrance"], at=[W - f["entrance"]["at"][0], f["entrance"]["at"][1]])
    return g


def main():
    lib = json.load(open(ROOT / "7_floor_plans/output/library/library.json")) + json.load(open(ROOT / "7_floor_plans/output/library/library_resplan.json"))
    Y, C = [], []
    for f in lib:
        if f["W"] > N * PX - 0.5 or f["D"] > N * PX - 0.5 or not f.get("entrance") or not f.get("lit"):
            continue
        for g in (f, mirror(f)):
            e = g["entrance"]["at"]
            Y.append(raster(g))
            C.append([g["W"], g["D"], "front" in g["lit"], "back" in g["lit"], e[0], e[1], g["bedrooms"],
                      0 if str(g.get("source", "")).startswith("ResPlan") else 1])
    Y, C = np.stack(Y), np.array(C, dtype=np.float32)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "plan_set.npz", Y=Y, C=C, classes=np.array(CLASSES))
    share = np.bincount(Y.ravel(), minlength=len(CLASSES)) / Y.size
    print("examples", len(Y), "| bedrooms", np.bincount(C[:, 6].astype(int)).tolist(),
          "| pixel share", dict((k, round(float(s), 3)) for k, s in zip(CLASSES, share)))


if __name__ == "__main__":
    main()
