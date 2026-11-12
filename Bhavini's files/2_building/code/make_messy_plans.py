"""Nomad - make "messy" copies of the test plans, closer to a real scanned drawing.

Each clean test plan (7_floor_plans/input/datasets/test_plans/<id>.png) gets, with a fixed random seed:
  room-name and area text, dimension lines with ticks and numbers outside the plan,
  thin furniture outlines inside, a grey hatch band, scanner noise and a low-quality JPEG save.
The truth is the same as the clean plan (same scale, same outline), so the reader can be graded on both.
Outputs: 7_floor_plans/input/datasets/test_plans_messy/<id>.jpg (+ a copy of truth.json)
Run: .venv/Scripts/python 2_building/code/make_messy_plans.py [limit]
"""
import json, random, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "7_floor_plans/input/datasets/test_plans"
OUT = ROOT / "7_floor_plans/input/datasets/test_plans_messy"
WORDS = ["SALA", "DORM.", "COCINA", "BAÑO", "PASO", "ALMACÉN", "TIENDA", "ASEO", "LOCAL", "ESTAR"]


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def mess(img, rng):
    W, H = img.size
    arr = np.asarray(img.convert("L"))
    ys, xs = np.where(arr < 110)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    d = ImageDraw.Draw(img)
    # dimension lines: one above, one left, with ticks and a number
    f = font(13)
    dy = max(8, y0 - 22)
    d.line([(x0, dy), (x1, dy)], fill=0, width=1)
    for x in (x0, x1):
        d.line([(x - 5, dy + 5), (x + 5, dy - 5)], fill=0, width=1)
    d.text(((x0 + x1) / 2 - 15, dy - 16), f"{(x1 - x0) / 40:.2f}", fill=0, font=f)
    dx = max(8, x0 - 22)
    d.line([(dx, y0), (dx, y1)], fill=0, width=1)
    for y in (y0, y1):
        d.line([(dx - 5, y + 5), (dx + 5, y - 5)], fill=0, width=1)
    d.text((dx + 3, (y0 + y1) / 2), f"{(y1 - y0) / 40:.2f}", fill=0, font=f)
    # room labels + furniture inside the plan, only on white floor
    for _ in range(rng.randint(4, 9)):
        for _try in range(30):
            x, y = rng.randint(x0, x1), rng.randint(y0, y1)
            if arr[max(0, y - 12):y + 12, max(0, x - 30):x + 30].min() > 200:
                break
        else:
            continue
        if rng.random() < 0.5:
            d.text((x - 25, y - 8), rng.choice(WORDS), fill=0, font=font(14))
            d.text((x - 20, y + 8), f"{rng.uniform(4, 25):.2f} m²", fill=0, font=font(11))
        else:
            w, h = rng.randint(15, 40), rng.randint(15, 40)
            if rng.random() < 0.5:
                d.rectangle([x - w // 2, y - h // 2, x + w // 2, y + h // 2], outline=0, width=1)
            else:
                d.ellipse([x - w // 2, y - w // 2, x + w // 2, y + w // 2], outline=0, width=1)
    # grey hatch band across a corner (like a section fill or shading)
    hx = rng.randint(x0, max(x0 + 1, x1 - 60))
    for k in range(0, 60, 6):
        d.line([(hx + k, y1 + 8), (hx + k + 20, y1 + 28)], fill=(150, 150, 150), width=1)
    # scan: blur, noise, low-quality JPEG
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(img).astype(np.float32)
    a += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 9, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main(limit=None):
    OUT.mkdir(parents=True, exist_ok=True)
    truth = json.load(open(SRC / "truth.json"))
    ids = list(truth)[:limit]
    for i, sid in enumerate(ids):
        rng = random.Random(int(sid))
        img = mess(Image.open(SRC / f"{sid}.png").convert("RGB"), rng)
        img.save(OUT / f"{sid}.jpg", quality=45)
    json.dump({k: truth[k] for k in ids}, open(OUT / "truth.json", "w"), indent=1)
    print(f"{len(ids)} messy plans in {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
