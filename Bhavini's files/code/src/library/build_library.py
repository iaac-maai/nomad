"""Nomad - the plan library: the real flats that pass every NOMAD rule, as plan graphs ready to stretch into a shop.

From the 13,444 Swiss Dwellings flats (0-3 bedrooms) that pass every NOMAD rule (CC BY 4.0), each flat is:
  squared     turned so its walls run along x and y (minimum rotated rectangle of the flat), then turned by a quarter
              so the side with the most window is the front (y = 0); kept only if every room is rectilinear
  rooms       polygons in metres from the flat's corner, NOMAD kinds: living, bed_main, bed, kitchen, bath, hall, storage
  graph       nodes = rooms, edges = doors (width) and open connections; the entrance door and its room
  sides       window length per side (front / back / left / right) and the side of the entrance door
This is the "plan graph" (Finch: rooms as nodes, doors and adjacency as edges): rules are checked on it
(src/library/plan_graph.py) and its walls are stretched to a new flat outline (src/library/fit.py).
Out: results/library/library.json (every squared flat), results/library/summary.json
Run: .venv/Scripts/python src/library/build_library.py [limit]
"""
import json, math, sys, time
from collections import defaultdict
from pathlib import Path
import pandas as pd
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "learn"))
import habitability as H  # noqa: E402

OUT = ROOT / "results" / "library"
NOMAD_KIND = {"living": "living", "bedroom": "bed", "kitchen": "kitchen", "bath": "bath", "circulation": "hall", "storage": "storage"}
SNAP = 0.12


def snap_axis(vals):
    """Cluster coordinates closer than SNAP and return value -> cluster mean."""
    vs = sorted(set(round(v, 3) for v in vals))
    groups, cur = [], [vs[0]]
    for v in vs[1:]:
        if v - cur[-1] <= SNAP:
            cur.append(v)
        else:
            groups.append(cur); cur = [v]
    groups.append(cur)
    m = {}
    for g in groups:
        c = round(sum(g) / len(g), 2)
        for v in g:
            m[v] = c
    return m


def rectilinear(poly, tol_deg=4.0):
    c = list(poly.exterior.coords)
    for a, b in zip(c[:-1], c[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if math.hypot(dx, dy) < 0.05:
            continue
        ang = abs(math.degrees(math.atan2(dy, dx))) % 90
        if min(ang, 90 - ang) > tol_deg:
            return False
    return True


def side_of(p, box, tol=0.7):
    x0, y0, x1, y1 = box
    d = {"front": p[1] - y0, "back": y1 - p[1], "left": p[0] - x0, "right": x1 - p[0]}
    k = min(d, key=d.get)
    return k if d[k] <= tol else "inside"


def square_flat(rooms, wins, ents, doors):
    """rooms: [(kind, poly)]; wins / doors / ents: shapely geometries. Returns the squared flat or None."""
    flat = unary_union([p for _, p in rooms])
    mrr = flat.minimum_rotated_rectangle
    c = list(mrr.exterior.coords)
    ang = math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0]))
    org = flat.centroid
    rot = lambda g, a: affinity.rotate(g, a, origin=org)
    best = None
    for q in (0, 90, 180, 270):                                   # the quarter turn that puts most window at the front
        a = -ang + q
        R = [rot(p, a) for _, p in rooms]
        box = unary_union(R).bounds
        W = [rot(w, a) for w in wins]
        front = sum(H.width_of(w)[1] for w in W if side_of((w.centroid.x, w.centroid.y), box) == "front")
        if best is None or front > best[0]:
            best = (front, a)
    a = best[1]
    geoms = [p for _, p in rooms]
    touch = lambda g, d=0.2: [i for i, q in enumerate(geoms) if q.distance(g) < d]
    edges = []
    for d in doors:                                                 # a door joins the two rooms nearest to it (walls 0,1-0,5 m)
        t = sorted((q.distance(d), i) for i, q in enumerate(geoms) if q.distance(d) < 0.5)
        if len(t) >= 2:
            edges.append([t[0][1], t[1][1], round(H.width_of(d)[1], 2)])
    for i in range(len(geoms)):                                     # open connections: rooms touching with no wall
        for j in range(i + 1, len(geoms)):
            if geoms[i].distance(geoms[j]) < 0.05 and geoms[i].buffer(0.05).intersection(geoms[j].buffer(0.05)).area > 0.05:
                edges.append([i, j, 0.0])
    ent_room = None
    for e in ents:                                                  # the room the entrance opens into: nearest within 0,5 m
        t = sorted((q.distance(e), i) for i, q in enumerate(geoms) if q.distance(e) < 0.5)
        ent_room = t[0][1] if t else None
        break
    R = [rot(p, a).simplify(0.05) for _, p in rooms]
    if not all(p.geom_type == "Polygon" and rectilinear(p) for p in R):
        return None
    box = unary_union(R).bounds
    xs = snap_axis([x - box[0] for p in R for x, _ in p.exterior.coords])
    ys = snap_axis([y - box[1] for p in R for _, y in p.exterior.coords])
    out_rooms = []
    for (k, _), p in zip(rooms, R):
        pts = []
        for x, y in list(p.exterior.coords)[:-1]:
            q = [xs[round(x - box[0], 3)], ys[round(y - box[1], 3)]]
            if not pts or q != pts[-1]:
                pts.append(q)
        if len(pts) >= 3 and pts[0] == pts[-1]:
            pts.pop()
        g = Polygon(pts).buffer(0)
        if g.is_empty or g.area < 0.5:
            return None
        out_rooms.append({"kind": k, "pts": pts, "area": round(g.area, 2), "clear": round(H.clear(g), 2)})
    bx = (0.0, 0.0, max(xs.values()), max(ys.values()))
    loc = lambda g: (round(g.centroid.x - box[0], 2), round(g.centroid.y - box[1], 2))
    windows = []
    for w in wins:
        g = rot(w, a)
        p = loc(g)
        windows.append({"at": p, "w": round(H.width_of(g)[1], 2), "side": side_of(p, bx)})
    ent = None
    for e in ents:
        g = rot(e, a)
        p = loc(g)
        ent = {"at": p, "w": round(H.width_of(g)[1], 2), "side": side_of(p, bx)}
        break
    if ent is not None:
        ent["room"] = ent_room
    return {"W": bx[2], "D": bx[3], "rooms": out_rooms, "windows": windows, "entrance": ent, "edges": edges,
            "doors": [{"at": loc(rot(d, a)), "w": round(H.width_of(rot(d, a))[1], 2)} for d in doors]}


