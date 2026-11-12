"""NOMAD - facade: one file that reads a building's facade from a photo and draws it (10 Nov 2026 method,
docs/facade_workflow.md). Read it top to bottom. It runs in five steps:

  STEP 1  STRAIGHTEN  the photo: lens bend, vertical and horizontal vanishing points, turned to face the facade
                      -> results/facade/<ref>/straight.jpg, straight.json
  STEP 2  HEIGHTS     (helpers) street level and cornice from ICGC LiDAR, measured where the facade is
  STEP 3  READ        edges, windows / doors / shopfronts / balconies / trees (Grounding DINO), floor lines
                      -> facade.json, facade_crop.jpg, facade_photo_m.jpg, check_PRIVATE.jpg
  STEP 4  DRAW        the facade rules: one size per floor type, symmetry as a test, balconies, ground-floor rhythm
                      -> openings.json, elevation.png
  STEP 5  EXPORT      every APPROVED facade, for the app -> site/data/facades.json (runs by itself after step 4)
  APPROVE (checkpoint) the user looks at elevation.png and approves: facade.py <ref> approve -> the app, 3D and plans

Steps 1-3:       tools/train-venv/Scripts/python.exe src/facade/facade.py <ref> straighten read   (GPU, OpenCV, Grounding DINO)
Steps 4-5:       .venv/Scripts/python src/facade/facade.py <ref> draw export                      (matplotlib)
(<ref> = 14-character cadastral reference; default 9331705DF2893A, Av. Diagonal 413.)

LICENCE: the photo comes from the Catastro facade photo service (Sede Electrónica del Catastro). The Sede legal notice
allows download and PRIVATE use only, so the photo, the check pictures AND the results made from it stay on this computer;
they are not published or shared (see docs/licences.md). The code holds no Catastro data.
Detector: Grounding DINO base (IDEA-Research, Apache-2.0). LiDAR: ICGC (CC BY 4.0). OpenCV (Apache-2.0).
Drawing it in Rhino: src/rhino/record_facade.py (runs inside Rhino, so it stays a separate file).
"""
import csv
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
try:                                   # steps 1 and 3 need OpenCV and Pillow (tools/train-venv); steps 4-5 run without them
    import cv2
    from PIL import Image, ImageDraw
except ImportError:
    cv2 = Image = ImageDraw = None

ROOT = Path(__file__).resolve().parents[2]
REF = sys.argv[1] if len(sys.argv) > 1 and len(sys.argv[1]) == 14 else "9331705DF2893A"
PHOTO = ROOT / "data/barcelona/catastro/facades" / f"{REF}.jpg"
D = ROOT / "results/facade" / REF                    # every output of this building


# ======================================================================================================================
# STEP 1  STRAIGHTEN the photo automatically
#   1. Find straight line pieces in the photo (OpenCV line segment detector).
#   2. Lens bend: try a range of lens corrections (one-number "division" model) and keep the one where the near-vertical
#      pieces best meet in ONE vanishing point (a bent lens makes long verticals curve, so they miss it).
#   3. Vanishing points: verticals (up) and facade horizontals (along the street).
#   4. From those two points the camera's focal length follows (they are at right angles in the real world); the photo
#      is then turned so the facade faces us: verticals vertical and parallel, horizontals horizontal, true proportions.
#   Frame: the street level across the photo (bottom row) up to the top of the photo's centre line.
# ======================================================================================================================

rng = np.random.default_rng(0)


def segments(gray):
    lsd = cv2.createLineSegmentDetector()
    s = lsd.detect(gray)[0].reshape(-1, 4)
    L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
    return s[L > 20]


def norm_pts(p, c, S):
    return (p - c) / S


def undistort(p, k):
    """division model: undistorted = distorted / (1 + k r^2), r in normalised units."""
    r2 = (p ** 2).sum(-1, keepdims=True)
    return p / (1 + k * r2)


def distort(u, k):
    """inverse of undistort (solve r_d from r_u)."""
    ru = np.sqrt((u ** 2).sum(-1, keepdims=True)) + 1e-12
    if abs(k) < 1e-9:
        return u
    disc = np.clip(1 - 4 * k * ru ** 2, 0, None)
    rd = (1 - np.sqrt(disc)) / (2 * k * ru)
    return u * rd / ru


def lines_of(seg):
    a = np.c_[seg[:, :2], np.ones(len(seg))]; b = np.c_[seg[:, 2:], np.ones(len(seg))]
    l = np.cross(a, b)
    return l / np.linalg.norm(l[:, :2], axis=1, keepdims=True)


def vp(seg, w, iters=400, tol=0.004):
    """vanishing point by RANSAC over pairs, refined by least squares on the inliers."""
    l = lines_of(seg)
    best, bi = None, None
    for _ in range(iters):
        i, j = rng.choice(len(l), 2, replace=False, p=w / w.sum())
        v = np.cross(l[i], l[j])
        if abs(v).max() < 1e-12:
            continue
        v = v / np.linalg.norm(v)
        d = abs(l @ v) / max(abs(v[2]), 1e-9) if abs(v[2]) > 1e-3 else abs(l[:, :2] @ v[:2] / np.linalg.norm(v[:2]))
        inl = d < tol if abs(v[2]) > 1e-3 else d < 0.02
        score = (w * inl).sum()
        if best is None or score > best:
            best, bi = score, inl
    A = (l[bi] * np.sqrt(w[bi])[:, None])
    v = np.linalg.svd(A)[2][-1]
    res = abs(l[bi] @ v)
    return v / np.linalg.norm(v), bi, float((w[bi] * res ** 2).sum() / w[bi].sum()), float(w[bi].sum() / w.sum())


def angle_sel(seg, vertical):
    a = np.degrees(np.arctan2(seg[:, 3] - seg[:, 1], seg[:, 2] - seg[:, 0])) % 180
    return (abs(a - 90) < 25) if vertical else ((a < 25) | (a > 155))


