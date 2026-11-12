"""Nomad - what makes a real flat habitable: measured on the 13,444 Swiss Dwellings flats that pass every NOMAD rule.

For each flat (results/rule_tests/sd_units.csv: residential, all rules pass, 0-3 bedrooms) from its rooms, walls,
doors, windows, entrance door and fixtures (data/datasets/swiss_dwellings, CC BY 4.0):
  space      useful area; share of living / bedrooms / kitchen / bath / circulation / storage; tiny leftover rooms
  entrance   which room the front door opens into, and what is on the other side (common stair or corridor, or outside)
  doors      the room graph: what each bedroom, bathroom and kitchen is reached from; rooms you must walk through
             to reach another room; open or closed kitchen
  windows    which room types have a window; window width per m² of floor; rooms without one
  shape      each room's width (short side), proportion, how rectangular it is
  corridor   width, length, share of the flat, doors along it
  depth      how far the flat reaches from its windows
  wet core   kitchen and bathroom sharing a wall
Out: results/habitability/units.csv, rooms.csv, summary.json
Run: .venv/Scripts/python src/learn/habitability.py [limit]
"""
import json, math, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "data" / "datasets" / "swiss_dwellings" / "swiss-dwellings-v3.0.0" / "geometries.csv"
OUT = ROOT / "results" / "habitability"
KIND = {"LIVING_ROOM": "living", "LIVING_DINING": "living", "DINING": "living", "KITCHEN_DINING": "living",
        "BEDROOM": "bedroom", "ROOM": "bedroom", "KITCHEN": "kitchen", "BATHROOM": "bath", "SANITARY_ROOMS": "bath",
        "TOILET": "bath", "CORRIDOR": "circulation", "CORRIDORS_AND_HALLS": "circulation", "LOBBY": "circulation",
        "FOYER": "circulation", "STOREROOM": "storage", "CLOAKROOM": "storage", "WASH_AND_DRY_ROOM": "storage",
        "BALCONY": "outdoor", "LOGGIA": "outdoor", "TERRACE": "outdoor", "WINTERGARTEN": "outdoor", "GARDEN": "outdoor",
        "PATIO": "outdoor", "SHAFT": "shaft", "VOID": "void", "LIGHTWELL": "void", "OUTDOOR_VOID": "void"}
COMMON = {"STAIRCASE", "CORRIDOR", "CORRIDORS_AND_HALLS", "LOBBY", "FOYER", "ELEVATOR"}
OUTSIDE = {"BALCONY", "LOGGIA", "TERRACE", "GARDEN", "PATIO", "WINTERGARTEN", "OUTDOOR_VOID"}


def load(limit=None):
    U = pd.read_csv(ROOT / "results" / "rule_tests" / "sd_units.csv")
    ok = U[(U.usage == "RESIDENTIAL") & U.all_pass & (U.bedrooms <= 3)].set_index("unit_id")
    if limit:
        ok = ok.head(limit)
    want_units = set(ok.index)
    floors = set()
    for ch in pd.read_csv(G, usecols=["unit_id", "floor_id"], chunksize=1000000):
        floors |= set(ch[ch.unit_id.isin(want_units)].floor_id)
    parts = [ch[ch.floor_id.isin(floors)] for ch in pd.read_csv(G, chunksize=500000, usecols=[
        "floor_id", "unit_id", "unit_usage", "entity_type", "entity_subtype", "geometry", "elevation"])]
    return ok, pd.concat(parts, ignore_index=True)


def width_of(g):
    """Short side of the minimum rotated rectangle (a room's clear width), long side, and how much of it the room fills."""
    r = g.minimum_rotated_rectangle
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return min(a, b), max(a, b), g.area / max(r.area, 1e-9)


def clear(g):
    """Clear width: the widest circle that fits (a corridor's or a room's real usable width)."""
    import shapely
    return 2 * shapely.maximum_inscribed_circle(g, 0.02).length if hasattr(shapely, "maximum_inscribed_circle") else 2 * g.area / max(g.length, 1e-9)


