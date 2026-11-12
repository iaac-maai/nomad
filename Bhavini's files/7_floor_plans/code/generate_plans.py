"""Nomad - plans from NOMAD's plan AI (7_floor_plans/code/train_plan.py), turned into real plans and checked like every library plan.

  picture   the U-Net fills the flat's rectangle with room classes (0,25 m pixels)
  clean     a 3 x 3 majority filter; blobs under 0,5 m² join their neighbour; every wall pixel joins its nearest room
            (no dead area); one living room, one kitchen (extra ones join a neighbour); the biggest bedroom is bedroom 1
  rooms     each room = the union of its pixels, holes filled, shrunk 5 cm each side (a 10 cm partition), rectilinear
  doors     every room gets a door on its longest shared wall to a hall, else to the living room; a kitchen touching the
            living room is open to it; the entrance at the asked point, into the room there; windows on the lit sides
  checks    the same as every real plan: library_fit (plan graph, doors, turning circles, widths, daylight side) and
            furnish (wardrobe, bed, worktop, bathroom, 1,20 m circles). Only plans that pass are kept.
Run (GPU env): tools/train-venv/Scripts/python.exe 7_floor_plans/code/generate_plans.py test | library
  test     the held-out flats' own conditions -> pass rate (7_floor_plans/output/ai/test_pass.json)
  library  a grid of street-flat slots -> 7_floor_plans/output/library/library_ai.json