def straighten():
    D.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(PHOTO)); H0, W0 = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    seg = segments(gray)
    c, S = np.array([W0 / 2, H0 / 2]), np.hypot(W0, H0) / 2
    P = norm_pts(seg.reshape(-1, 2), c, S).reshape(-1, 4)
    L = np.hypot(P[:, 2] - P[:, 0], P[:, 3] - P[:, 1])

    # lens bend: the k that makes the verticals meet best
    tries = []
    for k in np.linspace(-0.45, 0.25, 29):
        U = undistort(P.reshape(-1, 2), k).reshape(-1, 4)
        sel = angle_sel(U, True)
        _, inl, res, share = vp(U[sel], L[sel], iters=250)
        tries.append((res / max(share, 1e-3), k))
    k = min(tries)[1]
    U = undistort(P.reshape(-1, 2), k).reshape(-1, 4)

    # vanishing points
    sv, sh = angle_sel(U, True), angle_sel(U, False)
    v, _, _, vshare = vp(U[sv], L[sv])
    h, _, _, hshare = vp(U[sh], L[sh])

    # focal length from the two right-angled directions, then turn the camera to face the facade
    vv = v[:2] / v[2] if abs(v[2]) > 1e-9 else None
    hh = h[:2] / h[2] if abs(h[2]) > 1e-9 else None
    f2 = -(vv @ hh) if (vv is not None and hh is not None) else -1
    f = float(np.sqrt(f2)) if f2 > 0.05 else 1.0                # fallback: about 90 degrees wide
    K = np.diag([f, f, 1.0]); Ki = np.linalg.inv(K)
    dv = Ki @ v; dv /= np.linalg.norm(dv)
    if dv[1] > 0:                                             # point "up" (image y grows downwards)
        dv = -dv
    dh = Ki @ h; dh /= np.linalg.norm(dh)
    if dh[0] < 0:
        dh = -dh
    dh = dh - (dh @ dv) * dv; dh /= np.linalg.norm(dh)
    n = np.cross(dh, -dv)
    R = np.stack([dh, -dv, n])                                # new x = along street, new y = down, z = into the facade
    Hn = K @ R @ Ki                                           # normalised undistorted -> frontal (normalised)

    # output frame: where the photo's own pixels land (the sky corners would stretch to infinity)
    def fwd(pts):
        r = (Hn @ np.c_[undistort(norm_pts(np.array(pts, float), c, S), k), np.ones(len(pts))].T).T
        return r[:, :2] / r[:, 2:]
    bot = fwd([(x, H0 - 1) for x in np.linspace(0.02 * W0, 0.98 * W0, 30)])
    top = fwd([(W0 / 2, 0.02 * H0)])
    lo = np.array([bot[:, 0].min(), top[0, 1]]); hi = np.array([bot[:, 0].max(), bot[:, 1].max()])
    scale = 1500 / max(hi - lo)
    Wo, Ho = int((hi - lo)[0] * scale), int((hi - lo)[1] * scale)
    ox, oy = np.meshgrid(np.arange(Wo), np.arange(Ho))
    Q = np.c_[ox.ravel() / scale + lo[0], oy.ravel() / scale + lo[1], np.ones(ox.size)]
    pu = (np.linalg.inv(Hn) @ Q.T).T
    pu = pu[:, :2] / pu[:, 2:]
    pd = distort(pu, k) * S + c
    mx, my = pd[:, 0].reshape(Ho, Wo).astype(np.float32), pd[:, 1].reshape(Ho, Wo).astype(np.float32)
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(244, 244, 241))
    cv2.imwrite(str(D / "straight.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 88])
    info = {"ref": REF, "lens_k": round(float(k), 3), "focal_norm": round(f, 3), "vertical_share": round(vshare, 2),
            "horizontal_share": round(hshare, 2), "size": [Wo, Ho], "map": {"lo": lo.tolist(), "scale": scale, "c": c.tolist(), "S": S},
            "H": Hn.tolist()}
    json.dump(info, open(D / "straight.json", "w"), indent=1)
    print(json.dumps({k_: info[k_] for k_ in ("lens_k", "focal_norm", "vertical_share", "horizontal_share", "size")}))


# ======================================================================================================================
# STEP 2  HEIGHTS from ICGC LiDAR (CC BY 4.0), measured where the facade is, not over the whole plot
#   street level = LiDAR ground on the pavement strip 1-4 m in front of the facade line
#   front top    = LiDAR top-of-building in the strip 0,5-2,5 m behind the facade line (the front wall's top: cornice /
#                  parapet); median, plus the 90th percentile along the facade (ornaments, pediment)
#   deep roof    = the same 6-12 m behind the line, for comparison (setbacks, attics, rooftop huts)
#   Grids: data/lidar/grid/<e><n>.npz, 1 m cells, 'top' and 'gnd' (from src/building/lidar_heights.py).
# ======================================================================================================================

GRID = ROOT / "data/lidar/grid"
_cache = {}


def _cell(x, y, key):
    e, n = int(x // 1000), int(y // 1000)
    k = (e, n)
    if k not in _cache:
        f = GRID / ("%03d%03d.npz" % (e, n - 4000))
        _cache[k] = np.load(f) if f.exists() else None
    d = _cache[k]
    if d is None:
        return np.nan
    return float(d[key][int(x - e * 1000), int(y - n * 1000)])


def strip(a, c, foot, s0, s1, key, step=0.5, end=1.0):
    """values of grid `key` in a strip parallel to the facade line a-c, s0..s1 m from it (+ = street side)."""
    L = math.dist(a, c)
    ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
    nx, ny = -uy, ux
    cx, cy = np.mean([p[0] for p in foot]), np.mean([p[1] for p in foot])
    mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
    if (cx - mx) * nx + (cy - my) * ny > 0:              # normal must point away from the building: to the street
        nx, ny = -nx, -ny
    out = []
    for t in np.arange(end, L - end + 1e-6, step):
        for s in np.arange(s0, s1 + 1e-6, step):
            v = _cell(a[0] + ux * t + nx * s, a[1] + uy * t + ny * s, key)
            if not math.isnan(v):
                out.append((t, v))
    return out


def front_heights(a, c, foot):
    street = [v for _, v in strip(a, c, foot, 1.0, 4.0, "gnd")]
    front = strip(a, c, foot, -2.5, -0.5, "top")
    deep = [v for _, v in strip(a, c, foot, -12.0, -6.0, "top")]
    if len(street) < 5 or len(front) < 5:
        return None
    z0 = float(np.median(street))
    fv = np.array([v for _, v in front]) - z0
    prof = {}                                            # along the facade: the top of each 1 m slice
    for t, v in front:
        k = int(t)
        prof[k] = max(prof.get(k, -1e9), v - z0)
    return {"street_z": round(z0, 2), "street_spread": round(float(np.percentile(street, 90) - np.percentile(street, 10)), 2),
            "front_top_m": round(float(np.median(fv)), 2), "front_p90_m": round(float(np.percentile(fv, 90)), 2),
            "front_p10_m": round(float(np.percentile(fv, 10)), 2),
            "deep_roof_m": round(float(np.median(deep) - z0), 2) if deep else None,
            "along": [round(prof[k], 1) for k in sorted(prof)]}


# ======================================================================================================================
# STEP 3  READ the straightened photo
#   Detector: Grounding DINO base, asked in words for each element, on the whole facade and in enlarged overlapping
#   tiles (small windows are seen), then duplicates cleaned. Edges: of the long vertical lines either side, the pair whose
#   width fits the Catastro street front at the LiDAR height scale. Floors: lines from the facade's horizontal edges,
#   moved onto balcony bottoms (+0,15 m slab), above the heads below (+0,30 m), then the rule: the ground floor has its
#   own height, every floor above one same height (least squares). Trees are asked for and marked "hidden".
# ======================================================================================================================

MODEL = "IDEA-Research/grounding-dino-base"
ASK = {"window": "window. balcony door. french window", "door": "entrance door", "shopfront": "shop front. arched shop window",
       "balcony": "balcony railing"}
ASK_GROUND = {"shopfront": "shop front. shop window. arched opening", "door": "entrance door. doorway"}   # 2nd look at the ground floor
TILES = (3, 3)        # the photo is also read in overlapping tiles, enlarged, so small windows are seen
COL_CHECK = {"window": (44, 93, 143), "door": (201, 138, 43), "shopfront": (63, 143, 90), "balcony": (196, 71, 58)}
OFFX = 0              # px from the true left edge to the crop
_M = {}


def _model():
    if not _M:
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        _M.update(dev=dev, proc=AutoProcessor.from_pretrained(MODEL),
                  model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL).to(dev), torch=torch)
    return _M["dev"], _M["proc"], _M["model"]


def ask(im, words, threshold=0.25):
    """One question about one picture: boxes and scores (picture pixels)."""
    dev, proc, model = _model()
    inp = proc(images=im, text=words + ".", return_tensors="pt").to(dev)
    with _M["torch"].no_grad():
        out = model(**inp)
    r = proc.post_process_grounded_object_detection(out, inp.input_ids, threshold=threshold, text_threshold=threshold - 0.05,
                                                    target_sizes=[im.size[::-1]])[0]
    return list(zip(r["boxes"].tolist(), r["scores"].tolist()))


def detect(im, words=None):
    """Every element asked for in `words` (default ASK), on the whole picture and in enlarged overlapping tiles."""
    words = words or ASK
    dev, proc, model = _model()
    W, H = im.size
    views = [(0, 0, W, H)]
    tw, th = W / (TILES[0] - 0.5), H / (TILES[1] - 0.5)  # tiles overlap by half
    for i in range(TILES[0]):
        for j in range(TILES[1]):
            x0, y0 = min(i * tw / 1.5 * 1.0, W - tw), min(j * th / 1.5, H - th)
            views.append((int(x0), int(y0), int(x0 + tw), int(y0 + th)))
    found = []
    for (vx0, vy0, vx1, vy1) in views:
        crop = im.crop((vx0, vy0, vx1, vy1))
        k = 2 if (vx1 - vx0) < W else 1
        crop = crop.resize((crop.width * k, crop.height * k))
        for kind, w in words.items():                    # one question per element: cleaner labels
            inp = proc(images=crop, text=w + ".", return_tensors="pt").to(dev)
            with _M["torch"].no_grad():
                out = model(**inp)
            r = proc.post_process_grounded_object_detection(out, inp.input_ids, threshold=0.25, text_threshold=0.20,
                                                            target_sizes=[crop.size[::-1]])[0]
            for box, s in zip(r["boxes"].tolist(), r["scores"].tolist()):
                b = [box[0] / k + vx0, box[1] / k + vy0, box[2] / k + vx0, box[3] / k + vy0]
                edge = min(b[0] - vx0, vx1 - b[2], b[1] - vy0, vy1 - b[3])
                if k > 1 and edge < 3:
                    continue                             # cut by the tile edge: another tile sees it whole
                found.append({"kind": kind, "score": round(s, 2), "box": [round(v, 1) for v in b]})
    return found


def inside(poly, x, y):
    c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def _share(a, b):
    """share of box a inside box b."""
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / ((a[2] - a[0]) * (a[3] - a[1]) + 1e-9)


def clean(found, corners):
    """Duplicates out: keep the best of overlapping boxes, drop boxes outside the facade (corners) or as big as the
    whole building, and a window inside a bigger window."""
    keep = []
    for f in sorted(found, key=lambda f: -f["score"]):
        x0, y0, x1, y1 = f["box"]
        if not inside(corners, (x0 + x1) / 2, (y0 + y1) / 2):
            continue                                     # neighbours' facades
        if (x1 - x0) * (y1 - y0) > 0.08 * 1024 * 768:
            continue                                     # "the whole building" boxes
        if any(iou(f["box"], k["box"]) > 0.5 and (k["kind"] == f["kind"] or {k["kind"], f["kind"]} <= {"window", "door", "shopfront"})
               for k in keep):
            continue
        keep.append(f)
    OPEN = {"window", "door", "shopfront"}
    out = []
    for f in keep:                                       # a window inside a window: keep the outer one
        if f["kind"] in OPEN and any(g is not f and g["kind"] in OPEN and _share(f["box"], g["box"]) > 0.6
                                     and (g["box"][2] - g["box"][0]) * (g["box"][3] - g["box"][1]) > (f["box"][2] - f["box"][0]) * (f["box"][3] - f["box"][1])
                                     for g in keep):
            continue
        out.append(f)
    return out


def building(ref):
    """The building from the Catastro footprint and NOMAD's heights: candidate street fronts (runs of nearly straight
    footprint edges >= 6 m; the photo picks one later), floors, LiDAR roof."""
    h = next(r for r in csv.DictReader(open(ROOT / "results/heights/heights.csv", encoding="utf-8")) if r["ref"] == ref)
    p = json.load(open(ROOT / "site/data/premises.json", encoding="utf-8"))
    row = next(r for r in p["rows"] if r[6] == ref)
    b = json.load(gzip.open(ROOT / "data/barcelona/catastro/buildings.json.gz", "rt", encoding="utf-8"))[ref]
    area = lambda r: abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:]))) / 2
    ring = max((poly[0] for poly in b["foot"]), key=area)           # the main piece (a footprint can have small extra pieces)
    edges = list(zip(ring, ring[1:]))
    ang = lambda e: math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0])
    runs, i = [], 0
    while i < len(edges):
        j = i
        while j + 1 < len(edges) and abs(math.remainder(ang(edges[j + 1]) - ang(edges[i]), 2 * math.pi)) < math.radians(12):
            j += 1
        a, c = edges[i][0], edges[j][1]
        if math.dist(a, c) >= 6:
            runs.append((round(math.dist(a, c), 2), a, c))
        i = j + 1
    a, c = max(runs)[1:]
    return {"address": f"{row[2].title()} {row[3]}", "front_m": round(math.dist(a, c), 2), "front": [a, c], "runs": runs,
            "floors": int(h["floors"]), "roof_m": float(h["roof_p75"]), "roof_p50": float(h["roof_p50"]),
            "foot": ring}


