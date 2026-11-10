"""Nomad - the data behind the NOMAD website, gathered from NOMAD's own result files, nothing typed in.

Writes site/data/nomad.json (rule cards, experiments, golden set), site/data/premises.json (every empty ground-floor
premises with its zone and street life), site/data/basemap.json (Barcelona's zones, merged and simplified to 3 m) and
the 3D city (site/data/city, from the Catastro). The layout engine's data (demo shops, real-shop runs, Pyodide engine)
was parked on 9 Nov 2026: see PARKED.md and the branch parked/before-cleanup.
Run after the stages:  .venv/Scripts/python src/app/build_site.py
"""
import csv, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
R = ROOT / "results"



def j(p):
    return json.load(open(p, encoding="utf-8"))


def premises():
    rows = []
    av = {}
    ap = R / "avoid" / "avoid.csv"                            # src/check/avoid.py: shops within 100 m (street life)
    if ap.exists():
        for v in csv.DictReader(open(ap, encoding="utf-8")):
            av[v["ID_Global"]] = v
    with open(R / "zoning" / "empty_premises_zoning.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a = av.get(r["ID_Global"], {})
            rows.append([round(float(r["X_UTM_ETRS89"])), round(float(r["Y_UTM_ETRS89"])), r["Nom_Via"],
                         str(r["Num_Policia_Inicial"]).split(".")[0], r["Nom_Barri"], r["Nom_Districte"], r["Referencia_Cadastral"],
                         r["zone"], r["pgm_key"], r["housing"], r["why"], r["Nom_Activitat"].replace("Locals buits en ", ""),
                         int(a["retail_100m"]) if a.get("retail_100m") else None])
    # no prices (idealista18 removed), no daylight prediction (Exp 4 dropped), no home counts (layouts parked)
    return {"cols": ["x", "y", "street", "num", "barri", "district", "ref", "zone", "key", "housing", "why", "offer", "shops"], "rows": rows}


def basemap():
    from shapely.geometry import shape, Polygon
    from shapely.ops import unary_union
    F = j(ROOT / "data" / "barcelona" / "zoning" / "muc_qualificacio_bcn.geojson")["features"]

    def kind(c):
        c = c or ""
        if c.startswith("SX"):
            return None
        if c.startswith(("SV", "N")):
            return "green"
        if c.startswith(("R", "M1", "M3", "SD")) or c == "M2":
            return "res"
        return "other"
    groups = {}
    for f in F:
        k = kind(f["properties"]["C_QUAL_MUC"])
        if k:
            groups.setdefault(k, []).append(shape(f["geometry"]).buffer(0))
    out = {}
    for k, gs in groups.items():
        u = unary_union(gs).simplify(3.0, preserve_topology=True)
        rings = []
        for p in (u.geoms if u.geom_type == "MultiPolygon" else [u]):
            if p.area < 60:
                continue
            rings.append([[round(x), round(y)] for x, y in p.exterior.coords])
            rings += [[[round(x), round(y)] for x, y in h.coords] for h in p.interiors if Polygon(h).area > 200]
        out[k] = rings
    return out


def city(tile=1000.0):
    """The 3D city: every Catastro building part with floors (INSPIRE Buildings, src/building/catastro_buildings.py), in
    1 km tiles the page loads around the camera. Footprints simplified to 0,4 m, as 16-bit decimetres from the tile corner;
    height = 4 m ground floor + 3 m per upper floor (the Catastro gives floors, not metres). Also the street façade of every
    empty shop (src/building/real_shops.py), coloured by its zoning answer, for the ground-floor band."""
    import base64, gzip, math, struct
    from shapely.geometry import Polygon, Point, shape
    from shapely.strtree import STRtree
    B = json.load(gzip.open(ROOT / "data" / "barcelona" / "catastro" / "buildings.json.gz", "rt", encoding="utf-8"))
    # typology of each building = the PGM zone it stands in (MUC), and its NOMAD status (empty shops + real-shop run)
    Z = j(ROOT / "data" / "barcelona" / "zoning" / "muc_qualificacio_bcn.geojson")["features"]
    zg = [shape(f["geometry"]).buffer(0) for f in Z]
    ztree = STRtree(zg)

    def typology(code, name):
        code, name = code or "", name or ""
        for start, t in (("Nucli", 0), ("Densificació Urbana Intensiva", 1), ("Densificació Urbana Semi", 2), ("Conservació", 3),
                         ("Renovació", 4), ("Remodelació", 4), ("Ordenació en volumetria", 5), ("Residencial en vol", 5),
                         ("Ordenació en edif", 6), ("Zona d'activitats", 7), ("Zona industrial", 8), ("Terciari", 8)):
            if name.startswith(start):
                return t
        return 9 if code.startswith("S") else 10
    status = {}
    for r in csv.DictReader(open(R / "zoning" / "empty_premises_zoning.csv", encoding="utf-8")):
        ref = (r["Referencia_Cadastral"] or "")[:14]
        order = {"YES": 3, "CHECK": 2, "NO": 1}
        if order.get(r["housing"], 0) > order.get(status.get(ref, ["", 0])[0], 0):
            status[ref] = [r["housing"], 0]
    # (until 9 Nov 2026 the layout engine's answer and home count replaced the zone's here: parked, see PARKED.md)
    tiles = {}
    for ref, b in B.items():
        for p in b["parts"]:
            up = p["up"] or 0
            if up < 1:
                continue
            for poly in p["poly"]:
                g = Polygon(poly[0])
                if not g.is_valid or g.area < 4:
                    continue
                g = g.simplify(0.4, preserve_topology=True)
                c = g.representative_point()
                key = (int(c.x // tile), int(c.y // tile))
                t = tiles.setdefault(key, {"parts": [], "refs": {}})
                bi = t["refs"].setdefault(ref, len(t["refs"]))
                t["parts"].append((bi, up, list(g.exterior.coords)[:-1]))
    # trees (Open Data BCN: street, zone and park trees, CC BY 4.0): size class 0-4 from categoria_arbrat, 5 = palm
    size = {"EXEMPLAR": 4, "PRIMERA": 3, "SEGONA": 2, "TERCERA": 1}
    ntree = 0
    for f in sorted((ROOT / "data" / "barcelona" / "trees").glob("trees_*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            try:
                x, y = float(r["x"]), float(r["y"])
            except ValueError:
                continue
            k = 5 if r["palm"] == "1" else size.get(r["size"], 0)
            t = tiles.setdefault((int(x // tile), int(y // tile)), {"parts": [], "refs": {}})
            t.setdefault("trees", []).append((x, y, k))
            ntree += 1
    out = SITE / "data" / "city"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    index, total = [], 0
    for (tx, ty), t in tiles.items():
        x0, y0 = tx * tile, ty * tile
        counts, heights, bids, coords = [], [], [], []
        for bi, up, ring in t["parts"]:
            counts.append(len(ring))
            heights.append(up)
            bids.append(bi)
            for x, y in ring:
                coords += [max(-32768, min(32767, int(round((x - x0) * 10)))), max(-32768, min(32767, int(round((y - y0) * 10))))]
        meta = []
        for r in sorted(t["refs"], key=t["refs"].get):
            fp = [Polygon(p[0]) for p in B[r]["foot"] if len(p[0]) >= 3]
            c = max(fp, key=lambda g: g.area).representative_point() if fp else None
            zi = next((int(i) for i in ztree.query(c, predicate="intersects")), None) if c else None
            typ = typology(Z[zi]["properties"]["C_QUAL_MUC"], Z[zi]["properties"]["D_QUAL_AJT"]) if zi is not None else 10
            meta.append([r, B[r]["use"], B[r]["dwellings"], max([q["up"] or 0 for q in B[r]["parts"]] or [0]), typ] + status.get(r, ["", 0]))
        trees = t.get("trees", [])
        tx_ = [max(-32768, min(32767, int(round(v)))) for x, y, k in trees for v in ((x - x0) * 10, (y - y0) * 10)]
        data = {"x0": x0, "y0": y0, "n": counts, "up": heights, "bid": bids, "b": meta,
                "xy": base64.b64encode(struct.pack("<%dh" % len(coords), *coords)).decode(),
                "tr": base64.b64encode(struct.pack("<%dh" % len(tx_), *tx_)).decode(), "tk": "".join(str(k) for _, _, k in trees)}
        name = "t_%d_%d.json" % (tx, ty)
        (out / name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        index.append([tx, ty, len(counts)])
        total += (out / name).stat().st_size
    # empty shops: street façade segments with their answer, for the ground-floor band in 3D
    S = j(R / "real_shops" / "shells.json")
    m = list(csv.DictReader(open(R / "real_shops" / "clean_shops.csv", encoding="utf-8")))
    shops = []
    for r in m:
        s = S.get(r["ref14"])
        if not s:
            continue
        ox, oy = s["origin_utm"]
        for a, c in s["street"]:
            shops.append([round(a[0] + ox, 1), round(a[1] + oy, 1), round(c[0] + ox, 1), round(c[1] + oy, 1),
                          r["housing"] if r["kept"] == "True" else "REMOVED", r["ref14"]])
    json.dump({"tile": tile, "tiles": index, "shops": shops}, open(out / "index.json", "w", encoding="utf-8"), separators=(",", ":"))
    # ground layers from the MUC categories, merged and simplified to 1,5 m
    LAYERS = [("road_main", lambda c, n: c.startswith("SX1")),
              ("path", lambda c, n: n.startswith(("Vies cíviques", "Xarxa viària peatonal", "Xarxa viària en zona verda"))),
              ("road", lambda c, n: c.startswith("SX")),
              ("forest", lambda c, n: n.startswith("Parc forestal") or c.startswith("N")),
              ("park", lambda c, n: c.startswith("SV") or n.startswith(("Verd privat", "Zona verda", "Parcs i jardins"))),
              ("rail", lambda c, n: c.startswith("SF")),
              ("water", lambda c, n: c.startswith(("SH", "SP", "SC"))),
              ("facility", lambda c, n: c.startswith(("SE", "SD", "ST", "SS"))),
              ("zone_yes", lambda c, n: c.startswith(("R1", "R2", "M2")) or n.startswith("Renovació urbana: rehabilitació")),
              ("zone_check", lambda c, n: c.startswith(("R4", "R6", "M3", "M1"))),
              ("zone_no", lambda c, n: True)]
    from shapely.ops import unary_union
    groups = {k: [] for k, _ in LAYERS}
    for f, g in zip(Z, zg):
        c, n = f["properties"]["C_QUAL_MUC"] or "", f["properties"]["D_QUAL_AJT"] or ""
        k = next(k for k, test in LAYERS if test(c, n))
        groups[k].append(g)
    lay = {}
    for k, gs in groups.items():
        u = unary_union(gs).simplify(1.5, preserve_topology=True) if gs else None
        rings = []
        for p in (u.geoms if u is not None and u.geom_type == "MultiPolygon" else [u] if u is not None else []):
            if p.area < 30:
                continue
            rings.append([[round(x, 1), round(y, 1)] for x, y in p.exterior.coords])
            rings += [[[round(x, 1), round(y, 1)] for x, y in h.coords] for h in p.interiors if Polygon(h).area > 80]
        lay[k] = rings
    json.dump(lay, open(out / "layers.json", "w", encoding="utf-8"), separators=(",", ":"))
    print("city: %d tiles, %d parts, %d trees, %.1f MB + layers %.1f MB" % (len(index), sum(i[2] for i in index), ntree, total / 1e6,
                                                                         (out / "layers.json").stat().st_size / 1e6))


def experiments():
    ev = j(R / "plan_reading" / "eval_summary.json")["scale given"]
    race = {}
    for f in (R / "plan_reading" / "compare").glob("test_plans_messy__*.json"):
        race[f.stem.split("__")[1]] = j(f)["scale given"]["area_within_10pct"]
    scans = {}
    for f in (R / "plan_reading" / "compare").glob("test_plans_cubicasa__*.json"):
        s = j(f)["scale given"]
        scans[f.stem.split("__")[1]] = {"median_iou": s["median_iou"], "area10": s["area_within_10pct"], "plans": s["plans"]}
    head = {r["metric"]: float(r["value"]) for r in csv.DictReader(open(R / "dashboard" / "dashboard_data" / "headline.csv", encoding="utf-8"))}
    return {"reader": {"median_iou": ev["median_iou"], "area10": ev["area_within_10pct"], "race_messy": race, "real_scans": scans},
            "zoning": j(R / "zoning" / "summary.json"),
            "rules": {"pieces": int(head["rulebook_pieces"]), "norms": int(head["norms"]), "flats_all_pass": head["flats_all_pass"]},
            "golden": j(R / "eval" / "golden_summary.json")}


def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    data = {"rules": j(ROOT / "rules" / "rules.json"), "experiments": experiments()}
    json.dump(data, open(SITE / "data" / "nomad.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(premises(), open(SITE / "data" / "premises.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(basemap(), open(SITE / "data" / "basemap.json", "w", encoding="utf-8"), separators=(",", ":"))
    city()
    tot = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print("site data: %d rules, %.1f MB in site/" % (len(data["rules"]), tot / 1e6))


if __name__ == "__main__":
    main()
