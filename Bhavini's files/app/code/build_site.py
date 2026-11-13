"""Nomad - Stage 8: the data behind the NOMAD website (app/), gathered from NOMAD's own result files, nothing typed in.

Writes app/data/nomad.json (pipeline, experiments, demo shops, rule cards, golden set, real shops), app/data/premises.json
(every empty ground-floor premises with its zone and answer), app/data/basemap.json (Barcelona's zones, merged and
simplified to 3 m), the 3D city (app/data/city, from the Catastro), the browser engine (app/py: NOMAD's Python for
Pyodide) and the real-shop outlines, and copies the demo pictures (smaller) and 3D models to app/img and app/models.
The page itself is app/index.html. Run after the stages:  .venv/Scripts/python app/code/build_site.py
"""
import csv, json, shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "app"
# titles: {passing} {asked} = the shop as it is, {most} = most homes over the iterations (filled from the recipe)
DEMOS = [("D1_shop_146519_YES", "A shop that already works"),
         ("D2_warehouse_154822_patio", "A deep warehouse: {passing} of {asked} homes fit, the back has no façade"),
         ("D3_large_shop_152418", "A large shop: {passing} homes as asked, {most} at most"), ("D0_plan_drawing_145057", "A plan drawing read by NOMAD"),
         ("D4_warehouse_154608_NO", "A narrow warehouse that cannot be housing")]


def j(p):
    return json.load(open(p, encoding="utf-8"))


def small(src, dst, w=900):
    """Copy a picture at most w px wide, as an optimised PNG."""
    if not Path(src).exists():
        return None
    im = Image.open(src).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.quantize(colors=192, method=Image.Quantize.MEDIANCUT).save(dst, optimize=True)
    return dst.relative_to(SITE).as_posix()


def card(c):
    return {"title": c["title"], "ok": bool(c["ok"]), "check": bool(c.get("check")), "value": c["value"],
            "limit": c.get("limit", ""), "cite": c["cite"], "scope": c["scope"]}


def demos():
    out = []
    for name, blurb in DEMOS:
        p = ROOT / "7_floor_plans/output/sheets" / "recipes" / (name + ".json")
        if not p.exists():
            continue
        c = j(p)["case"]
        b = c["before"]["res"]
        title = blurb.format(passing=b["flats_passing"], asked=b["flats_asked"],
                             most=max([it["homes"] for it in c["iterations"]] or [b["flats_passing"]]))
        d = {"id": name, "title": title, "mix": c["mix_text"], "shop_m2": b["shop_m2"], "source": c["shop"]["source"],
             "before": {"verdict": b["verdict"], "passing": b["flats_passing"], "asked": b["flats_asked"],
                        "cards": [card(x) for x in b["cards"]],
                        "plan": small(ROOT / "7_floor_plans/output/figures" / (name + "_p0_plan.png"), SITE / "img" / (name + "_p0.png"))},
             "iterations": []}
        for k, it in enumerate(c["iterations"], 1):
            r = it["res"]
            glb = ROOT / "7_floor_plans/output/model3d" / ("%s_it%d.glb" % (name, k))
            web = SITE / "models" / (glb.stem + ".gltf.json")       # the web host serves .json, not .glb:
            if glb.exists():                                          # the same glTF, geometry embedded as JSON
                import trimesh
                from trimesh.exchange.gltf import export_gltf
                web.parent.mkdir(parents=True, exist_ok=True)
                files = export_gltf(trimesh.load(glb), embed_buffers=True)
                web.write_bytes(files["model.gltf"])
            d["iterations"].append({
                "label": it["label"], "homes": it["homes"], "verdict": r["verdict"], "mix": r.get("mix_text", ""),
                "patio": bool(it["plan"].get("patios")), "interventions": it["plan"].get("interventions", []),
                "cards": [card(x) for x in r["cards"]],
                "plan": small(ROOT / "7_floor_plans/output/figures" / ("%s_p%d_plan.png" % (name, k)), SITE / "img" / ("%s_p%d.png" % (name, k))),
                "zoning3d": small(ROOT / "7_floor_plans/output/sheets" / ("%s_3d_%d.png" % (name, k)), SITE / "img" / ("%s_z%d.png" % (name, k)), 700),
                "walls3d": small(ROOT / "7_floor_plans/output/sheets" / ("%s_walls_%d.png" % (name, k)), SITE / "img" / ("%s_w%d.png" % (name, k)), 700),
                "glb": ("models/" + web.name) if glb.exists() else None,
                "ifc": glb.with_suffix(".ifc").name if glb.with_suffix(".ifc").exists() else None})
        out.append(d)
    return out