def edges_of(img):
    """Candidate building edges (long vertical lines left and right of the centre, with their strength) and the
    roofline (median first non-sky row between the strongest pair)."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    s = cv2.createLineSegmentDetector().detect(g)[0].reshape(-1, 4)
    v = s[(abs(s[:, 0] - s[:, 2]) < 4) & (abs(s[:, 1] - s[:, 3]) > 40)]
    acc = {}
    for x, l in zip(np.round((v[:, 0] + v[:, 2]) / 2 / 5) * 5, abs(v[:, 1] - v[:, 3])):
        acc[float(x)] = acc.get(float(x), 0) + float(l)
    L = {x: a for x, a in acc.items() if x < 0.35 * w}
    R = {x: a for x, a in acc.items() if x > 0.65 * w}
    left, right = max(L, key=L.get), max(R, key=R.get)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sky = (hsv[..., 2] > 225) & (hsv[..., 1] < 30)
    tops = []
    for x in range(int(left) + 10, int(right) - 10, 3):
        run = np.convolve((~sky[:, x]).astype(int), np.ones(25, int), "valid")
        if run.max() >= 25:
            tops.append(int(np.argmax(run >= 25)))
    Lc = sorted(x for x, a in L.items() if a >= 0.25 * L[left])     # candidates: at least a quarter as strong as the strongest
    Rc = sorted(x for x, a in R.items() if a >= 0.25 * R[right])
    return Lc, Rc, int(left), int(right), int(np.median(tops))


def floor_lines(gray, base, top, sz, n):
    """Floor lines from the facade's own horizontal edges (slabs, balcony edges), in metres via the LiDAR scale.
    Model (our assumption, typical of Barcelona blocks): ground floor g, first floor t, then n-2 floors of equal
    height s; the top floor must keep >= 2,6 m below the roof. Each line is then moved to the strongest edge within 0,4 m."""
    e = (np.abs(cv2.Sobel(gray.astype(float), cv2.CV_64F, 0, 1, ksize=3)) > 60).mean(1)
    prof = np.convolve(e, np.ones(5) / 5, "same")
    H = (base - top) * sz
    at = lambda z: prof[int(round(base - z / sz))] if 0 <= base - z / sz < len(prof) else 0
    near = lambda z, r=0.3: max(at(z + d) for d in np.arange(-r, r + 1e-6, sz))
    best = None
    for g in np.arange(3.5, 7.6, 0.1):
        for t in np.arange(3.0, 6.6, 0.1):
            for s in np.arange(2.9, 4.6, 0.05):
                L = [g, g + t] + [g + t + s * i for i in range(1, n - 2)]
                if H - L[-1] < 2.6:
                    continue
                sc = sum(near(z) for z in L)
                if best is None or sc > best[0]:
                    best = (sc, L)
    out = [0.0]
    for z in best[1]:
        cand = np.arange(z - 0.4, z + 0.4 + 1e-6, sz)
        out.append(round(float(max(cand, key=at)), 2))
    return out


def refine(pil, found, lines, base, sz, sx, roof):
    """Three fixes after the first look.
    1. Trees and palms: asked for by name; their area is 'hidden', not 'no window'.
    2. Bay by bay: columns = where the upper floors' openings line up; each floor x column cell is cut out, enlarged and
       asked again for a balcony (iron or stone) and for a window / balcony door. A small close picture is read better.
    3. A cell hidden by a tree with no opening found takes the opening of the same column on the nearest floor that
       has one, marked inferred."""
    W = pil.width
    to_m = lambda b: [round((b[0] + OFFX) * sx, 2), round(max(0, (base - b[3]) * sz), 2), round((b[2] + OFFX) * sx, 2), round((base - b[1]) * sz, 2)]
    hidden = []
    for b, s in ask(pil, "tree. palm tree. leaves", 0.30):
        if (b[2] - b[0]) * (b[3] - b[1]) < 0.6 * W * pil.height:
            hidden.append({"box": [round(v, 1) for v in b], "m": to_m(b), "score": round(s, 2)})
    xs = sorted((((f["m"][0] + f["m"][2]) / 2, f) for f in found if f["floor"] >= 2 and f["kind"] in ("window", "door")), key=lambda t: t[0])
    cols = []                                            # columns from floors >= 2 (the first floor is often wider bays)
    for x, f in xs:
        if cols and x - cols[-1]["xs"][-1] < 1.2:
            cols[-1]["xs"].append(x); cols[-1]["f"].append(f)
        else:
            cols.append({"xs": [x], "f": [f]})
    cols = [c for c in cols if len(c["xs"]) >= 2]
    for c in cols:
        c["x0"] = float(np.median([f["m"][0] for f in c["f"]])); c["x1"] = float(np.median([f["m"][2] for f in c["f"]]))
    n = len(lines)
    tops = lines[1:] + [roof]
    added = 0
    for fl in range(2, n):
        for c in cols:
            m0, m1 = max(0, c["x0"] - 0.6), min((W + OFFX) * sx, c["x1"] + 0.6)
            px0, px1 = max(0, int(m0 / sx - OFFX)), min(W, int(m1 / sx - OFFX))
            py0, py1 = int(base - tops[fl] / sz), int(base - lines[fl] / sz) + 8
            cell = pil.crop((px0, py0, px1, py1))
            k = max(1, int(240 / max(1, cell.height)))
            big = cell.resize((cell.width * k, cell.height * k))
            back = lambda b: [b[0] / k + px0, b[1] / k + py0, b[2] / k + px0, b[3] / k + py0]
            have = [f for f in found if f["floor"] == fl and min(f["m"][2], m1) - max(f["m"][0], m0) > 0.3]
            if fl < n - 1 and not any(f["kind"] == "balcony" for f in have):     # top floor (attic): its own pattern
                got = ask(big, "balcony. stone balustrade. curved balcony. balcony railing", 0.30)
                if got:
                    b, s = max(got, key=lambda t: t[1]); b = back(b)
                    low = b[3] > py1 - 0.35 * (py1 - py0)              # stands on the floor: bottom in the lowest third
                    alone = not any(g["kind"] == "balcony" and _share(b, g["box"]) > 0.3 for g in found)
                    if (b[3] - b[1]) * sz < 3.5 and low and alone:      # a balcony, not the whole cell or the parapet
                        found.append({"kind": "balcony", "score": round(s, 2), "box": [round(v, 1) for v in b], "m": to_m(b),
                                      "floor": fl, "by": "bay check"}); added += 1
            if not any(f["kind"] in ("window", "door") for f in have):
                got = ask(big, "window. balcony door. french window", 0.30)
                if got:
                    b, s = max(got, key=lambda t: t[1]); b = back(b)
                    found.append({"kind": "window", "score": round(s, 2), "box": [round(v, 1) for v in b], "m": to_m(b),
                                  "floor": fl, "by": "bay check"}); added += 1
                    continue
                cbox = [px0, py0, px1, py1]
                cov = max([_share(cbox, h_["box"]) for h_ in hidden] or [0])
                if cov > 0.3:                                        # hidden by a tree: copy the column's nearest floor
                    near = sorted(((abs(f["floor"] - fl), f) for f in c["f"] if f["floor"] != fl), key=lambda t: t[0])
                    if near:
                        g = near[0][1]; dz = lines[fl] - lines[g["floor"]]
                        m = [g["m"][0], round(g["m"][1] + dz, 2), g["m"][2], round(g["m"][3] + dz, 2)]
                        found.append({"kind": g["kind"], "score": 0, "box": [g["box"][0], g["box"][1] - dz / sz, g["box"][2], g["box"][3] - dz / sz],
                                      "m": m, "floor": fl, "inferred": True, "by": "hidden by a tree: copied from floor %d" % g["floor"]})
                        added += 1
    print("bay check: %d columns, %d added; %d tree areas" % (len(cols), added, len(hidden)))
    return hidden


def read():
    global OFFX
    info = building(REF)
    img = cv2.imread(str(D / "straight.jpg"))
    Lc, Rc, left0, right0, top = edges_of(img)
    # DETECTION always on the crop between the strongest edge lines (stable: the same picture gives the same boxes);
    # the true edges only change the measuring (OFFX = pixels between the true left edge and the crop's left)
    y0c = max(0, top - 15)                                     # no sky above the roofline
    crop = img[y0c:, left0:right0]; top -= y0c
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    whole = [(0, 0), (pil.width, 0), (pil.width, pil.height), (0, pil.height)]
    found = clean(detect(pil), whole)
    # street level: the bottom of the ground-floor doors and shopfronts, but only those standing in the lowest fifth of
    # the photo (the straightened photo ends at the pavement); a "shopfront" found higher up is a mistake and is dropped
    low = 0.80 * pil.height
    found = [f for f in found if f["kind"] not in ("door", "shopfront") or f["box"][3] >= low]
    ground = [f["box"][3] for f in found if f["kind"] in ("door", "shopfront")]
    base = int(np.median(ground)) if ground else pil.height - 1
    # which footprint side is in the photo (the old whole-plot scale is good enough to tell 21 m from 38 m)
    L, a, c = min(info["runs"], key=lambda r: abs(math.log(r[0] / (right0 - left0) / (info["roof_m"] / (base - top)))))
    info.update(front_m=L, front=[a, c])
    # HEIGHT, measured where the facade is: street = pavement in front; facade top = the front wall's top (cornice)
    fh = front_heights(a, c, info["foot"])
    H_c = fh["front_top_m"] if fh else info["roof_m"]
    info["lidar_front"] = fh
    pxm = (base - top) / H_c                                   # px per metre, up the facade (LiDAR)
    # EDGES: of the candidate lines, the pair whose width equals the Catastro front at that same scale
    pairs = [(abs((r - l) / pxm - L), l, r) for l in Lc for r in Rc if r - l > 0.5 * (right0 - left0)]
    err, left, right = min(pairs) if pairs else (0.0, left0, right0)
    left, right = int(left), int(right)
    sx = L / (right - left)                                    # m per px across (Catastro)
    sz = 1 / pxm                                               # m per px up (LiDAR)
    OFFX = left0 - left
    if right0 - left0 < 0.85 * (right - left):
        # the strongest lines were inside the facade (a pilaster, a bay edge): part of the facade was never searched.
        # Search again between the true edges; street level and the up scale follow the new detections.
        print("detection crop %d px < 85 %% of the facade %d px: searching the whole facade again" % (right0 - left0, right - left))
        left0, right0, OFFX = left, right, 0
        crop = img[y0c:, left:right]
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        whole = [(0, 0), (pil.width, 0), (pil.width, pil.height), (0, pil.height)]
        found = [f for f in clean(detect(pil), whole) if f["kind"] not in ("door", "shopfront") or f["box"][3] >= 0.80 * pil.height]
        ground = [f["box"][3] for f in found if f["kind"] in ("door", "shopfront")]
        base = int(np.median(ground)) if ground else pil.height - 1
        pxm = (base - top) / H_c
        sx, sz = L / (right - left), 1 / pxm
    info["roof_m"] = H_c
    for f in found:
        x0, y0, x1, y1 = f["box"]
        f["m"] = [round(max(0, (x0 + OFFX) * sx), 2), round(max(0, (base - y1) * sz), 2), round(min(L, (x1 + OFFX) * sx), 2), round((base - y0) * sz, 2)]
    found = [f for f in found if f["m"][3] > 0.3 and f["m"][1] < H_c + 1]
    Image.fromarray(cv2.cvtColor(img[y0c + top:y0c + base, left:right], cv2.COLOR_BGR2RGB)).save(D / "facade_photo_m.jpg", quality=90)
    n = info["floors"]
    lines = floor_lines(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), base, top, sz, n)
    # a balcony stands on its floor: where balconies sit on a line, the floor is at their bottom (+0,15 m slab)
    fixed = {}
    for i in range(1, n):
        b = [f["m"][1] for f in found if f["kind"] == "balcony" and abs((f["m"][1] + f["m"][3]) / 2 - lines[i]) < 1.5]
        if b:
            fixed[i] = round(float(min(b)) + 0.15, 2)          # lowest railing bottom = the slab
    up = sorted(i for i in fixed if i >= 2)
    if len(up) >= 2:                                         # upper floors evenly spaced from the balcony floors
        s_ = float(np.median([(fixed[b] - fixed[a]) / (b - a) for a, b in zip(up, up[1:])]))
        for i in range(2, n):
            if i not in fixed:
                j = min(up, key=lambda j: abs(j - i))
                fixed[i] = round(fixed[j] + s_ * (i - j), 2)
    for i, z in fixed.items():
        lines[i] = z
    # second look at the ground floor alone: shop arches and doors
    g_top = int(base - lines[1] / sz)
    band = pil.crop((0, g_top, pil.width, base + 5))
    extra = clean([dict(f, box=[f["box"][0], f["box"][1] + g_top, f["box"][2], f["box"][3] + g_top]) for f in detect(band, ASK_GROUND)], whole)
    for f in extra:
        if not any(iou(f["box"], g["box"]) > 0.3 for g in found):
            x0, y0, x1, y1 = f["box"]
            f["m"] = [round((x0 + OFFX) * sx, 2), round(max(0, (base - y1) * sz), 2), round((x1 + OFFX) * sx, 2), round((base - y0) * sz, 2)]
            found.append(f)
    for f in found:
        if f["kind"] == "balcony":                           # a balcony belongs to the floor line nearest its bottom
            f["floor"] = min(range(1, len(lines)), key=lambda i: abs(lines[i] - f["m"][1]))
            continue
        z = (f["m"][1] + f["m"][3]) / 2
        f["floor"] = max(i for i, l in enumerate(lines) if l <= z + 1e-6)
    hidden = refine(pil, found, lines, base, sz, sx, info["roof_m"])
    # balconies found bay by bay also place their floor (lowest bottom + 0,15 m slab), if within 1,2 m of the line
    for i in range(2, n):
        b = [f["m"][1] for f in found if f["kind"] == "balcony" and f.get("by") == "bay check" and f["floor"] == i]
        if b and abs(min(b) + 0.15 - lines[i]) < 1.2 and not any(g["kind"] == "balcony" and g.get("by") != "bay check" and g["floor"] == i for g in found):
            lines[i] = round(min(b) + 0.15, 2)
    for f in found:
        if f.get("inferred"):
            continue
        if f["kind"] == "balcony":
            f["floor"] = min(range(1, len(lines)), key=lambda i: abs(lines[i] - f["m"][1]))
            continue
        z = (f["m"][1] + f["m"][3]) / 2
        f["floor"] = max(i for i, l in enumerate(lines) if l <= z + 1e-6)
    # a floor line must sit above the heads of the floor below (+ 0,30 m lintel, our assumption) and not above the
    # sills of its own openings; where it does not, it moves up to that point and the openings are re-assigned
    moved = []
    for i in range(1, n):
        hb = [f["m"][3] for f in found if f["floor"] == i - 1 and f["kind"] in ("window", "door") and not f.get("inferred")]
        sa = [f["m"][1] for f in found if f["floor"] == i and f["kind"] in ("window", "door") and not f.get("inferred")]
        if len(hb) >= 2:
            lo = float(np.median(hb)) + 0.30
            hi = float(np.median(sa)) if sa else lo
            if lines[i] < lo and hi >= lo:
                moved.append((i, lines[i], round(lo, 2)))
                lines[i] = round(lo, 2)
    if moved:
        print("floor lines moved above the heads below:", moved)
        for f in found:
            if f["kind"] == "balcony" or f.get("inferred"):
                continue
            z = (f["m"][1] + f["m"][3]) / 2
            f["floor"] = max(i for i, l in enumerate(lines) if l <= z + 1e-6)
    # RULE (user, 10 Nov): the ground floor has its own height; every floor above has one same height.
    # Fit: line k (k = 1..n-1) = g + (k-1) * s, least squares on the measured lines; what is left above the top
    # floor up to the LiDAR cornice is the cornice / parapet band.
    measured = list(lines)
    k = np.arange(1, n)
    A = np.c_[np.ones(n - 1), k - 1]
    g, s_ = np.linalg.lstsq(A, np.array(lines[1:]), rcond=None)[0]
    fit = [0.0] + [round(float(g + (i - 1) * s_), 2) for i in range(1, n)]
    band = round(float(H_c - (fit[-1] + s_)), 2)
    resid = [round(m_ - f_, 2) for m_, f_ in zip(measured[1:], fit[1:])]
    print("fit: ground %.2f m, upper floors %.2f m each, cornice band %.2f m; measured minus fit %s" % (g, s_, band, resid))
    lines = fit
    for f in found:
        if f["kind"] == "balcony":
            f["floor"] = min(range(1, n), key=lambda i: abs(lines[i] - f["m"][1]))
        elif not f.get("inferred"):
            z = (f["m"][1] + f["m"][3]) / 2
            f["floor"] = max(i for i, l in enumerate(lines) if l <= z + 1e-6)
    res = {"ref": REF, **{k: info[k] for k in ("address", "front_m", "front", "floors", "roof_m")},
           "facade_m": info["front_m"], "height_m": info["roof_m"], "floor_lines_m": lines, "floor_lines_measured_m": measured,
           "floor_rule": {"ground_m": round(float(g), 2), "upper_m": round(float(s_), 2), "cornice_band_m": band, "measured_minus_fit_m": resid},
           "floor_heights_m": [round(b_ - a_, 2) for a_, b_ in zip(lines, lines[1:] + [info["roof_m"]])],
           "clear_heights_m": [round(b_ - a_ - 0.30, 2) for a_, b_ in zip(lines, lines[1:])],   # minus 0,30 m slab (our assumption)
           "px": {"left": left, "right": right, "crop_left": left0, "top": top, "base": base, "m_per_px_x": round(sx, 4), "m_per_px_z": round(sz, 4)},
           "check": f"edges chosen so the Catastro width fits the LiDAR height scale (off by {err:.2f} m); scale {1 / sx:.1f} px/m across, {1 / sz:.1f} px/m up",
           "lidar_front": info.get("lidar_front"),
           "detector": MODEL + " (Apache-2.0)",
           "source": "Photo: Dirección General del Catastro, accessed 2026-11-10. Heights: ICGC LiDAR (CC BY 4.0). Drawing: NOMAD.",
           "hidden": hidden, "items": found}
    json.dump(res, open(D / "facade.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pil.save(D / "facade_crop.jpg", quality=88)
    d = ImageDraw.Draw(pil)                                    # private check picture (never published)
    for h_ in hidden:
        d.rectangle(h_["box"], outline=(0, 160, 0), width=2)
    for f in found:
        d.rectangle(f["box"], outline=COL_CHECK[f["kind"]], width=3 if not f.get("inferred") else 1)
    for z in lines[1:]:
        y = base - z / sz
        d.line([(0, y), (pil.width, y)], fill=(229, 255, 0), width=2)
    d.line([(0, top), (pil.width, top)], fill=(255, 0, 255), width=2); d.line([(0, base), (pil.width, base)], fill=(255, 0, 255), width=2)
    pil.save(D / "check_PRIVATE.jpg", quality=85)
    cnt = {}
    for f in found:
        cnt.setdefault(f["floor"], {}).setdefault(f["kind"], 0); cnt[f["floor"]][f["kind"]] += 1
    print(res["check"]); print(json.dumps({k: cnt[k] for k in sorted(cnt)})); print("floor lines", lines)
    print("floor heights", res["floor_heights_m"], "clear", res["clear_heights_m"], "edges px", left, right)


# ======================================================================================================================
# STEP 3b ANALYSE before drawing (user, 12 Nov: "first analyse the image, then draw")
#   1. Level: the straightened photo can keep a little perspective (horizontals that tilt more the higher they are).
#      The tilt of every long near-horizontal line is measured against its height and taken out (rows sheared about the
#      facade's middle), so balconies and sills of one floor line up across the whole facade.
#   2. Repeat: each upper floor is cut into a band (between its floor lines) and the bands are compared (correlation of
#      the grey images). Floors that look alike form one TYPE; usually all upper floors are one type.
#   3. Template: the bands of one type are blended (pixel median): trees, blinds, people and one-off detection errors
#      fade, the repeated design stays. The openings are read on that clean typical floor, once.
#   4. Inventory: per type, every opening (kind, place across, sill and head above its floor), and the ground floor's
#      shopfronts and doors; saved for the user to check BEFORE the drawing (inventory.json, analysis.png).
# ======================================================================================================================

SAME = 0.55           # two floor bands whose grey images correlate at least this much are the same floor type


def level(img):
    """Measure the leftover tilt of the horizontals against height and take it out. Returns the levelled image and
    the tilt (degrees) found at the top and at the bottom."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    s = cv2.createLineSegmentDetector().detect(g)[0].reshape(-1, 4)
    dx, dy = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    L = np.hypot(dx, dy)
    keep = (L > 0.06 * img.shape[1]) & (np.abs(dy) < 0.15 * np.abs(dx) + 1e-9)
    if keep.sum() < 6:
        return img, (0.0, 0.0)
    slope = dy[keep] / dx[keep]
    yc = (s[keep, 1] + s[keep, 3]) / 2
    A = np.c_[np.ones(keep.sum()), yc]
    coef = np.linalg.lstsq(A * L[keep, None], slope * L[keep], rcond=None)[0]   # slope = a + b * y, weighted by length
    h, w = g.shape
    xc = w / 2
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    src_y = ys + (xs - xc) * (coef[0] + coef[1] * ys)
    out = cv2.remap(img, xs, src_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out, (float(np.degrees(np.arctan(coef[0]))), float(np.degrees(np.arctan(coef[0] + coef[1] * h))))


def bands(img, lines, top_m, sz, base):
    """The upper floors' bands (floor 1 up), each from its floor line up one typical floor height."""
    out = []
    for k in range(1, len(lines)):
        z0, z1 = lines[k], (lines[k + 1] if k + 1 < len(lines) else top_m)
        y0, y1 = int(round(base - z1 / sz)), int(round(base - z0 / sz))
        out.append((k, max(0, y0), min(img.shape[0], y1)))
    return out


def ncc(a, b):
    a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))


