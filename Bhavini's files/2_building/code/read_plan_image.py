"""Nomad - Stage 4 (first test): read a floor-plan IMAGE (png/jpg) into walls, doors and windows.

Uses the floorplan-to-3d model (github.com/Yytsi/floorplan-to-3d, MIT; weights from Hugging Face
Yytsi/floorplan-to-3d-walls, MIT; trained on CubiCasa5K). Their code reads SVGs; this adapter feeds a
normal image with the same preprocessing (letterbox to 512x512, ImageNet normalisation).
Run with that project's environment:
  tools/borrowed_code/floorplan-to-3d/.venv/Scripts/python 2_building/code/read_plan_image.py <image> [<image> ...]
Writes, into 2_building/output/plan_reading/: <name>.plan.json (polygons in pixels) and <name>.preview.png (image | mask).
"""
import json, sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
F3D = ROOT / "tools/borrowed_code/floorplan-to-3d"
sys.path.insert(0, str(F3D / "src"))
import types  # noqa: E402
sys.modules.setdefault("cairosvg", types.ModuleType("cairosvg"))   # SVG rendering not needed for images
from buildingcv.extract_polygons import PolygonExtractor, mask_to_polygons, _colorize_mask  # noqa: E402

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
OUT = ROOT / "2_building/output/plan_reading"


def image_tensor(path, size):
    H, W = size
    img = Image.open(path).convert("RGB")
    scale = min(W / img.width, H / img.height)
    w, h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    arr = np.asarray(img.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255.0
    t = (torch.from_numpy(arr).permute(2, 0, 1) - torch.tensor(MEAN).view(3, 1, 1)) / torch.tensor(STD).view(3, 1, 1)
    canvas = torch.zeros(3, H, W)
    top, left = (H - h) // 2, (W - w) // 2
    canvas[:, top:top + h, left:left + w] = t
    return canvas, (left, top, w, h), img


def main(paths):
    OUT.mkdir(parents=True, exist_ok=True)
    ex = PolygonExtractor(F3D / "weights", device="cpu")
    for p in paths:
        p = Path(p)
        t, (left, top, w, h), img = image_tensor(p, ex.image_size)
        with torch.no_grad():
            mask = ex.model(t.unsqueeze(0)).argmax(dim=1).squeeze(0).numpy().astype(np.uint8)
        polys = mask_to_polygons(mask)
        counts = {k: len(v) for k, v in polys.items()}
        share = {name: round(float((mask == i).mean()), 3) for i, name in enumerate(["floor", "wall", "door", "window"])}
        (OUT / f"{p.stem}.plan.json").write_text(json.dumps({"source": str(p), "content_rect": [left, top, w, h],
                                                             "polygons": polys}), encoding="utf-8")
        prev = Image.new("RGB", (mask.shape[1] * 2, mask.shape[0]), "white")
        prev.paste(img.resize((w, h)), (left, top))
        prev.paste(_colorize_mask(mask), (mask.shape[1], 0))
        prev.save(OUT / f"{p.stem}.preview.png")
        print(f"{p.name}: polygons {counts} | pixel share {share}")


if __name__ == "__main__":
    main(sys.argv[1:])
