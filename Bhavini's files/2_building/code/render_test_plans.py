"""Nomad - make test plans with known answers for the plan reader.

For each clean shop in 7_floor_plans/output/clean/nomad_shells.json we draw the real Swiss Dwellings geometry of that
unit as a normal architectural plan image: walls filled black, windows as thin triple lines in a white
gap, doors as a white gap with a swing arc. The reader then gets only the image; the true outline,
façade length, area and scale are kept in truth.json to grade it.
Outputs: 7_floor_plans/input/datasets/test_plans/<shell_id>.png and truth.json
"""
import json, math, os
import pandas as pd
import shapely
import pymupdf

SRC = "7_floor_plans/input/datasets/swiss_dwellings/swiss-dwellings-v3.0.0/geometries.csv"
OUT = "7_floor_plans/input/datasets/test_plans"
PX_PER_M = 40.0
MARGIN_M = 1.5


def main(limit=None):
    os.makedirs(OUT, exist_ok=True)
    shells = json.load(open("7_floor_plans/output/clean/nomad_shells.json", encoding="utf-8"))["shells"][:limit]
    floors = set(s["floor_id"] for s in shells)
    keep = []
    cols = ["unit_id", "floor_id", "entity_type", "entity_subtype", "geometry", "unit_usage"]
    for ch in pd.read_csv(SRC, usecols=cols, chunksize=500_000):
        keep.append(ch[ch.floor_id.isin(floors)])
    df = pd.concat(keep, ignore_index=True)
    df["geom"] = shapely.from_wkt(df.geometry.values)
    truth = {}
    for s in shells:
        fl = df[df.floor_id == s["floor_id"]]
        unit_areas = fl[(fl.entity_type == "area") & (fl.unit_id == s["shell_id"])]
        shell = shapely.unary_union([p.buffer(0.15, join_style="mitre") for p in unit_areas.geom]).buffer(-0.15, join_style="mitre")
        if shell.geom_type != "Polygon":
            shell = max(shell.geoms, key=lambda p: p.area)
        zone = shell.buffer(0.45, join_style="mitre")
        walls = [g.intersection(zone) for g in fl[fl.entity_type == "separator"].geom if g.intersects(zone)]
        wins = [g for g, st in zip(fl.geom, fl.entity_subtype) if st == "WINDOW" and g.intersects(zone)]
        doors = [g for g, st in zip(fl.geom, fl.entity_subtype) if st in ("DOOR", "ENTRANCE_DOOR") and g.intersects(zone)]
        minx, miny, maxx, maxy = zone.bounds
        W = (maxx - minx + 2 * MARGIN_M) * PX_PER_M
        H = (maxy - miny + 2 * MARGIN_M) * PX_PER_M
        T = lambda x, y: pymupdf.Point((x - minx + MARGIN_M) * PX_PER_M, (maxy - y + MARGIN_M) * PX_PER_M)
        doc = pymupdf.open()
        page = doc.new_page(width=W, height=H)

        def poly(g, **kw):
            for p in getattr(g, "geoms", [g]):
                if p.geom_type == "Polygon" and p.area > 1e-4:
                    page.draw_polyline([T(*c) for c in p.exterior.coords], closePath=True, **kw)

        for g in walls:
            poly(g, color=None, fill=(0, 0, 0))
        for g in wins:                                  # white gap + three thin lines along the window
            poly(g, color=None, fill=(1, 1, 1))
            r = shapely.minimum_rotated_rectangle(g)
            c = list(r.exterior.coords)[:4]
            e = [(c[i], c[(i + 1) % 4]) for i in range(4)]
            long1, long2 = sorted(e, key=lambda ab: -math.dist(*ab))[:2]
            for t in (0.0, 0.5, 1.0):
                a = (long1[0][0] + t * (long2[1][0] - long1[0][0]), long1[0][1] + t * (long2[1][1] - long1[0][1]))
                b = (long1[1][0] + t * (long2[0][0] - long1[1][0]), long1[1][1] + t * (long2[0][1] - long1[1][1]))
                page.draw_line(T(*a), T(*b), color=(0, 0, 0), width=2)
        door_w = []
        for g in doors:
            poly(g, color=None, fill=(1, 1, 1))
            r = shapely.minimum_rotated_rectangle(g)
            c = list(r.exterior.coords)[:4]
            sides = sorted(math.dist(c[i], c[(i + 1) % 4]) for i in range(4))
            door_w.append(sides[-1])
            a, b = c[0], (c[1] if math.dist(c[0], c[1]) >= math.dist(c[1], c[2]) else c[3])
            if sides[-1] <= 1.6:                        # quarter-circle swing, like a drawn door
                page.draw_sector(T(*a), T(*b), 90, color=(0.5, 0.5, 0.5), width=0.6, fullSector=False)
        page.get_pixmap(dpi=72).save(f"{OUT}/{s['shell_id']}.png")
        ext = list(shell.exterior.coords)
        truth[s["shell_id"]] = {"px_per_m": PX_PER_M, "area_m2": round(shell.area, 1), "facade_m": s["facade_m"],
                                "windows": len(wins), "doors": len(doors),
                                "median_door_m": round(sorted(door_w)[len(door_w) // 2], 2) if door_w else None,
                                "origin_px": [(-minx + MARGIN_M) * PX_PER_M, (maxy + MARGIN_M) * PX_PER_M],
                                "outline_m": [[round(x, 3), round(y, 3)] for x, y in ext]}
    json.dump(truth, open(f"{OUT}/truth.json", "w"), indent=0)
    print("rendered", len(truth), "test plans into", OUT)


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