def analyse_floor(fl, ok):
    out_u, out_r = [], []
    geo = [wkt.loads(s) for s in fl.geometry]
    fl = fl.assign(g=geo)
    areas = fl[fl.entity_type == "area"]
    tree = STRtree(list(areas.g))
    a_rows = list(areas.itertuples())
    footprint = unary_union([g.buffer(0.15) for g in areas.g]).buffer(-0.1)      # the floor, walls included
    for uid, u in fl[fl.unit_id.isin(ok.index)].groupby("unit_id"):
        rooms = [r for r in u[u.entity_type == "area"].itertuples()]
        if not rooms:
            continue
        ix = {id(r): k for k, r in enumerate(rooms)}
        kinds = [KIND.get(r.entity_subtype, "other") for r in rooms]
        geoms = [r.g for r in rooms]
        rtree = STRtree(geoms)
        touch = lambda g: [int(i) for i in rtree.query(g.buffer(0.2)) if geoms[int(i)].distance(g) < 0.2]
        # ---- doors: which rooms each door joins
        adj = defaultdict(set)
        door_w = []
        for i, gi in enumerate(geoms):                     # open connections: two rooms touching with no wall between
            for j in rtree.query(gi.buffer(0.05)):
                j = int(j)
                if j != i and gi.distance(geoms[j]) < 0.05 and gi.buffer(0.05).intersection(geoms[j].buffer(0.05)).area > 0.05:
                    adj[i].add(j); adj[j].add(i)
        for d in u[(u.entity_type == "opening") & (u.entity_subtype == "DOOR")].itertuples():
            t = touch(d.g)
            door_w.append(width_of(d.g)[1])
            for i in t:
                for j in t:
                    if i != j:
                        adj[i].add(j)
        # ---- entrance: the room it opens into and what is outside it
        ent_in, ent_out = None, None
        for d in u[(u.entity_type == "opening") & (u.entity_subtype == "ENTRANCE_DOOR")].itertuples():
            t = touch(d.g)
            if t:
                ent_in = rooms[t[0]].entity_subtype
            outside = [a_rows[int(i)] for i in tree.query(d.g.buffer(0.3)) if a_rows[int(i)].unit_id != uid
                       and a_rows[int(i)].g.distance(d.g) < 0.3]
            ent_out = ("common " + outside[0].entity_subtype.lower()) if outside and outside[0].entity_subtype in COMMON else \
                      ("outdoor " + outside[0].entity_subtype.lower()) if outside and outside[0].entity_subtype in OUTSIDE else \
                      ("other unit" if outside else "outside the building")
            break
        # ---- windows: which rooms, and on the outer wall of the floor
        win = defaultdict(float)
        for w in u[(u.entity_type == "opening") & (u.entity_subtype == "WINDOW")].itertuples():
            t = touch(w.g)
            if t:
                win[t[0]] += width_of(w.g)[1]
        fix = Counter()
        for f in u[u.entity_type == "feature"].itertuples():
            t = [i for i in rtree.query(f.g.centroid) if geoms[int(i)].contains(f.g.centroid)]
            if t:
                fix[(int(t[0]), f.entity_subtype)] += 1
        # ---- graph from the entrance: which room each room is reached from
        start = next((i for i, r in enumerate(rooms) if r.entity_subtype == ent_in), None)
        parent, order = {}, []
        if start is not None:
            parent[start] = None
            q = [start]
            while q:
                i = q.pop(0); order.append(i)
                for j in sorted(adj[i], key=lambda j: kinds[j] != "circulation"):      # prefer reaching rooms via circulation
                    if j not in parent:
                        parent[j] = i; q.append(j)
        through = [i for i in parent if parent[i] is not None and kinds[parent[i]] in ("bedroom",) ]
        useful = [i for i, k in enumerate(kinds) if k in ("living", "bedroom", "kitchen", "bath", "circulation", "storage", "other")]
        tot = sum(geoms[i].area for i in useful) or 1
        share = Counter()
        for i in useful:
            share[kinds[i]] += geoms[i].area / tot
        # depth: farthest point of the flat from any window
        wins = [w.g for w in u[(u.entity_type == "opening") & (u.entity_subtype == "WINDOW")].itertuples()]
        flat = unary_union([geoms[i] for i in useful])
        depth = None
        if wins and not flat.is_empty:
            wu = unary_union(wins)
            pts = [p for g in ([flat] if flat.geom_type == "Polygon" else flat.geoms) for p in g.exterior.coords]
            depth = max(Point(p).distance(wu) for p in pts)
        kit = [i for i, k in enumerate(kinds) if k == "kitchen"]
        kit_feat = [i for (i, s), n in fix.items() if s == "KITCHEN"]
        open_kitchen = any(kinds[i] == "living" for i in kit_feat) and not kit
        baths = [i for i, k in enumerate(kinds) if k == "bath"]
        wet = any(geoms[a].distance(geoms[b]) < 0.35 for a in kit + [i for i in kit_feat if kinds[i] != "kitchen"] for b in baths)
        on_facade = lambda i: geoms[i].buffer(0.5).intersects(footprint.exterior) if footprint.geom_type == "Polygon" else \
            any(geoms[i].buffer(0.5).intersects(p.exterior) for p in footprint.geoms)
        for i in useful:
            w_, l_, fill = width_of(geoms[i])
            out_r.append({"unit_id": uid, "type": rooms[i].entity_subtype, "kind": kinds[i], "area_m2": round(geoms[i].area, 2), "clear_width_m": round(clear(geoms[i]), 2),
                          "width_m": round(w_, 2), "length_m": round(l_, 2), "rect_fill": round(fill, 3),
                          "window_m": round(win.get(i, 0.0), 2), "doors": len(adj[i]),
                          "reached_from": kinds[parent[i]] if parent.get(i) is not None else ("entrance" if i == start else "not reached"),
                          "walk_through": sum(1 for j in parent if parent[j] == i) if kinds[i] in ("bedroom", "living") else 0,
                          "on_facade": bool(on_facade(i))})
        circ = [i for i in useful if kinds[i] == "circulation"]
        o = ok.loc[uid]
        out_u.append({"unit_id": uid, "bedrooms": int(o.bedrooms), "useful_m2": round(tot, 1),
                      **{"share_" + k: round(share.get(k, 0), 3) for k in ("living", "bedroom", "kitchen", "bath", "circulation", "storage", "other")},
                      "entrance_into": ent_in, "entrance_from": ent_out, "open_kitchen": bool(open_kitchen), "kitchen_room": bool(kit),
                      "wet_core": bool(wet), "rooms_walked_through": len(set(parent[i] for i in through)),
                      "bedrooms_via_living": sum(1 for i in parent if kinds[i] == "bedroom" and parent[i] is not None and kinds[parent[i]] == "living"),
                      "bedrooms_via_circulation": sum(1 for i in parent if kinds[i] == "bedroom" and parent[i] is not None and kinds[parent[i]] == "circulation"),
                      "baths_via_bedroom": sum(1 for i in parent if kinds[i] == "bath" and parent[i] is not None and kinds[parent[i]] == "bedroom"),
                      "corridor_m2": round(sum(geoms[i].area for i in circ), 1),
                      "corridor_width_m": round(min(clear(geoms[i]) for i in circ), 2) if circ else None,
                      "elevation_m": round(float(u.elevation.min()), 1), "ground_floor": bool(u.elevation.min() < 1.0),
                      "doors": len(door_w), "door_width_m": round(float(np.median(door_w)), 2) if door_w else None,
                      "depth_from_window_m": round(depth, 1) if depth is not None else None,
                      "tiny_rooms": sum(1 for i in useful if geoms[i].area < 2.0 and kinds[i] not in ("bath", "storage"))})
    return out_u, out_r


def main(limit=None):
    t = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    ok, df = load(limit)
    print("flats %d, rows on their floors %d (%.0f s)" % (len(ok), len(df), time.time() - t), flush=True)
    U, R = [], []
    for k, (fid, fl) in enumerate(df.groupby("floor_id")):
        try:
            a, b = analyse_floor(fl, ok)
            U += a; R += b
        except Exception as e:
            print("floor", fid, e, flush=True)
        if k % 500 == 0:
            print("  floor %d, flats %d (%.0f s)" % (k, len(U), time.time() - t), flush=True)
    pd.DataFrame(U).to_csv(OUT / "units.csv", index=False)
    pd.DataFrame(R).to_csv(OUT / "rooms.csv", index=False)
    print("done: %d flats, %d rooms, %.0f min" % (len(U), len(R), (time.time() - t) / 60))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
