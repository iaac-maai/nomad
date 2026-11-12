"""Nomad - Stage 4: read a floor-plan drawing (PNG / JPG / PDF) into a shell the generator can use.

Steps
  1. AI model (floorplan-to-3d, MIT, trained on CubiCasa5K) labels every pixel wall / door / window / floor.
     Dark pixels also count as wall, so a plan drawn in plain black lines still works.
  2. Outline: flood in from the paper's edge; door gaps are closed with the smallest closing that
     makes an enclosed interior. The interior (rooms) becomes one polygon.
  3. Façade: the outline edges that have window pixels next to them.
  4. Scale (pixels -> metres), in this order: --px-per-m, --facade-m (length of the longest façade),
     --width-m (overall width of the plan); otherwise estimated from wall thickness (outer walls
     taken as 0,30 m) and checked against door widths (taken as 0,85 m).
Output JSON (same format as data/clean/nomad_shells.json, metres, y up) + a preview PNG.

Run with the floorplan-to-3d environment:
  external/floorplan-to-3d/.venv/Scripts/python src/building/read_plan.py plan.png [--facade-m 12] [--out out.json]
"""
import argparse, json, math, sys, types
from pathlib import Path
import numpy as np
import cv2
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
F3D = ROOT / "external" / "floorplan-to-3d"
sys.path.insert(0, str(F3D / "src"))
sys.modules.setdefault("cairosvg", types.ModuleType("cairosvg"))       # SVG rendering not needed
from buildingcv.extract_polygons import PolygonExtractor  # noqa: E402

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
FLOOR, WALL, DOOR, WINDOW = 0, 1, 2, 3
OUTER_WALL_M, DOOR_M = 0.30, 0.85
_EX = None


def load_image(path, dpi=150):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import pymupdf
        pix = pymupdf.open(path)[0].get_pixmap(dpi=dpi)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return Image.open(path).convert("RGB")