"""
import json, math, sys, time
from pathlib import Path
import numpy as np
import torch
from scipy import ndimage
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "7_floor_plans/code"), str(ROOT / "7_floor_plans/code")]
import train_plan as T  # noqa: E402
import library_fit as F  # noqa: E402
import furnish as U  # noqa: E402

PX, N = T.PX, T.N
CLASSES = ["outside", "wall", "living", "bed_main", "bed", "kitchen", "bath", "hall", "storage"]
ROOM = dict((i, k) for i, k in enumerate(CLASSES) if i >= 2)
MIN_PX = 8                                   # 0,5 m²
MIN_M2 = {"living": 10.0, "bed_main": 6.0, "bed": 5.0, "kitchen": 3.0, "bath": 2.5, "hall": 1.5, "storage": 0.5}   # smaller blobs are noise
SHRINK = 0.05
ONE_OF = ("living", "kitchen")
DEV = "cuda" if torch.cuda.is_available() and "--cpu" not in sys.argv else "cpu"


def load(dev=None):
    dev = dev or DEV
    ck = torch.load(ROOT / "7_floor_plans/output/ai/plan_unet.pt", map_location=dev, weights_only=True)
    net = T.UNet().to(dev)
    net.load_state_dict(ck["state"])
    net.eval()
    return net


def predict(net, C, dev=None):
    dev = dev or DEV
    out = []
    with torch.no_grad():
        for i in range(0, len(C), 256):
            c = torch.as_tensor(np.asarray(C[i:i + 256], dtype=np.float32))
            out.append(net(T.conditions(c).to(dev)).softmax(1).cpu().numpy())
    return np.concatenate(out)


def _majority(lab, w, d):
    a = lab[:d, :w]
    cnt = np.stack([ndimage.uniform_filter((a == k).astype(np.float32), 3, mode="nearest") for k in range(len(CLASSES))])
    return cnt.argmax(0)


def _neighbour_label(comp, mask, labels):
    """The label of the component sharing most border with `mask` (excluding its own)."""
    ring = ndimage.binary_dilation(mask) & ~mask
    vals = labels[ring]
    vals = vals[vals > 0]
    vals = vals[vals != comp]
    if not len(vals):
        return None
    return np.bincount(vals).argmax()


def _lines(change, gap=2, support=4):
    """Wall lines along one axis: positions where the room type changes over >= `support` pixels (1 m), the strongest
    one kept within `gap` pixels (0,5 m)."""
    cand = sorted([(int(v), i) for i, v in enumerate(change) if v >= support], reverse=True)
    keep = []
    for v, i in cand:
        if all(abs(i - j) > gap for j in keep):
            keep.append(i)
    return sorted(keep)


def _straighten(cls):
    """Straight, orthogonal walls: the flat is cut by its main wall lines into cells, each cell takes the room type most
    of its pixels have (walls only where nothing else is)."""
    d, w = cls.shape
    xs = [0] + _lines([(cls[:, x - 1] != cls[:, x]).sum() for x in range(1, w)]) + [w]
    xs = sorted(set([0] + [x + 1 for x in xs[1:-1]] + [w]))
    ys = sorted(set([0] + [y + 1 for y in _lines([(cls[y - 1, :] != cls[y, :]).sum() for y in range(1, d)])] + [d]))
    out = cls.copy()
    for y0, y1 in zip(ys[:-1], ys[1:]):
        for x0, x1 in zip(xs[:-1], xs[1:]):
            cell = cls[y0:y1, x0:x1].ravel()
            cnt = np.bincount(cell, minlength=len(CLASSES))
            cnt[1] = 0 if cnt[2:].sum() else cnt[1]
            out[y0:y1, x0:x1] = cnt.argmax()
    return out


def clean(prob, w, d):
    """Class probabilities (K, N, N) -> per-pixel room-component labels and their kinds, inside the w x d pixel rectangle."""
    cls = prob[:, :d, :w].argmax(0)
    cls = _majority(np.pad(cls, ((0, N - d), (0, N - w))), w, d)
    cls[cls == 0] = 1                                         # inside the flat nothing is outside
    cls = _straighten(cls)
    labels = np.zeros_like(cls)
    kinds = {0: None}
    n = 0
    for k in range(2, len(CLASSES)):
        lab, m = ndimage.label(cls == k)
        for j in range(1, m + 1):
            n += 1
            labels[lab == j] = n
            kinds[n] = CLASSES[k]
    for _ in range(3):                                        # blobs too small for their kind join their neighbour
        for comp in sorted(kinds, key=lambda c: (labels == c).sum() if c else 0):
            if comp == 0 or kinds.get(comp) is None:
                continue
            mask = labels == comp
            if 0 < mask.sum() < max(MIN_PX, MIN_M2.get(kinds[comp], 0.5) / (PX * PX)):
                nb = _neighbour_label(comp, mask, labels)
                labels[mask] = nb if nb else 0
                kinds.pop(comp)
    for kind in ONE_OF:                                       # one living room, one kitchen: extra ones join a neighbour
        comps = sorted([c for c, k in kinds.items() if k == kind], key=lambda c: -(labels == c).sum())
        for comp in comps[1:]:
            mask = labels == comp
            nb = _neighbour_label(comp, mask, labels)
            if nb:
                labels[mask] = nb
                kinds.pop(comp)
    if (labels == 0).any() and (labels > 0).any():           # wall pixels join their nearest room: no dead area
        _, idx = ndimage.distance_transform_edt(labels == 0, return_indices=True)
        labels = labels[idx[0], idx[1]]
    beds = sorted([c for c, k in kinds.items() if k in ("bed", "bed_main")], key=lambda c: -(labels == c).sum())
    for i, c in enumerate(beds):
        kinds[c] = "bed_main" if i == 0 else "bed"
    return labels, dict((c, k) for c, k in kinds.items() if c and (labels == c).any())


def _poly(mask):
    rows, cols = np.nonzero(mask)
    g = unary_union([box(c * PX, r * PX, (c + 1) * PX, (r + 1) * PX) for r, c in zip(rows, cols)])
    if isinstance(g, MultiPolygon):
        g = max(g.geoms, key=lambda p: p.area)
    return Polygon(g.exterior).simplify(0.001)


def _shared(a, b):
    s = a.boundary.intersection(b.boundary)
    segs = [g for g in getattr(s, "geoms", [s]) if g.geom_type == "LineString" and g.length > 0.3]
    return max(segs, key=lambda g: g.length) if segs else None


def vectorize(prob, c, ident="ai"):
    """One picture + its condition row -> a library entry (7_floor_plans/code/build_library.py format) or None. A room that no
    door can reach (it touches only bathrooms, or too little of anything) joins its neighbour, and the plan is redone."""
    w, d = int(round(float(c[0]) / PX)), int(round(float(c[1]) / PX))
    labels, kinds = clean(prob, w, d)
    for _ in range(4):
        if not kinds:
            return None
        f, lost = _build(labels, kinds, c, w, d, ident)
        if not lost:
            return f
        for u in lost:
            mask = labels == u
            nb = _neighbour_label(u, mask, labels)
            if nb is None:
                return None
            labels[mask] = nb
            kinds.pop(u, None)
    return None


def _build(labels, kinds, c, w, d, ident):
    W, D = w * PX, d * PX
    comps = sorted(kinds)
    polys = dict((k, _poly(labels == k)) for k in comps)
    rooms, idx = [], {}
    for k in comps:
        g = polys[k].buffer(-SHRINK, join_style=2)
        if g.is_empty or g.area < 1.0:
            continue
        if isinstance(g, MultiPolygon):
            g = max(g.geoms, key=lambda p: p.area)
        pts = [[round(x, 2), round(y, 2)] for x, y in list(g.exterior.coords)[:-1]]
        idx[k] = len(rooms)
        rooms.append({"kind": kinds[k], "pts": pts, "area": round(g.area, 2), "clear": round(F.clear_width(pts), 2)})
    if not any(r["kind"] == "living" for r in rooms):
        return None, []
    ex, ey = float(c[4]), float(c[5])
    e_lab = labels[min(d - 1, max(0, int(ey / PX))), min(w - 1, max(0, int(ex / PX)))]
    if e_lab not in idx:
        return None, []
    doors, edges = [], []
    kind_of = dict((k, kinds[k]) for k in idx)
    adj = {}
    for a in idx:
        for b in idx:
            if a < b:
                s = _shared(polys[a], polys[b])
                if s is not None and s.length >= 0.9:
                    adj[(a, b)] = adj[(b, a)] = s
    # doors as people walk: from the entrance room, keep adding the unreached room with the best door - through a hall
    # first, then the living room, then the kitchen; never through a bathroom; a bedroom only as the last resort
    COST = {"hall": 0, "living": 1, "kitchen": 3, "storage": 6, "bed_main": 8, "bed": 8, "bath": 99}
    reached = set([e_lab])
    while True:
        best = None
        for (v, u), s in adj.items():
            if v in reached and u not in reached and COST[kind_of[v]] < 99:
                c_ = COST[kind_of[v]] - min(s.length, 3.0) / 10.0
                if best is None or c_ < best[0]:
                    best = (c_, v, u, s)
        if best is None:
            break
        _, v, u, s = best
        reached.add(u)
        if set((kind_of[u], kind_of[v])) == set(("kitchen", "living")) and s.length >= 1.2:
            edges.append([idx[u], idx[v], 0.0])              # a kitchen open to the living room
            continue
        m = s.interpolate(0.5, normalized=True)
        dw = 0.80 if s.length >= 1.0 else 0.70
        doors.append({"at": [round(m.x, 2), round(m.y, 2)], "w": dw})
        edges.append([idx[u], idx[v], dw])
    lost = [k for k in idx if k not in reached]
    if lost:
        return None, lost
    side = min([("front", ey), ("back", D - ey), ("left", ex), ("right", W - ex)], key=lambda t: t[1])[0]
    ent = {"at": [round(min(max(ex, 0.0), W), 2), round(min(max(ey, 0.0), D), 2)], "w": 0.90, "side": side, "room": idx[e_lab]}
    lit = (["front"] if c[2] > 0.5 else []) + (["back"] if c[3] > 0.5 else [])
    windows = []
    for r in rooms:
        if r["kind"] in ("hall", "storage"):
            continue
        g = Polygon(r["pts"])
        for s_, y0 in (("front", 0.0), ("back", D)):
            if s_ not in lit:
                continue
            seg = g.intersection(box(0, y0 - 0.2, W, y0 + 0.2))
            if not seg.is_empty and seg.bounds[2] - seg.bounds[0] >= 0.8:
                x0, x1 = seg.bounds[0], seg.bounds[2]
                windows.append({"at": [round((x0 + x1) / 2, 2), round(-0.1 if s_ == "front" else D + 0.1, 2)],
                                "w": round(0.6 * (x1 - x0), 2), "side": s_})
    beds = sum(1 for r in rooms if r["kind"] in ("bed", "bed_main"))
    return ({"id": ident, "bedrooms": beds, "W": round(W, 2), "D": round(D, 2), "rooms": rooms, "doors": doors, "windows": windows,
            "entrance": ent, "edges": edges, "lit": lit, "useful": round(sum(r["area"] for r in rooms), 1),
            "source": "NOMAD AI", "W0": round(W, 2), "D0": round(D, 2)}, [])


def check(f):
    """(passes, failing texts, the checked plan) with NOMAD's library and furniture checks."""
    g = F.widen_doors(f)
    cs = F.checks(g)
    g["swings"] = F.swings(g)
    _, fc = U.furnish(g)
    cov = F.coverage(g)
    bad = [x["text"] for x in cs if not x["ok"]] + [x["text"] for x in fc if not x["ok"] and x["rule"] != "furniture"]
    bad += [x["text"] for x in fc if x["rule"] == "furniture" and not x["ok"] and not x["text"].startswith("living")]
    if cov < F.MIN_COVER:
        bad.append("rooms cover %.0f %% of the flat" % (100 * cov))
    kinds = [r["kind"] for r in g["rooms"]]
    for k in ("kitchen", "bath"):                            # Decret 141/2012 Annex 1 3.15.b and 3.15.c: every home has them
        if k not in kinds:
            bad.append("no %s" % k)
    if any(len(r["pts"]) > 8 for r in g["rooms"]):          # straight walls: rectangles, L, T or U rooms only
        bad.append("a room with more than 8 corners")
    return not bad, bad, g