def premises():
    rows = []
    val = {}
    vp = ROOT / "8_report_and_city/output/value" / "premises_value.csv"                  # 8_report_and_city/code/value.py (idealista18 2018 asking prices, ODbL)
    if vp.exists():
        for v in csv.DictReader(open(vp, encoding="utf-8")):
            val[v["ID_Global"]] = (v["eur_m2_500m"], v["eur_m2_ground_800m"])
    av = {}
    ap = ROOT / "1_find_the_shops/output/avoid" / "avoid.csv"                            # 1_find_the_shops/code/avoid.py (avoid answers, Bars's daylight, shops nearby)
    if ap.exists():
        for v in csv.DictReader(open(ap, encoding="utf-8")):
            av[v["ID_Global"]] = v
    num = lambda x, k=1: round(float(x), k) if x not in ("", None) else None
    with open(ROOT / "1_find_the_shops/output/zoning" / "empty_premises_zoning.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = val.get(r["ID_Global"], ("", ""))
            a = av.get(r["ID_Global"], {})
            rows.append([round(float(r["X_UTM_ETRS89"])), round(float(r["Y_UTM_ETRS89"])), r["Nom_Via"],
                         str(r["Num_Policia_Inicial"]).split(".")[0], r["Nom_Barri"], r["Nom_Districte"], r["Referencia_Cadastral"],
                         r["zone"], r["pgm_key"], r["housing"], r["why"], r["Nom_Activitat"].replace("Locals buits en ", ""),
                         int(float(v[0])) if v[0] else None, int(float(v[1])) if v[1] else None,
                         a.get("answer"), a.get("why"), num(a.get("daylight_df")), num(a.get("lit_depth_m")),
                         int(a["retail_100m"]) if a.get("retail_100m") else None, int(float(a["homes"])) if a.get("homes") else None])
    return {"cols": ["x", "y", "street", "num", "barri", "district", "ref", "zone", "key", "housing", "why", "offer", "eur", "eurg",
                     "ans", "awhy", "df", "lit", "shops", "homes"], "rows": rows}


def basemap():
    from shapely.geometry import shape, Polygon
    from shapely.ops import unary_union
    F = j(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson")["features"]

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
    """The 3D city: every Catastro building part with floors (INSPIRE Buildings, 2_building/code/catastro_buildings.py), in
    1 km tiles the page loads around the camera. Footprints simplified to 0,4 m, as 16-bit decimetres from the tile corner;
    height = 4 m ground floor + 3 m per upper floor (the Catastro gives floors, not metres). Also the street façade of every
    empty shop (2_building/code/real_shops.py), coloured by its zoning answer, for the ground-floor band."""
    import base64, gzip, math, struct
    from shapely.geometry import Polygon, Point, shape
    from shapely.strtree import STRtree
    B = json.load(gzip.open(ROOT / "0_shared_input/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    # typology of each building = the PGM zone it stands in (MUC), and its NOMAD status (empty shops + real-shop run)
    Z = j(ROOT / "0_shared_input/zoning/muc_qualificacio_bcn.geojson")["features"]
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
    for r in csv.DictReader(open(ROOT / "1_find_the_shops/output/zoning" / "empty_premises_zoning.csv", encoding="utf-8")):
        ref = (r["Referencia_Cadastral"] or "")[:14]
        order = {"YES": 3, "CHECK": 2, "NO": 1}
        if order.get(r["housing"], 0) > order.get(status.get(ref, ["", 0])[0], 0):
            status[ref] = [r["housing"], 0]
    rp = ROOT / "2_building/output/real_shops" / "nomad_results.csv"
    if rp.exists():
        for r in csv.DictReader(open(rp, encoding="utf-8")):
            if r["as_is"] != "ERROR":
                status[r["ref"]] = [r["after"], int(r["most_homes"] or 0)]      # NOMAD's own answer replaces the zone's
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
    for f in sorted((ROOT / "app/input/trees").glob("trees_*.csv")):
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
    S = j(ROOT / "2_building/output/real_shops" / "shells.json")
    m = list(csv.DictReader(open(ROOT / "2_building/output/real_shops" / "clean_shops.csv", encoding="utf-8")))
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


def engine():
    """The browser engine: NOMAD's own Python files, read straight from the step folders by app/py/worker.js (Pyodide),
    Python's standard library as base64 JSON (the host serves no .zip), the learned room sizes, and the outlines of the
    clean real shops (2_building/code/clean_real_shops.py) that the requirements form can load by address."""
    import base64
    z = SITE / "py" / "python_stdlib.zip"
    if z.exists():
        json.dump({"b64": base64.b64encode(z.read_bytes()).decode()}, open(SITE / "py" / "python_stdlib.json", "w"))
    S = j(ROOT / "2_building/output/real_shops" / "shells.json")
    keep = {r["ref14"]: r for r in csv.DictReader(open(ROOT / "2_building/output/real_shops" / "clean_shops.csv", encoding="utf-8")) if r["kept"] == "True"}
    out = {ref: dict({"outline": s["outline"], "facade": s["facade"], "street": s["street"], "floors": s["floors"],
                      "shared": s["premises_in_building"] > 1, "label": keep[ref]["label"]},
                     **({"existing": s["existing"]} if s.get("existing") else {}),          # the building's portal / stair
                     **{k: s.get(k, []) for k in ("patios", "wells_above")})                # light wells (light_wells.py)
           for ref, s in S.items() if ref in keep}
    json.dump(out, open(SITE / "data" / "shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    demo = {}
    for name, _ in DEMOS:                                      # the five test shops, for the design form
        p = ROOT / "7_floor_plans/output/sheets" / "recipes" / (name + ".json")
        if p.exists():
            sh = j(p)["case"]["shop"]
            demo[name] = {"outline": sh["outline"], "facade": sh["facade"], "height": sh["height"]}
    json.dump(demo, open(SITE / "data" / "demo_shops.json", "w", encoding="utf-8"), separators=(",", ":"))
    print("engine: %d modules, %d real shop outlines, %d test shops" % (14, len(out), len(demo)))


def real():
    """The real-shop analysis (2_building/code/run_real_shops.py) for the page: totals, by district, every shop's answer."""
    p = ROOT / "2_building/output/real_shops" / "summary_nomad.json"
    if not p.exists():
        return None
    rows = list(csv.DictReader(open(ROOT / "2_building/output/real_shops" / "nomad_results.csv", encoding="utf-8")))
    return {"summary": j(p), "cleaning": j(ROOT / "2_building/output/real_shops" / "cleaning_report.json"), "buildings": j(ROOT / "2_building/output/real_shops" / "summary.json"),
            "shops": [[r["ref"], r["address"], r["barri"], r["district"], r["ground_m2"], r["street_facade_m"], r["as_is"],
                       r["after"], r["after_passing"], r["most_homes"]] for r in rows if r["as_is"] != "ERROR"]}


def experiments():
    ev = j(ROOT / "2_building/output/plan_reading" / "eval_summary.json")["scale given"]
    race = {}
    for f in (ROOT / "2_building/output/plan_reading" / "compare").glob("test_plans_messy__*.json"):
        race[f.stem.split("__")[1]] = j(f)["scale given"]["area_within_10pct"]
    scans = {}
    for f in (ROOT / "2_building/output/plan_reading" / "compare").glob("test_plans_cubicasa__*.json"):
        s = j(f)["scale given"]
        scans[f.stem.split("__")[1]] = {"median_iou": s["median_iou"], "area10": s["area_within_10pct"], "plans": s["plans"]}
    it = j(ROOT / "7_floor_plans/output/generation" / "iterations_summary.json")
    head = {r["metric"]: float(r["value"]) for r in csv.DictReader(open(ROOT / "8_report_and_city/output/dashboard" / "dashboard_data" / "headline.csv", encoding="utf-8"))}
    return {"reader": {"median_iou": ev["median_iou"], "area10": ev["area_within_10pct"], "race_messy": race, "real_scans": scans},
            "zoning": j(ROOT / "1_find_the_shops/output/zoning" / "summary.json"),
            "rules": {"pieces": int(head["rulebook_pieces"]), "norms": int(head["norms"]), "flats_all_pass": head["flats_all_pass"]},
            "check": {"verdicts": it["stage5_flags_as_it_is"], "iterations": it["iterations"],
                      "strategies": j(ROOT / "7_floor_plans/output/generation" / "compare_v2.json")},     # old vs new iterations (lab book E23)
            "golden": j(ROOT / "4_laws_and_rules/output/eval" / "golden_summary.json"),
            "golden_rows": list(csv.DictReader(open(ROOT / "4_laws_and_rules/output/eval" / "golden_scores.csv", encoding="utf-8")))}


def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    data = {"demos": demos(), "rules": j(ROOT / "4_laws_and_rules/output/rules/rules.json"),
            "annex4": j(ROOT / "4_laws_and_rules/output/rules/annex4.json"), "experiments": experiments(), "real": real()}
    json.dump(data, open(SITE / "data" / "nomad.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(premises(), open(SITE / "data" / "premises.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(basemap(), open(SITE / "data" / "basemap.json", "w", encoding="utf-8"), separators=(",", ":"))
    engine()
    city()
    tot = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print("site data: %d demos, %d rules, %.1f MB in app/" % (len(data["demos"]), len(data["rules"]), tot / 1e6))


if __name__ == "__main__":
    main()