def model_mask(img, weights="weights"):
    """Run the segmentation model on the whole image (letterboxed to 512) and scale the mask back.
    weights: "weights" = published floorplan-to-3d; "weights_scans" = fine-tuned on real scans (finetune_scans.py)."""
    global _EX
    if _EX is None:
        _EX = {}
    if weights not in _EX:
        _EX[weights] = PolygonExtractor(F3D / weights, device="cpu")
    ex = _EX[weights]
    H, W = ex.image_size
    s = min(W / img.width, H / img.height)
    w, h = max(1, round(img.width * s)), max(1, round(img.height * s))
    arr = np.asarray(img.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255.0
    t = (torch.from_numpy(arr).permute(2, 0, 1) - torch.tensor(MEAN).view(3, 1, 1)) / torch.tensor(STD).view(3, 1, 1)
    canvas = torch.zeros(3, H, W)
    top, left = (H - h) // 2, (W - w) // 2
    canvas[:, top:top + h, left:left + w] = t
    with torch.no_grad():
        m = ex.model(canvas.unsqueeze(0)).argmax(dim=1).squeeze(0).numpy().astype(np.uint8)
    m = m[top:top + h, left:left + w]
    return cv2.resize(m, (img.width, img.height), interpolation=cv2.INTER_NEAREST)


_MIT = None
MITUNET = ROOT / "external" / "mitunet" / "experiments" / "models" / "mitunet_finetune_a6_mit_b4_tversky_8864_28E.pth"


def mitunet_mask(img):
    """Walls only, from MitUNet (MIT code, weights CC BY-NC, trained on CubiCasa5K). Image stretched to 512 x 512."""
    global _MIT
    if _MIT is None:
        import segmentation_models_pytorch as smp
        aux = smp.Segformer(encoder_name="mit_b4", encoder_weights=None)
        _MIT = smp.Unet(encoder_name="mit_b4", encoder_weights=None, in_channels=3, classes=1, decoder_attention_type="scse")
        _MIT.encoder = aux.encoder
        _MIT.load_state_dict(torch.load(MITUNET, map_location="cpu", weights_only=True))
        _MIT.eval()
    arr = np.asarray(img.resize((512, 512), Image.BILINEAR), dtype=np.float32) / 255.0
    t = (torch.from_numpy(arr).permute(2, 0, 1) - torch.tensor(MEAN).view(3, 1, 1)) / torch.tensor(STD).view(3, 1, 1)
    with torch.no_grad():
        m = (torch.sigmoid(_MIT(t.unsqueeze(0).float())) > 0.5).squeeze().numpy().astype(np.uint8)
    return cv2.resize(m, (img.width, img.height), interpolation=cv2.INTER_NEAREST)


def wall_angle(wall):
    """Main wall direction (degrees, 0-90) from the edges of the wall shapes, weighted by length."""
    cs, _ = cv2.findContours(wall.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    hist = np.zeros(90)
    for c in cs:
        if len(c) < 3:
            continue
        p = cv2.approxPolyDP(c, 2.0, True)[:, 0, :].astype(float)
        for a, b in zip(p, np.roll(p, -1, axis=0)):
            d = b - a
            L = float(np.hypot(*d))
            if L > 8:
                hist[int(math.degrees(math.atan2(d[1], d[0])) % 90) % 90] += L
    hist = np.convolve(np.r_[hist[-2:], hist, hist[:2]], np.ones(5), "valid")
    return float(np.argmax(hist))


def rotate(arr, angle, fill):
    """Rotate an image array by angle degrees around its centre, expanding the canvas."""
    h, w = arr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    c, s = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * s + w * c), int(h * c + w * s)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    flags = cv2.INTER_NEAREST if arr.ndim == 2 else cv2.INTER_LINEAR
    return cv2.warpAffine(arr, M, (nw, nh), flags=flags, borderValue=fill), M


def _inside(barrier, k):
    b = cv2.morphologyEx(barrier, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))) if k > 1 else barrier.copy()
    if k > 1:   # also bridge straight gaps along a wall line (shopfronts, wide entrances): 6x longer, one direction at a time
        L = 6 * k
        b = b | cv2.morphologyEx(barrier, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (L, 3)))
        b = b | cv2.morphologyEx(barrier, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, L)))
    pad = cv2.copyMakeBorder(b, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    ff = pad.copy()
    cv2.floodFill(ff, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 255)
    inside = ((ff != 255) & (pad == 0))[2:-2, 2:-2]
    return inside, (b > 0)


def interior_region(barrier):
    """Rooms = every pixel not reachable from the paper edge. Gaps in the outer wall (doors, window
    openings) are closed with the smallest closing after which the enclosed area stops growing:
    smaller leaves leaks, larger starts filling notches of the outline."""
    ks = (1, 5, 9, 15, 21, 31, 45, 61, 81, 101)
    areas = []
    for k in ks:
        inside, _ = _inside(barrier, k)
        areas.append((int(inside.sum()), k, inside))
    for i in range(1, len(areas) - 1):
        a0, a1 = areas[i][0], areas[i + 1][0]
        if a0 > 0 and a1 <= a0 * 1.04 and a0 > 0.5 * max(a for a, _, _ in areas):
            return areas[i][2], areas[i][1]
    best = max(areas, key=lambda x: x[0])
    return best[2], best[1]


def estimate_scale(wall, doors_px):
    """px per metre from outer-wall thickness (0,30 m); door widths (0,85 m) as a second opinion."""
    dist = cv2.distanceTransform(wall.astype(np.uint8), cv2.DIST_L2, 3)
    thick = dist[dist > 0]
    est_wall = (2.0 * float(np.percentile(thick, 97)) / OUTER_WALL_M) if thick.size else None
    est_door = (float(np.median(doors_px)) / DOOR_M) if len(doors_px) >= 2 else None
    if est_wall and est_door and 0.6 < est_wall / est_door < 1.6:
        return (est_wall + est_door) / 2.0, "wall thickness + door widths"
    if est_door:
        return est_door, "door widths (0,85 m)"
    if est_wall:
        return est_wall, "outer wall thickness (0,30 m)"
    return 50.0, "unknown: assumed 50 px per metre"


def read(path, px_per_m=None, facade_m=None, width_m=None, height_m=2.8, preview=None, walls="f3d"):
    """walls: "f3d" = floorplan-to-3d model + dark pixels (default); "f3d_only" = model alone;
    "mitunet" = MitUNet walls + dark pixels (openings still from floorplan-to-3d); "dark" = dark pixels alone;
    "scans" / "scans_only" = like f3d / f3d_only with the model fine-tuned on real scans."""
    img0 = load_image(path)
    m0 = model_mask(img0, "weights_scans" if walls.startswith("scans") else "weights")
    if walls == "mitunet":
        m0 = np.where(mitunet_mask(img0) == 1, WALL, np.where(m0 == WALL, FLOOR, m0)).astype(np.uint8)
    elif walls == "dark":
        m0 = np.where(m0 == WALL, FLOOR, m0).astype(np.uint8)
    # straighten: rotate so the main walls run horizontal/vertical; results are rotated back at the end
    gray0 = np.asarray(img0.convert("L"))
    ang = wall_angle(((m0 == WALL) | (gray0 < 110)).astype(np.uint8))
    rot = ang if ang <= 45 else ang - 90
    g_arr, Mrot = rotate(np.asarray(img0), rot, (255, 255, 255))
    img = Image.fromarray(g_arr)
    m, _ = rotate(m0, rot, FLOOR)
    Minv = cv2.invertAffineTransform(Mrot)
    gray = np.asarray(img.convert("L"))
    dark = (gray < 110) if walls not in ("f3d_only", "scans_only") else np.zeros_like(gray, dtype=bool)
    wall = ((m == WALL) | dark).astype(np.uint8)
    window = (m == WINDOW).astype(np.uint8)
    door = (m == DOOR).astype(np.uint8)
    opening = ((window | door) > 0).astype(np.uint8)      # the model often calls windows "door": both are openings
    barrier = ((wall | opening) > 0).astype(np.uint8) * 255
    rooms, closing = interior_region(barrier)
    # one solid flat: rooms plus the partitions between them (but not the outer walls)
    solid = cv2.morphologyEx(rooms.astype(np.uint8) * 255, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    cs, _ = cv2.findContours(solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return {"ok": False, "reason": "no enclosed space found in the drawing"}
    c = max(cs, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    poly = cv2.approxPolyDP(c, max(2.0, 0.006 * peri), True)[:, 0, :].astype(float)

    # doors: widths in px from the model's door blobs
    n, lab, stats, _ = cv2.connectedComponentsWithStats(door, 8)
    doors_px = [max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 15]

    # scale
    edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    elen = [float(np.hypot(*(b - a))) for a, b in edges]
    # façade edges: walk along each outline edge just outside it, inside the outer wall.
    # A stretch where that wall is a window/door, or missing (a shopfront gap), is an opening.
    cnt = poly.astype(np.float32).reshape(-1, 1, 2)
    Hh, Ww = wall.shape
    win_near, open_len = [], []
    for (a, b), L in zip(edges, elen):
        if L < 4:
            win_near.append(False)
            open_len.append(0.0)
            continue
        d = (b - a) / L
        nrm = np.array([-d[1], d[0]])
        mid = (a + b) / 2
        if cv2.pointPolygonTest(cnt, (float(mid[0] + 3 * nrm[0]), float(mid[1] + 3 * nrm[1])), False) > 0:
            nrm = -nrm                                    # make the normal point outside
        n_open = 0
        steps = int(L // 2)
        for i in range(steps):
            p = a + d * (2 * i + 1)
            hit_open = False
            solid = 0
            for off in (3, 6, 9):
                x, y = int(p[0] + nrm[0] * off), int(p[1] + nrm[1] * off)
                if 0 <= x < Ww and 0 <= y < Hh:
                    if opening[y, x]:
                        hit_open = True
                    solid += int(wall[y, x])
            if hit_open or solid == 0:
                n_open += 1
        frac = n_open / max(steps, 1)
        open_len.append(frac * L)
        win_near.append(frac > 0.15)
    method = None
    if px_per_m:
        method = "given (%.1f px per m)" % px_per_m
    elif facade_m and any(win_near):
        px_per_m = max(L for L, w in zip(elen, win_near) if w) / facade_m
        method = "longest façade = %.2f m" % facade_m
    elif width_m:
        px_per_m = (poly[:, 0].max() - poly[:, 0].min()) / width_m
        method = "overall width = %.2f m" % width_m
    else:
        px_per_m, method = estimate_scale(wall, doors_px)
        method = "estimated from " + method

    k = 1.0 / px_per_m
    back = lambda p: Minv @ np.array([p[0], p[1], 1.0])                                  # to the original image
    orig = np.array([back(p) for p in poly])
    x0, y1 = orig[:, 0].min(), orig[:, 1].max()
    to_m = lambda p: [round((back(p)[0] - x0) * k, 3), round((y1 - back(p)[1]) * k, 3)]   # metres, y up
    outline = [to_m(p) for p in poly] + [to_m(poly[0])]
    facade = [[to_m(a), to_m(b)] for (a, b), w in zip(edges, win_near) if w]
    area = cv2.contourArea(poly.astype(np.float32)) * k * k
    res = {"ok": True, "source": str(path), "scale_px_per_m": round(px_per_m, 2), "scale_method": method,
           "area_m2": round(area, 1), "facade_m": round(sum(L for L, w in zip(elen, win_near) if w) * k, 1),
           "windows_found": int(cv2.connectedComponents(window)[0] - 1), "doors_found": len(doors_px),
           "height_m": height_m, "outline": outline, "facade": facade, "door_closing_px": closing,
           "rotation_deg": round(rot, 1), "origin_px": [round(float(x0), 1), round(float(y1), 1)],
           "image_px": [img0.width, img0.height]}
    if preview:
        over = np.asarray(img).copy()
        over[m == WINDOW] = (40, 120, 215)
        over[m == DOOR] = (230, 160, 40)
        cv2.polylines(over, [poly.astype(np.int32)], True, (220, 40, 40), 3)
        for (a, b), w in zip(edges, win_near):
            if w:
                cv2.line(over, tuple(map(int, a)), tuple(map(int, b)), (30, 160, 70), 6)
        Image.fromarray(over).save(preview)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("--px-per-m", type=float)
    ap.add_argument("--facade-m", type=float, help="length of the longest street façade in metres")
    ap.add_argument("--width-m", type=float, help="overall width of the plan in metres")
    ap.add_argument("--height-m", type=float, default=2.8)
    ap.add_argument("--out")
    ap.add_argument("--preview")
    a = ap.parse_args()
    res = read(a.image, a.px_per_m, a.facade_m, a.width_m, a.height_m, a.preview)
    txt = json.dumps(res)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("outline", "facade")}))


if __name__ == "__main__":
    main()