def test():
    z = np.load(ROOT / "7_floor_plans/output/ai/plan_set.npz")
    C = z["C"]
    n = len(C)
    flat = np.arange(n) // 2
    g = torch.Generator().manual_seed(0)                      # the same held-out flats as train_plan.py
    test_flats = torch.randperm(int(flat.max()) + 1, generator=g)[: (n // 2) // 20].numpy()
    te = np.where(np.isin(flat, test_flats))[0]
    net = load()
    prob = predict(net, C[te])
    ok, reasons, n_vec, beds_ok = 0, {}, 0, 0
    for p, i in zip(prob, te):
        f = vectorize(p, C[i], "ai-test-%d" % i)
        if f is None:
            reasons["no plan (no living room or entrance room)"] = reasons.get("no plan (no living room or entrance room)", 0) + 1
            continue
        n_vec += 1
        beds_ok += f["bedrooms"] == int(C[i][6])
        good, bad, _ = check(f)
        ok += good
        for b in bad[:1]:
            key = b.split(":")[0][:40]
            reasons[key] = reasons.get(key, 0) + 1
    res = {"held_out": len(te), "vectorized": n_vec, "bedrooms_as_asked": beds_ok, "pass_every_check": ok,
           "pass_rate": round(ok / len(te), 3), "first_failure": dict(sorted(reasons.items(), key=lambda x: -x[1])[:12])}
    json.dump(res, open(ROOT / "7_floor_plans/output/ai/test_pass.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


def library(seeds=(0.2, 0.35, 0.5, 0.65, 0.8)):
    """Street-flat slots: one-sided (lit front, door at the back) and through flats (lit front + back, door at a side)."""
    rows = []
    for beds in range(4):
        for W in np.arange(4.5, 12.01, 0.5):
            for D in np.arange(6.0, 10.01, 0.5):
                for t in seeds:
                    rows.append([W, D, 1, 0, W * t, D - 0.1, beds, 1])               # one-sided, door at the back
                    rows.append([W, D, 1, 1, 0.1, D * t, beds, 1])                   # through flat, door on the left
    C = np.array(rows, dtype=np.float32)
    net = load()
    t0 = time.time()
    prob = predict(net, C)
    keep, tried = [], 0
    for k, (p, c) in enumerate(zip(prob, C)):
        f = vectorize(p, c, "ai-%d" % k)
        tried += 1
        if f is None or f["bedrooms"] != int(c[6]):
            continue
        good, _, _ = check(f)
        if good:
            keep.append(f)
    out = ROOT / "7_floor_plans/output/library/library_ai.json"
    json.dump(keep, open(out, "w"), separators=(",", ":"))
    by = {}
    for f in keep:
        key = "%d bed %s" % (f["bedrooms"], "+".join(f["lit"]))
        by[key] = by.get(key, 0) + 1
    print("slots %d, plans that pass every check %d (%.0f %%) %s, %.0f s" % (tried, len(keep), 100.0 * len(keep) / tried, by, time.time() - t0))


if __name__ == "__main__":
    {"test": test, "library": library}[sys.argv[1] if len(sys.argv) > 1 else "test"]()