def main(limit=None):
    t = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    ok, df = H.load(limit)
    print("flats %d (%.0f s)" % (len(ok), time.time() - t), flush=True)
    lib, skipped = [], defaultdict(int)
    for k, (fid, fl) in enumerate(df.groupby("floor_id")):
        fl = fl.assign(g=[H.wkt.loads(s) for s in fl.geometry])
        for uid, u in fl[fl.unit_id.isin(ok.index)].groupby("unit_id"):
            ar = [r for r in u[u.entity_type == "area"].itertuples() if H.KIND.get(r.entity_subtype) in NOMAD_KIND]
            if not ar:
                skipped["no rooms"] += 1; continue
            rooms = [(NOMAD_KIND[H.KIND[r.entity_subtype]], r.g) for r in ar if r.g.geom_type == "Polygon"]
            op = u[u.entity_type == "opening"]
            try:
                sq = square_flat(rooms, list(op[op.entity_subtype == "WINDOW"].g), list(op[op.entity_subtype == "ENTRANCE_DOOR"].g),
                                 list(op[op.entity_subtype == "DOOR"].g))
            except Exception:
                sq = None
            if not sq:
                skipped["not rectilinear"] += 1; continue
            beds = [r for r in sq["rooms"] if r["kind"] == "bed"]
            if beds:
                max(beds, key=lambda r: r["area"])["kind"] = "bed_main"
            o = ok.loc[uid]
            sq.update(id=int(uid), bedrooms=int(o.bedrooms), useful=round(sum(r["area"] for r in sq["rooms"]), 1),
                      ground=bool(u.elevation.min() < 1.0))
            sides = defaultdict(float)
            for w in sq["windows"]:
                sides[w["side"]] += w["w"]
            sq["lit"] = sorted(s for s, v in sides.items() if s != "inside" and v >= 0.6)
            lib.append(sq)
        if k % 500 == 0:
            print("  floor %d: %d in the library (%.0f s)" % (k, len(lib), time.time() - t), flush=True)
    json.dump(lib, open(OUT / "library.json", "w"), separators=(",", ":"))
    L = pd.DataFrame([{"bedrooms": f["bedrooms"], "lit": "+".join(f["lit"]), "entrance": (f["entrance"] or {}).get("side"),
                       "W": f["W"], "D": f["D"], "ground": f["ground"]} for f in lib])
    summ = {"flats_in": int(len(ok)), "in_library": int(len(L)), "skipped": dict(skipped),
            "by_bedrooms": L.bedrooms.value_counts().to_dict(), "lit_sides": L.lit.value_counts().head(8).to_dict(),
            "entrance_side": L.entrance.value_counts().to_dict(),
            "one_side_lit": {"all": int((L.lit == "front").sum()),
                             "entrance_back": int(((L.lit == "front") & (L.entrance == "back")).sum()),
                             "entrance_front": int(((L.lit == "front") & (L.entrance == "front")).sum()),
                             "entrance_left_right": int(((L.lit == "front") & L.entrance.isin(["left", "right"])).sum())},
            "front_and_back_lit": int((L.lit == "back+front").sum()),
            "W_median": float(L.W.median()), "D_median": float(L.D.median()), "minutes": round((time.time() - t) / 60, 1)}
    json.dump(summ, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