def structure(tpl, ops, sx, sz, hb):
    """The typical floor read as an architect would, after the vote:
    1. a "window" that is really the balcony's railing (mostly inside a balcony, head under 1,9 m) goes;
    2. a wide window with a bright pier down its middle is two windows (column brightness on the clean typical floor);
    3. every balcony has a door behind it: asked for just above the balcony on the typical floor; if none is read, a
       door of 0,55 x the balcony's width, centred, up to the floor's typical head (marked inferred)."""
    W = tpl.shape[1]
    bal = [o for o in ops if o["kind"] == "balcony"]
    inside = lambda o, b: max(0, min(o["x1"], b["x1"]) - max(o["x0"], b["x0"])) / max(1e-6, o["x1"] - o["x0"])
    ops = [o for o in ops if not (o["kind"] == "window" and o["head"] < 1.9 and any(inside(o, b) > 0.6 for b in bal))]
    g = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY).astype(float)
    out = []
    for o in ops:
        if o["kind"] == "window" and o["x1"] - o["x0"] > 1.0:
            c0, c1 = int(o["x0"] / sx), int(o["x1"] / sx)
            r0, r1 = int(hb - o["head"] / sz), int(hb - o["sill"] / sz)
            prof = g[max(0, r0):max(1, r1), c0:c1].mean(0)
            mid = prof[int(0.2 * len(prof)):int(0.8 * len(prof))]
            j = int(np.argmax(mid)) + int(0.2 * len(prof))
            if len(mid) and prof[j] > np.median(prof) + 15:      # a bright pier: two windows
                xs_ = o["x0"] + j * sx
                out += [dict(o, x1=round(xs_ - 0.06, 2), split="pier"), dict(o, x0=round(xs_ + 0.06, 2), split="pier")]
                continue
        out.append(o)
    heads = [o["head"] for o in out if o["kind"] == "window"]
    head = float(np.median(heads)) if heads else 2.4
    for b in [o for o in out if o["kind"] == "balcony"]:
        if any(o["kind"] in ("window", "door") and inside(o, b) > 0.5 and o["head"] > 1.9 for o in out):
            continue
        c0, c1 = max(0, int(b["x0"] / sx)), min(W, int(b["x1"] / sx))
        r0, r1 = max(0, int(hb - (head + 0.4) / sz)), int(hb - 0.05 / sz)
        crop = tpl[r0:r1, c0:c1]
        got = []
        if crop.size:
            k3 = 3
            pil = Image.fromarray(cv2.cvtColor(cv2.resize(crop, (crop.shape[1] * k3, crop.shape[0] * k3), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB))
            got = [(bx, sc) for bx, sc in ask(pil, "door. french window. roller shutter. balcony door", 0.25)
                   if (bx[3] - bx[1]) / k3 * sz > 1.2 and 0.5 <= (bx[2] - bx[0]) / k3 * sx < 0.95 * (b["x1"] - b["x0"])]
        if got:
            bx, sc = max(got, key=lambda t: t[1])
            out.append({"kind": "window", "x0": round(b["x0"] + bx[0] / 3 * sx, 2), "x1": round(b["x0"] + bx[2] / 3 * sx, 2),
                        "sill": 0.05, "head": round((hb - (r0 + bx[1] / 3)) * sz, 2), "by": "door behind the balcony"})
        else:
            w_ = 0.55 * (b["x1"] - b["x0"]); c = (b["x0"] + b["x1"]) / 2
            out.append({"kind": "window", "x0": round(c - w_ / 2, 2), "x1": round(c + w_ / 2, 2), "sill": 0.05, "head": round(head, 2),
                        "inferred": True, "by": "a balcony has a door: placed centred", "bal": b})
    # a balcony like another (width within 25 %) takes that balcony's door, read, at the same place in its own balcony
    read_ = [(o, b) for o in out if o.get("by") == "door behind the balcony" for b in out if b["kind"] == "balcony" and inside(o, b) > 0.5]
    for o in [q for q in out if q.get("bal")]:
        b = o.pop("bal")
        like = [(d, bb) for d, bb in read_ if abs((bb["x1"] - bb["x0"]) - (b["x1"] - b["x0"])) < 0.25 * (bb["x1"] - bb["x0"])]
        if like:
            d, bb = like[0]
            off = ((d["x0"] + d["x1"]) / 2 - (bb["x0"] + bb["x1"]) / 2)
            c = (b["x0"] + b["x1"]) / 2 - off if (b["x0"] + b["x1"]) / 2 > (bb["x0"] + bb["x1"]) / 2 else (b["x0"] + b["x1"]) / 2 + off
            w_ = d["x1"] - d["x0"]
            o.update(x0=round(c - w_ / 2, 2), x1=round(c + w_ / 2, 2), head=d["head"], by="the same door as the matching balcony")
    return out


def analyse():
    f = json.load(open(D / "facade.json", encoding="utf-8"))
    img = cv2.imread(str(D / "facade_photo_m.jpg"))            # the facade alone, edge to edge, street to cornice
    H_px = img.shape[0]
    sz, sx = f["px"]["m_per_px_z"], f["px"]["m_per_px_x"]
    lines, H = f["floor_lines_m"], f["height_m"]
    lev, tilt = level(img)
    cv2.imwrite(str(D / "facade_level.jpg"), lev, [cv2.IMWRITE_JPEG_QUALITY, 90])
    upper = f["floor_rule"]["upper_m"]
    base = H_px                                                   # the picture's bottom row is the street
    B = bands(lev, lines, H, sz, base)
    hb = int(round(upper / sz))                                   # one typical floor, in px
    ks = list(range(1, len(lines)))
    gry = lambda m: cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)

    def win(k, d):
        """floor k's window: one typical floor high, bottom on its floor line moved up by d px (padded at the top)"""
        y1 = int(round(base - lines[k] / sz)) - d
        y0 = y1 - hb
        m = lev[max(0, y0):max(1, y1)]
        return cv2.copyMakeBorder(m, max(0, -y0), 0, 0, 0, cv2.BORDER_REPLICATE) if y0 < 0 else m

    # line each floor up with a middle floor: real floors are not exactly equal, so slide each by up to 0,8 m
    refk = ks[(len(ks) - 1) // 2]
    R = int(0.8 / sz)
    shift = {k: max(range(-R, R + 1, 2), key=lambda d: ncc(gry(win(k, d)), gry(win(refk, 0)))) for k in ks}
    W_ = {k: win(k, shift[k]) for k in ks}
    sim = {(a_, b_): ncc(gry(W_[a_]), gry(W_[b_])) for a_ in ks for b_ in ks}
    core = max(ks, key=lambda a_: sum(sim[(a_, b_)] for b_ in ks))
    types = [[k for k in ks if sim[(core, k)] >= SAME]]
    rest = [k for k in ks if k not in types[0]]
    while rest:
        c = rest[0]; t = [k for k in rest if sim[(c, k)] >= SAME]; types.append(t); rest = [k for k in rest if k not in t]
    inv = {"ref": REF, "address": f["address"], "tilt_deg": {"top": round(tilt[0], 2), "bottom": round(tilt[1], 2)},
           "floors": len(lines), "ground_m": lines[1], "upper_m": upper,
           "shift_m": {str(k): round(shift[k] * sz, 2) for k in ks},
           "similarity": {"%d-%d" % k_: round(v, 2) for k_, v in sim.items() if k_[0] < k_[1]}, "types": []}
    tiles = []
    for ti, t in enumerate(types):
        tpl = np.median(np.stack([W_[k] for k in t]), axis=0).astype(np.uint8)   # the clean typical floor
        cv2.imwrite(str(D / ("type_%d.jpg" % ti)), tpl)
        # VOTE: read every floor of the type (enlarged) and keep what most floors agree on, at the median size
        seen = []
        for k in t:
            k3 = 2
            pil = Image.fromarray(cv2.cvtColor(cv2.resize(W_[k], (W_[k].shape[1] * k3, hb * k3), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB))
            whole = [(0, 0), (pil.width, 0), (pil.width, pil.height), (0, pil.height)]
            for o in clean(detect(pil, {"window": "window. french window. balcony door", "balcony": "balcony railing. balcony"}), whole):
                x0, y0, x1, y1 = [v / k3 for v in o["box"]]
                sill, head = (hb - y1) * sz, (hb - y0) * sz
                if o["kind"] == "balcony" and head - sill < 0.6:
                    continue                                      # a ledge, not a balcony
                seen.append({"floor": k, "kind": o["kind"], "x0": x0 * sx, "x1": x1 * sx, "sill": sill, "head": head})
        groups = []
        for o in sorted(seen, key=lambda o: (o["kind"], (o["x0"] + o["x1"]) / 2)):
            c = (o["x0"] + o["x1"]) / 2
            g_ = next((g for g in groups if g["kind"] == o["kind"] and abs(g["c"] - c) < 0.45), None)
            if g_:
                g_["m"].append(o); g_["c"] = float(np.median([(q["x0"] + q["x1"]) / 2 for q in g_["m"]]))
            else:
                groups.append({"kind": o["kind"], "c": c, "m": [o]})
        need = 1 if len(t) == 1 else max(2, int(np.ceil(0.5 * len(t))))
        ops = []
        for g in groups:
            fl_ = {q["floor"] for q in g["m"]}
            if len(fl_) >= need:
                med = lambda k_: round(float(np.median([q[k_] for q in g["m"]])), 2)
                ops.append({"kind": g["kind"], "x0": med("x0"), "x1": med("x1"), "sill": med("sill"), "head": med("head"),
                            "floors_seen": len(fl_), "of": len(t)})
        # one box over a pair: drop an opening that holds the centres of two narrower kept openings of the same kind
        cen2 = lambda o: (o["x0"] + o["x1"]) / 2
        ops = [o for o in ops if not (sum(1 for q in ops if q is not o and q["kind"] == o["kind"] and o["x0"] < cen2(q) < o["x1"]
                                          and q["x1"] - q["x0"] < 0.7 * (o["x1"] - o["x0"])) >= 2)]
        ops = structure(tpl, ops, sx, sz, hb)
        ops.sort(key=lambda o: o["x0"])
        inv["types"].append({"floors": t, "openings": ops,
                             "count": {k_: sum(1 for o in ops if o["kind"] == k_) for k_ in ("window", "balcony")}})
        tiles.append((ti, tpl, ops))
    # ground floor: shopfronts and doors, on the levelled photo
    g_top = int(round(base - lines[1] / sz))
    gpil = Image.fromarray(cv2.cvtColor(lev[g_top:base], cv2.COLOR_BGR2RGB))
    gw = [(0, 0), (gpil.width, 0), (gpil.width, gpil.height), (0, gpil.height)]
    gfound = clean(detect(gpil, {"shopfront": "shop front. shop window. glazed shopfront", "door": "entrance door. doorway. door"}), gw)
    inv["ground"] = sorted([{"kind": "door" if (o["box"][2] - o["box"][0]) * sx < 1.3 else o["kind"],      # a narrow glazed opening is a door
                             "x0": round(o["box"][0] * sx, 2), "x1": round(o["box"][2] * sx, 2),
                             "head": round((gpil.height - o["box"][1]) * sz, 2), "score": o["score"]}
                            for o in gfound if o["box"][3] > 0.8 * gpil.height], key=lambda o: o["x0"])
    # each floor found by sliding the typical floor (type with most floors) up the levelled facade
    big = max(range(len(types)), key=lambda i: len(types[i]))
    tg = cv2.cvtColor(tiles[big][1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    score = cv2.matchTemplate(cv2.cvtColor(lev, cv2.COLOR_BGR2GRAY).astype(np.float32), tg, cv2.TM_CCOEFF_NORMED)[:, 0]
    zof = lambda y: (base - (y + hb)) * sz
    found_ = []
    for k in ks:
        cand = [y for y in range(len(score)) if abs(zof(y) - lines[k]) <= 1.0]
        if cand:
            y = max(cand, key=lambda y: score[y])
            if score[y] >= 0.6:
                found_.append([k, round(zof(y), 2), round(float(score[y]), 2)])
    inv["floor_photo"] = found_                              # [floor, line (m), match]
    json.dump(inv, open(D / "inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # the analysis picture: levelled facade with floor lines and types | each type's clean typical floor with what was read
    colours = [(0, 200, 255), (255, 120, 0), (0, 180, 0), (200, 0, 200)]
    show = lev.copy()
    for k, y0, y1 in B:
        ti = next(i for i, t in enumerate(types) if k in t)
        cv2.rectangle(show, (2, y0 + 2), (show.shape[1] - 3, y1 - 2), colours[ti % 4], 3)
        cv2.putText(show, "floor %d: type %s" % (k, "ABCD"[ti]), (8, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colours[ti % 4], 2)
    cv2.rectangle(show, (2, g_top), (show.shape[1] - 3, base - 2), (60, 60, 60), 3)
    for o in inv["ground"]:
        cv2.rectangle(show, (int(o["x0"] / sx), int(base - o["head"] / sz)), (int(o["x1"] / sx), base - 3), (0, 140, 255) if o["kind"] == "door" else (90, 160, 60), 3)
    panels = []
    for ti, tpl, ops in tiles:
        p = cv2.resize(tpl, (tpl.shape[1] * 2, tpl.shape[0] * 2))
        for o in ops:
            c = (60, 60, 200) if o["kind"] == "balcony" else (200, 90, 40)
            cv2.rectangle(p, (int(o["x0"] / sx * 2), int((hb - o["head"] / sz) * 2)), (int(o["x1"] / sx * 2), int((hb - o["sill"] / sz) * 2)), c, 3)
        cv2.putText(p, "type %s (floors %s)" % ("ABCD"[ti], ",".join(map(str, types[ti]))), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        panels.append(p)
    right = np.vstack([cv2.copyMakeBorder(p, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for p in panels])
    hgt = max(show.shape[0], right.shape[0])
    pad = lambda m: cv2.copyMakeBorder(m, 0, hgt - m.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.imwrite(str(D / "analysis_PRIVATE.jpg"), np.hstack([pad(show), pad(right)]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("tilt left in the photo: %.2f deg at the top, %.2f deg at the bottom (taken out)" % tilt)
    print("floors lined up (shift, m):", inv["shift_m"])
    print("floor types:", {"ABCD"[i]: t for i, t in enumerate(types)})
    print("similarity:", inv["similarity"])
    for i, t in enumerate(inv["types"]):
        print("type %s openings:" % "ABCD"[i], [(o["kind"], o["x0"], o["x1"], o["sill"], o["head"]) for o in t["openings"]])
    print("ground:", [(o["kind"], o["x0"], o["x1"], o["head"]) for o in inv["ground"]])


# ======================================================================================================================
# STEP 4  DRAW the facade as an architect reads it
#   tidy:     per floor, overlapping openings merge; windows share the floor's head; a window over a balcony is a balcony
#             door; on the typical floors every opening snaps to its column and takes the column's typical width.
#   symmetry: a TEST, not a rule: the facade counts as symmetrical only if >= 60 % of the openings seen have a mirror
#             partner within 0,8 m AND the mirror line is within 8 % of the width from the facade's middle; then one template width, mirrored columns, pairs by order from the outside in,
#             balconies from their doors + the middle balcony's margin, repetition stamps missing balconies, one width and
#             head for the ground-floor rhythm, one opening height on the typical floors. Inferred items are marked.
# ======================================================================================================================

COL = {"window": "#2C5D8F", "balcony door": "#6E9BC6", "door": "#C98A2B", "shopfront": "#3F8F5A", "balcony": "#C4473A"}
INK, PAPER = "#111211", "#F4F4F1"


def tidy(f):
    """Detections -> a regular facade drawing (exemplar method). Ground floor, first floor and top floor keep their
    own pattern (shops, bay windows, attic)."""
    W, H = f["facade_m"], f["height_m"]
    lines = f["floor_lines_m"] + [H]
    n = len(lines) - 1
    floors = {}
    for fl in range(n):
        row = [i for i in f["items"] if i["floor"] == fl]
        ops = sorted([i for i in row if i["kind"] != "balcony"], key=lambda i: i["m"][0])
        merged = []
        for i in ops:
            a_, b_ = i["m"][0], i["m"][2]
            if merged and a_ < merged[-1]["x1"] - 0.2:
                m = merged[-1]; m["x1"] = max(m["x1"], b_); m["lo"] = min(m["lo"], i["m"][1]); m["hi"] = max(m["hi"], i["m"][3])
                m["seen"] = m["seen"] or not i.get("inferred")
                if i["kind"] in ("door", "shopfront"):
                    m["kind"] = i["kind"]
            else:
                merged.append({"x0": a_, "x1": b_, "kind": i["kind"], "lo": i["m"][1], "hi": i["m"][3], "seen": not i.get("inferred")})
        bal = []
        # a "balcony" under 0,6 m tall is a stone ledge or a sill, not a balcony (real ones measured 1,0 m and more)
        for q in sorted([i for i in row if i["kind"] == "balcony" and fl < n - 1 and i["m"][3] - i["m"][1] >= 0.6], key=lambda i: i["m"][0]):   # attic: none
            if bal and q["m"][0] < bal[-1][1] - 0.2:
                bal[-1][1] = max(bal[-1][1], q["m"][2])
            else:
                bal.append([q["m"][0], q["m"][2]])
        floors[fl] = {"ops": [m for m in merged if m["x1"] - m["x0"] >= 0.5], "bal": bal}
    typical = range(2, n - 1)
    every = [m for fl in typical for m in floors[fl]["ops"]]
    cen_ = lambda m: (m["x0"] + m["x1"]) / 2

    def bridge(m):
        """a box over two narrower openings seen in the same place on other floors (one box caught a pair)"""
        inner = sorted(cen_(q) for q in every if q is not m and m["x0"] < cen_(q) < m["x1"] and q["x1"] - q["x0"] < 0.7 * (m["x1"] - m["x0"]))
        return len(inner) >= 2 and inner[-1] - inner[0] > 0.4
    pts = sorted((cen_(m), m["x1"] - m["x0"], m["seen"]) for m in every if not bridge(m))
    # openings join one column when their centres are closer than 1,2 m and than 0,9 x the narrower one's width
    # (pairs of narrow windows side by side are two columns, not one)
    cols = []
    for x, w, seen in pts:
        if cols and x - cols[-1]["x"][-1] < min(1.2, 0.9 * min(w, cols[-1]["w"][-1][0])):
            cols[-1]["x"].append(x); cols[-1]["w"].append((w, seen))
        else:
            cols.append({"x": [x], "w": [(w, seen)]})
    axes = []
    for c in cols:
        if len(c["x"]) >= 2:
            ws = [w for w, s in c["w"] if s] or [w for w, s in c["w"]]
            axes.append((float(np.median(c["x"])), float(np.median(ws))))
    out = []
    for fl in range(n):
        ops, bal = floors[fl]["ops"], floors[fl]["bal"]
        if fl in typical:
            split = []
            for m in ops:                                    # a box over a pair: one opening per column it covers
                inside_ = [a for a in axes if m["x0"] < a[0] < m["x1"]]
                if bridge(m) and len(inside_) >= 2:
                    split += [dict(m, x0=a[0] - a[1] / 2, x1=a[0] + a[1] / 2) for a in inside_]
                else:
                    split.append(m)
            ops[:] = split
            for m in ops:
                cx = (m["x0"] + m["x1"]) / 2
                ax_ = min(axes, key=lambda a: abs(a[0] - cx), default=None)
                if ax_ and abs(ax_[0] - cx) < 0.9:
                    m["x0"], m["x1"] = ax_[0] - ax_[1] / 2, ax_[0] + ax_[1] / 2
            edges = [e for a in axes for e in (a[0] - a[1] / 2 - 0.3, a[0] + a[1] / 2 + 0.3)]
            for q in bal:
                for j in (0, 1):
                    e = min(edges, key=lambda e: abs(e - q[j]), default=None)
                    if e is not None and abs(e - q[j]) < 0.9:
                        q[j] = e
        if fl in typical and len(bal) >= 2:                  # hidden bay on a balcony floor: stamp the floor's balcony
            for m in ops:
                cx = (m["x0"] + m["x1"]) / 2
                hid = any(h_["m"][0] <= cx <= h_["m"][2] and h_["m"][1] <= lines[fl] + 1 <= h_["m"][3] for h_ in f.get("hidden", []))
                if hid and not any(min(m["x1"], q[1]) - max(m["x0"], q[0]) > 0.3 for q in bal):
                    bal.append([m["x0"] - 0.3, m["x1"] + 0.3, True])
        win = [m["hi"] for m in ops if m["kind"] == "window" and m["seen"]]
        head = min(float(np.median(win)) if win else lines[fl + 1] - 0.6, lines[fl + 1] - 0.3)
        for m in ops:
            a_, b_, k = max(0.0, m["x0"]), min(W, m["x1"]), m["kind"]
            if fl == 0:
                sill, top = 0.0, min(m["hi"], lines[1] - 0.3)
                if k == "window" and m["lo"] < 0.6:
                    k = "shopfront"                          # down to the pavement on the ground floor
            else:
                over = any(min(b_, q[1]) - max(a_, q[0]) > 0.3 for q in bal)
                k = "balcony door" if over else k
                sill = lines[fl] + 0.05 if over else max(lines[fl] + 0.6, min(m["lo"], head - 1.0))
                top = head
            out.append({"floor": fl, "kind": k, "x0": round(a_, 2), "x1": round(b_, 2), "sill": round(sill, 2), "head": round(top, 2),
                        "inferred": not m["seen"]})
        for q in bal:
            out.append({"floor": fl, "kind": "balcony", "x0": round(max(0, q[0]), 2), "x1": round(min(W, q[1]), 2),
                        "sill": round(lines[fl], 2), "head": round(lines[fl] + 1.0, 2), "inferred": len(q) > 2})
    return out


def symmetry(f, out):
    """Template + repetition grid + symmetry (after the user's note).
    1. Mirror axis: the line that best maps the openings seen onto each other (searched, not assumed).
    2. Typical floors: every opening takes one template width (median of the single openings really seen) and sits on
       columns mirrored about the axis.
    3. Other floors: mirrored pairs get equal width and mirrored places (a seen opening wins over a hidden one); a hidden
       opening inside the mirror of a bigger seen one is replaced by that mirror.
    4. Balconies: from the doors they serve (on the wall, so free of perspective) plus the side margin of the middle
       balcony, where the photo's perspective is smallest."""
    W, items = f["facade_m"], f["items"]
    n = len(f["floor_lines_m"])
    typical = set(range(2, n - 1))
    hidden = f.get("hidden", [])

    def in_hidden(x, z):
        return any(h["m"][0] <= x <= h["m"][2] and h["m"][1] <= z <= h["m"][3] for h in hidden)

    cen = lambda o: (o["x0"] + o["x1"]) / 2
    ops = [o for o in out if o["kind"] != "balcony"]
    seen = [o for o in ops if not o.get("inferred") and not in_hidden(cen(o), (o["sill"] + o["head"]) / 2)]
    cs = [cen(o) for o in seen]
    axis = float(min(np.arange(0.35 * W, 0.65 * W, 0.01), key=lambda a: sum(min(abs(2 * a - c - d) for d in cs) for c in cs)))
    # TEST, not a rule (user): symmetrical only if most openings seen have a mirror partner on the same floor within 0,8 m
    hits = sum(1 for o in seen if any(abs((2 * axis - cen(o)) - cen(q)) < 0.8 for q in seen if q["floor"] == o["floor"]))
    share = hits / max(1, len(seen))
    if share < 0.6:
        print("not symmetrical: %d of %d openings have a mirror partner; column grid only" % (hits, len(seen)))
        return out, None
    if abs(axis - W / 2) > 0.08 * W:                       # a mirror line far from the middle: few columns pair by chance
        print("not symmetrical: the best mirror line is %.2f m from the facade's middle (more than 8 %% of %.1f m); column grid only"
              % (abs(axis - W / 2), W))
        return out, None
    print("symmetrical: %d of %d openings have a mirror partner" % (hits, len(seen)))
    singles = [i["m"][2] - i["m"][0] for i in items if i["floor"] in typical and i["kind"] == "window"
               and not i.get("inferred") and i["m"][2] - i["m"][0] < 2.2]
    tw = float(np.median(singles)) if singles else None
    offs = sorted((abs(cen(o) - axis), o["x1"] - o["x0"]) for o in ops if o["floor"] in typical and o["x1"] - o["x0"] < 3.0)
    groups = []                                          # column offsets from the axis, over all typical floors
    for d, w in offs:
        if groups and d - groups[-1][-1][0] < min(0.9, 0.9 * (tw or 1.0)):
            groups[-1].append((d, w))
        else:
            groups.append([(d, w)])
    # a column ON the axis only when its openings sit close to it (under a quarter of the template width): a pair of
    # narrow windows either side of the axis stays a pair. Each column keeps its own width when it differs from the
    # template by more than 25 % on the narrow side (narrow windows beside wide balcony doors)
    col = [0.0 if np.mean([d for d, _ in g]) < 0.25 * (tw or 2.4) else float(np.mean([d for d, _ in g])) for g in groups]
    colw = []
    for g in groups:
        w_ = float(np.median([w for _, w in g]))
        colw.append(w_ if tw and w_ < 0.75 * tw else tw)       # only narrower columns (wider ones are often merged boxes)
    res = []
    for fl in range(n):
        row = [o for o in ops if o["floor"] == fl]
        if fl in typical and tw:
            cols = sorted({axis + s_ * x for x in col for s_ in (-1, 1)})
            split = []
            for o in row:                                     # one box over two doors (merged): one opening per column
                inside_ = [c for c in cols if o["x0"] <= c <= o["x1"]]
                if o["x1"] - o["x0"] >= 3.0 and len(inside_) >= 2:
                    split += [dict(o, x0=c - 0.1, x1=c + 0.1) for c in inside_]
                else:
                    split.append(o)
            for o in split:
                k_ = min(range(len(col)), key=lambda i: abs(abs(cen(o) - axis) - col[i]))
                d, w_ = col[k_], colw[k_]
                c2 = axis + (d if cen(o) >= axis else -d)
                res.append(dict(o, x0=round(c2 - w_ / 2, 2), x1=round(c2 + w_ / 2, 2)))
            continue
        hid = lambda o: bool(o.get("inferred")) or in_hidden(cen(o), (o["sill"] + o["head"]) / 2)
        # pair by order (1st from the left with 1st from the right ...): robust to the perspective shift of parts that
        # stand out of the wall, like bay windows. Hidden ones are left out and rebuilt by mirroring.
        vis = sorted([o for o in row if not hid(o)], key=cen)
        out_fl = []
        i, j = 0, len(vis) - 1
        while i < j:
            o, p = vis[i], vis[j]
            if cen(o) < axis < cen(p) and abs((cen(o) + cen(p)) / 2 - axis) < 1.5:
                w2 = ((o["x1"] - o["x0"]) + (p["x1"] - p["x0"])) / 2
                d2 = (abs(cen(o) - axis) + abs(cen(p) - axis)) / 2
                out_fl.append(dict(o, x0=round(axis - d2 - w2 / 2, 2), x1=round(axis - d2 + w2 / 2, 2)))
                out_fl.append(dict(p, x0=round(axis + d2 - w2 / 2, 2), x1=round(axis + d2 + w2 / 2, 2)))
                i += 1; j -= 1
            else:
                break
        rest = vis[i:j + 1]
        for o in rest:
            c, w = cen(o), o["x1"] - o["x0"]
            if abs(c - axis) < 0.6 + w / 4:                      # the middle one: centred on the axis
                out_fl.append(dict(o, x0=round(axis - w / 2, 2), x1=round(axis + w / 2, 2)))
                continue
            out_fl.append(o)
            m0, m1 = 2 * axis - o["x1"], 2 * axis - o["x0"]      # its mirror falls behind the tree: draw it there
            if any(h["m"][0] - 0.5 <= m0 and m1 <= h["m"][2] + 0.5 for h in hidden) and not any(
                    min(m1, q["x1"]) - max(m0, q["x0"]) > 0.3 for q in out_fl):
                out_fl.append(dict(o, x0=round(m0, 2), x1=round(m1, 2), inferred=True))
        res += out_fl
    lines_ = f["floor_lines_m"]
    # balconies from their doors
    bal = [o for o in out if o["kind"] == "balcony"]
    margin = None
    for fl in sorted(typical):
        mid = [i for i in items if i["floor"] == fl and i["kind"] == "balcony" and i["m"][0] < axis < i["m"][2]
               and i["m"][2] - i["m"][0] < 5]
        if mid and tw:
            margin = ((mid[0]["m"][2] - mid[0]["m"][0]) - tw) / 2
            break
    margin = margin if margin is not None and 0.2 < margin < 1.2 else 0.5
    uniq = []
    for b in sorted(bal, key=lambda b: bool(b.get("inferred"))):
        if not any(u["floor"] == b["floor"] and min(u["x1"], b["x1"]) - max(u["x0"], b["x0"]) > 0.5 * (b["x1"] - b["x0"]) for u in uniq):
            uniq.append(b)
    for b in uniq:
        doors = [r for r in res if r["floor"] == b["floor"] and min(b["x1"], r["x1"]) - max(b["x0"], r["x0"]) > 0.3]
        if b["floor"] in typical and doors:
            res.append(dict(b, x0=round(min(r["x0"] for r in doors) - margin, 2), x1=round(max(r["x1"] for r in doors) + margin, 2)))
        elif b["x0"] < axis < b["x1"]:                      # e.g. the terrace rail over the bay windows: mirror it
            d = max(axis - b["x0"], b["x1"] - axis)
            res.append(dict(b, x0=round(axis - d, 2), x1=round(axis + d, 2)))
        else:
            res.append(b)
    # mirror (symmetrical facades): an opening whose mirror partner on the same floor has a balcony gets one too
    for fl in sorted(typical):
        bls = [r for r in res if r["floor"] == fl and r["kind"] == "balcony"]
        for r in [q for q in res if q["floor"] == fl and q["kind"] != "balcony"]:
            if any(min(r["x1"], b["x1"]) - max(r["x0"], b["x0"]) > 0.3 for b in bls):
                continue
            m0, m1 = 2 * axis - r["x1"], 2 * axis - r["x0"]
            mb = [b for b in bls if min(m1, b["x1"]) - max(m0, b["x0"]) > 0.3]
            if mb and abs(cen(r) - axis) > 0.6:
                b = mb[0]
                res.append(dict(b, x0=round(2 * axis - b["x1"], 2), x1=round(2 * axis - b["x0"], 2), inferred=True))
                r.update(kind="balcony door", sill=round(lines_[fl] + 0.05, 2), inferred=True)
                bls = [q for q in res if q["floor"] == fl and q["kind"] == "balcony"]
    # repetition (stamp): on a typical floor where most openings have a balcony, an opening without one gets the floor's
    # template balcony and becomes a balcony door (inferred)
    lines = f["floor_lines_m"]
    for fl in sorted(typical):
        opn = [r for r in res if r["floor"] == fl and r["kind"] != "balcony"]
        bls = [r for r in res if r["floor"] == fl and r["kind"] == "balcony"]
        cov = lambda r: any(min(r["x1"], b["x1"]) - max(r["x0"], b["x0"]) > 0.3 for b in bls)
        if opn and sum(map(cov, opn)) >= 0.6 * len(opn):
            for r in opn:
                # only in a column that has balconies on most typical floors (a column of plain windows keeps none)
                same = [q for q in res if q["floor"] in typical and q["kind"] != "balcony" and abs(cen(q) - cen(r)) < 0.4]
                withb = [q for q in same if any(b["floor"] == q["floor"] and b["kind"] == "balcony" and min(q["x1"], b["x1"]) - max(q["x0"], b["x0"]) > 0.3 for b in res)]
                if not cov(r) and len(withb) >= 0.6 * len(same):
                    res.append({"floor": fl, "kind": "balcony", "x0": round(r["x0"] - margin, 2), "x1": round(r["x1"] + margin, 2),
                                "sill": round(lines[fl], 2), "head": round(lines[fl] + 1.0, 2), "inferred": True})
                    r.update(kind="balcony door", sill=round(lines[fl] + 0.05, 2), inferred=True)
    # ground floor: openings in one rhythm (shopfronts and the entrance under the same arches) share one width and one
    # head height, the medians of the ground floor; the entrance keeps its kind
    g0 = [r for r in res if r["floor"] == 0 and r["kind"] != "balcony"]
    if len(g0) >= 3:
        ws = [r["x1"] - r["x0"] for r in g0]
        if max(ws) <= 1.4 * min(ws):                         # one rhythm only (no wide garage door etc.)
            gw, gh = float(np.median(ws)), float(np.median([r["head"] for r in g0]))
            for r in g0:
                c = (r["x0"] + r["x1"]) / 2
                r.update(x0=round(c - gw / 2, 2), x1=round(c + gw / 2, 2), head=round(gh, 2))
            print("ground floor: %d openings, one width %.2f m, head %.2f m" % (len(g0), gw, gh))
    # one opening height on the typical floors (same rule as the width): the median head above each floor line
    rel = [r["head"] - lines[r["floor"]] for r in res if r["floor"] in typical and r["kind"] != "balcony" and not r.get("inferred")]
    if rel:
        th = float(np.median(rel))
        for r in res:
            if r["floor"] in typical and r["kind"] != "balcony":
                r["head"] = round(lines[r["floor"]] + th, 2)
        print("template opening height %.2f m above the floor" % th)
    print("axis %.2f m (facade centre %.2f), template width %s m, balcony margin %.2f m, columns %s"
          % (axis, W / 2, round(tw, 2) if tw else None, margin, [round(c, 2) for c in col]))
    return res, axis


def elevation(f, ops):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    W, H = f["facade_m"], f["height_m"]
    fig, ax = plt.subplots(figsize=(6.4, 8.6), dpi=150)
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    ax.add_patch(Rectangle((0, 0), W, H, fc="#D9D9D4", ec=INK, lw=1.4))
    for fl, z in enumerate(f["floor_lines_m"]):
        if fl:
            ax.plot([0, W], [z, z], color="#8A8A85", lw=0.6, ls=(0, (4, 3)))
        ax.text(W + 0.4, z + 0.8, f"floor {fl}  +{z:.1f} m", fontsize=6.5, family="monospace", va="center")
    for o in ops:
        if o["kind"] == "balcony":
            ax.add_patch(Rectangle((o["x0"], o["sill"]), o["x1"] - o["x0"], 1.0, fc="none", ec=COL["balcony"], lw=1.4, hatch="||||",
                                   ls=(0, (3, 2)) if o.get("inferred") else "-"))
        else:
            ax.add_patch(Rectangle((o["x0"], o["sill"]), o["x1"] - o["x0"], o["head"] - o["sill"], fc=COL[o["kind"]], ec=INK, lw=0.6,
                                   alpha=0.45 if o.get("inferred") else 0.9, hatch="////" if o.get("inferred") else None))
    for h_ in f.get("hidden", []):
        x0, z0, x1, z1 = h_["m"]
        ax.add_patch(Rectangle((x0, z0), x1 - x0, min(z1, H) - z0, fc="none", ec="#3F8F5A", lw=0.9, ls=(0, (3, 2))))
        ax.text(x0 + 0.3, min(z1, H) - 0.9, "hidden by a tree", fontsize=5.5, color="#3F8F5A", family="monospace")
    if f.get("axis"):
        ax.plot([f["axis"], f["axis"]], [-0.5, H + 0.5], color="#C4473A", lw=0.6, ls=(0, (8, 3, 2, 3)))
        ax.text(f["axis"] + 0.2, H + 0.6, "mirror axis", fontsize=5.5, color="#C4473A", family="monospace")
    ax.annotate("", (0, -1.2), (W, -1.2), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(W / 2, -2.2, f"{W:.1f} m street front (Catastro)", ha="center", fontsize=7, family="monospace")
    ax.annotate("", (-1.2, 0), (-1.2, H), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(-2.0, H / 2, f"{H:.1f} m (ICGC LiDAR)", rotation=90, ha="center", va="center", fontsize=7, family="monospace")
    for k, c in COL.items():
        ax.add_patch(Rectangle((0, 0), 0, 0, fc=c, label=k))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=4, frameon=False, fontsize=7)
    ax.set_xlim(-3.5, W + 4.5); ax.set_ylim(-3, H + 1); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{f['address']}: facade drawn by NOMAD from a photo", fontsize=9, loc="left")
    fig.text(0.02, 0.03, "Hatched / dashed = inferred: hidden by a tree, taken from the same column or floor.", fontsize=5.5, family="monospace")
    fig.text(0.02, 0.01, "Openings found by Grounding DINO, tidied per floor. Photo: Dirección General del Catastro, accessed 2026-11-10.",
             fontsize=5.5, family="monospace")
    fig.savefig(D / "elevation.png", facecolor=PAPER, bbox_inches="tight"); plt.close(fig)


def quad(x0, x1, z0, z1, y):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]


def model3d(f, ops):
    """Facade wall with the openings cut out (wall = strips between openings), glass set back, balcony slabs out.
    Not run: the 3D facade waits until it is asked for (user, 10 Nov)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    W, H, DEP = f["facade_m"], f["height_m"], 12.0
    faces, cols = [], []
    xs = sorted({0.0, W} | {o["x0"] for o in ops if o["kind"] != "balcony"} | {o["x1"] for o in ops if o["kind"] != "balcony"})
    holes = [o for o in ops if o["kind"] != "balcony"]
    for a, b in zip(xs, xs[1:]):                            # each vertical strip: wall wherever no opening
        cuts = sorted((o["sill"], o["head"]) for o in holes if o["x0"] <= a + 1e-6 and o["x1"] >= b - 1e-6)
        z = 0.0
        for s, h in cuts + [(H, H)]:
            if s > z + 1e-6:
                faces.append(quad(a, b, z, s, 0)); cols.append("#D9D9D4")
            z = max(z, h)
    for o in holes:                                         # glass 0,25 m back
        faces.append(quad(o["x0"], o["x1"], o["sill"], o["head"], 0.25)); cols.append(COL[o["kind"]])
    for o in ops:
        if o["kind"] == "balcony":
            x0, x1, s = o["x0"], o["x1"], o["sill"]
            faces.append([(x0, 0, s), (x1, 0, s), (x1, -0.9, s), (x0, -0.9, s)]); cols.append("#8A8A85")
            faces.append(quad(x0, x1, s, s + 1.0, -0.9)); cols.append(COL["balcony"])
    faces += [[(0, 0, H), (W, 0, H), (W, DEP, H), (0, DEP, H)], [(0, 0, 0), (0, DEP, 0), (0, DEP, H), (0, 0, H)]]
    cols += ["#BDBDB8", "#C9C9C4"]
    fig = plt.figure(figsize=(7.5, 7.5), dpi=150); fig.patch.set_facecolor(PAPER)
    ax = fig.add_subplot(projection="3d"); ax.set_facecolor(PAPER)
    ax.add_collection3d(Poly3DCollection(faces, facecolors=cols, edgecolors=[("#555" if c != "#D9D9D4" else c) for c in cols],
                                         linewidths=0.3))
    ax.set_xlim(-2, W + 2); ax.set_ylim(-6, DEP); ax.set_zlim(0, H)
    ax.set_box_aspect((W + 4, DEP + 6, H)); ax.view_init(elev=14, azim=-62); ax.axis("off")
    ax.set_title(f"{f['address']}: the same facade in 3D, openings cut in the wall", fontsize=9, loc="left")
    fig.savefig(D / "facade_3d.png", facecolor=PAPER, bbox_inches="tight"); plt.close(fig)


def uniform(meas, n, top):
    """User's rule (12 Nov): the ground floor has its own height g, every floor above one same height s, both rounded to
    5 cm. meas = [[floor, line m], ...] measured on the photo; top = the facade's top from LiDAR. Best fit on a 5 cm grid,
    with the top floor ending no more than 0,5 m above the LiDAR top."""
    best = None
    for g in np.arange(2.5, 7.01, 0.05):
        for s_ in np.arange(2.6, 4.51, 0.05):
            if g + (n - 1) * s_ > top + 0.5:
                continue
            e = float(np.sqrt(np.mean([(z - (g + (k - 1) * s_)) ** 2 for k, z in meas])))
            if best is None or e < best[0]:
                best = (e, round(float(g), 2), round(float(s_), 2))
    return best


def floors_uniform(f):
    """The floor lines from the uniform rule; measured on the analysed photo when there is an inventory, else the lines
    the reader measured (balcony bottoms)."""
    n = len(f["floor_lines_m"])
    inv_p = D / "inventory.json"
    meas = [[k, z] for k, z, _ in json.load(open(inv_p, encoding="utf-8")).get("floor_photo", [])] if inv_p.exists() else []
    if len(meas) < 2:
        meas = [[k, z] for k, z in enumerate(f["floor_lines_measured_m"]) if k >= 1]
    e, g, s_ = uniform(meas, n, f["height_m"])
    lines = [0.0] + [round(g + (k - 1) * s_, 2) for k in range(1, n)]
    f["floor_lines_m"] = lines
    f["floor_rule"] = {"ground_m": g, "upper_m": s_, "cornice_band_m": round(f["height_m"] - (g + (n - 1) * s_), 2),
                       "rounded_to_m": 0.05, "fit_rms_m": round(e, 2), "measured_m": meas,
                       "city_model_m": round(5 + 3 * (n - 1), 1), "lidar_top_m": f["height_m"]}
    print("floors: ground %.2f m, every upper floor %.2f m (5 cm steps; photo fit %.2f m rms); top floor ends at %.2f m, "
          "LiDAR facade top %.2f m, city model estimate %.1f m" % (g, s_, e, g + (n - 1) * s_, f["height_m"], 5 + 3 * (n - 1)))
    return f


def from_inventory(f, inv):
    """Every floor drawn from its type in the inventory (step 3b): the same openings on every floor of a type, at that
    floor's line; a window over a balcony is its balcony door; the ground floor from the inventory's ground openings."""
    lines = f["floor_lines_m"]
    ops = [{"floor": 0, "kind": g["kind"], "x0": g["x0"], "x1": g["x1"], "sill": 0.0, "head": round(min(g["head"], lines[1] - 0.3), 2),
            "inferred": False} for g in inv["ground"]]
    for t in inv["types"]:
        bal = [o for o in t["openings"] if o["kind"] == "balcony"]
        top_head = max([o["head"] for o in t["openings"] if o["kind"] != "balcony"] or [2.4])
        for k in t["floors"]:
            z = lines[k]
            room = (lines[k + 1] if k + 1 < len(lines) else f["height_m"]) - z - 0.3    # up to the next floor (or cornice), minus a lintel
            fit_ = min(1.0, room / top_head)                     # a lower floor (often the top one) keeps the openings, scaled to fit
            for o in t["openings"]:
                if o["kind"] == "balcony":
                    ops.append({"floor": k, "kind": "balcony", "x0": o["x0"], "x1": o["x1"], "sill": round(z, 2), "head": round(z + 1.0, 2),
                                "inferred": False})
                    continue
                over = any(min(o["x1"], b["x1"]) - max(o["x0"], b["x0"]) > 0.3 for b in bal) and o["sill"] < 0.3
                ops.append({"floor": k, "kind": "balcony door" if over else "window", "x0": o["x0"], "x1": o["x1"],
                            "sill": round(z + o["sill"] * fit_, 2), "head": round(z + o["head"] * fit_, 2), "inferred": bool(o.get("inferred"))})
    cen = [(o["x0"] + o["x1"]) / 2 for o in ops if o["floor"] > 0]
    W = f["facade_m"]
    axis = float(min(np.arange(0.35 * W, 0.65 * W, 0.01), key=lambda a: sum(min(abs(2 * a - c - d) for d in cen) for c in cen))) if cen else None
    return ops, axis if axis is not None and abs(axis - W / 2) <= 0.08 * W else None


def draw():
    f = floors_uniform(json.load(open(D / "facade.json", encoding="utf-8")))
    if (D / "inventory.json").exists():                    # analysed first (step 3b): draw from the inventory
        ops, axis = from_inventory(f, json.load(open(D / "inventory.json", encoding="utf-8")))
        print("drawn from the inventory (step 3b)")
    else:
        ops, axis = symmetry(f, tidy(f))
    count = {}
    for o in ops:
        count.setdefault(str(o["floor"]), {}).setdefault(o["kind"], 0)
        count[str(o["floor"])][o["kind"]] += 1
    f["axis"] = round(float(axis), 2) if axis is not None else None
    json.dump({k: f[k] for k in ("ref", "address", "facade_m", "height_m", "floors", "floor_lines_m", "front", "px", "source", "hidden", "axis")} | {"per_floor": count, "openings": ops},
              open(D / "openings.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    elevation(f, ops)
    print(json.dumps(count))
    export()                                                # the app, its 3D and the plans follow every new drawing


# ======================================================================================================================
# STEP 5  EXPORT every facade read so far for the app: site/data/facades.json. Only what NOMAD made (sizes, floor
#   heights, openings); never the photo. Private use only (Catastro Sede legal notice): never in a shared or published copy.
# ======================================================================================================================

def left_right(ref, front):
    """The facade line's two ends in UTM, ordered left to right as seen from the street (the drawing's x runs that way)."""
    a, c = front
    b = json.load(gzip.open(ROOT / "data/barcelona/catastro/buildings.json.gz", "rt", encoding="utf-8"))[ref]
    area = lambda r: abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:]))) / 2
    ring = max((poly[0] for poly in b["foot"]), key=area)
    cx, cy = np.mean([p[0] for p in ring]), np.mean([p[1] for p in ring])
    L = math.dist(a, c); ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
    nx, ny = -uy, ux                                             # normal to the street (away from the building)
    if (cx - (a[0] + c[0]) / 2) * nx + (cy - (a[1] + c[1]) / 2) * ny > 0:
        nx, ny = -nx, -ny
    rx, ry = -ny, nx                                             # the viewer looks along -n; their right hand points this way
    return [list(a), list(c)] if a[0] * rx + a[1] * ry < c[0] * rx + c[1] * ry else [list(c), list(a)]


APPROVED = ROOT / "results/facade/approved.json"     # {ref: date}: ONLY these go to the app, its 3D and the plans


def approved():
    return json.load(open(APPROVED, encoding="utf-8")) if APPROVED.exists() else {}


def approve():
    """CHECKPOINT (user, 12 Nov): a facade reaches the app only after the user has looked at its drawing and approved it."""
    import datetime
    import shutil
    a = approved()
    a[REF] = datetime.date.today().isoformat()
    json.dump(a, open(APPROVED, "w", encoding="utf-8"), indent=1)
    keep = ROOT / "results/facade/approved" / REF               # a frozen copy: later code changes do not touch it
    keep.mkdir(parents=True, exist_ok=True)
    for n_ in ("facade.json", "openings.json", "elevation.png"):
        shutil.copy2(D / n_, keep / n_)
    print("approved:", REF)
    export()


def export():
    """Every APPROVED facade, for the app. Runs by itself after every drawing and every approval, so the app, its 3D and
    the plans always use the latest approved drawing; a drawing not approved yet never leaves results/facade."""
    out, ok = {}, approved()
    for p in sorted((ROOT / "results/facade/approved").glob("*/openings.json")):   # the frozen approved copies only
        o = json.load(open(p, encoding="utf-8"))
        if o["ref"] not in ok:
            continue
        f = json.load(open(p.parent / "facade.json", encoding="utf-8"))
        out[o["ref"]] = {
            "lr": left_right(o["ref"], f["front"]),             # the facade line, left end then right end (UTM)
            "address": o["address"], "w": o["facade_m"], "h": o["height_m"], "lines": o["floor_lines_m"],
            "rule": f.get("floor_rule"), "axis": o.get("axis"), "street_z": (f.get("lidar_front") or {}).get("street_z"),
            "ops": [[x["floor"], x["kind"], x["x0"], x["x1"], x["sill"], x["head"], int(bool(x.get("inferred")))] for x in o["openings"]],
            "hidden": [h["m"] for h in o.get("hidden") or []],
            "source": "Facade read by NOMAD from the Catastro facade photo (Dirección General del Catastro, accessed 2026-11-10); "
                      "heights ICGC LiDAR (CC BY 4.0).",
        }
    json.dump(out, open(ROOT / "site/data/facades.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(out), "approved facades ->", ROOT / "site/data/facades.json", "| waiting for approval:",
          sorted(p.parent.name for p in (ROOT / "results/facade").glob("*/openings.json") if p.parent.name not in ok))


# ======================================================================================================================

if __name__ == "__main__":
    if "approve" in sys.argv[1:]:
        approve(); sys.exit()
    steps = [a for a in sys.argv[1:] if a in ("straighten", "read", "analyse", "draw", "export")] or ["straighten", "read", "analyse"]
    for s in steps:
        print("== STEP", {"straighten": "1 STRAIGHTEN", "read": "3 READ", "analyse": "3b ANALYSE", "draw": "4 DRAW", "export": "5 EXPORT"}[s], REF)
        {"straighten": straighten, "read": read, "analyse": analyse, "draw": draw, "export": export}[s]()
