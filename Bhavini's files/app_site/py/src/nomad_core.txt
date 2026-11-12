# -*- coding: utf-8 -*-
"""NOMAD core for Rhino/Grasshopper (IronPython 2.7): where a shop comes from, and the full check.

Used by grasshopper/NOMAD.gh (the NOMAD component) and by background runs (src/rhino/make_sheets.py),
so what you see in Grasshopper and what goes into the lab book are made by the same code.

  shop_from_plan(path, facade_m)   plan drawing -> outline + façade (runs src/building/read_plan.py)
  shop_from_curve(crv, facade_crv) a curve you traced in Rhino
  shop_from_dataset(i)             one of the 180 cleaned shops
  run(shop, mix, size, lit_depth)  generator (src/generate/layout.py) + flags (src/check/flags.py)
  inbox_jobs()                     every plan in nomad/inbox/ that has no up-to-date sheet yet
"""
import os, io, json, math, sys, unicodedata

ROOT = r"C:\Bhavini\AI\ADs\nomad"
for _p in (ROOT + r"\src\generate", ROOT + r"\src\check"):
    if _p not in sys.path:
        sys.path.append(_p)
import layout
import flags
import better
import plan2
import plan3

F3D_PY = ROOT + r"\external\floorplan-to-3d\.venv\Scripts\python.exe"
READER = ROOT + r"\src\building\read_plan.py"
CACHE = ROOT + r"\results\plan_reading\from_rhino"
INBOX = ROOT + r"\inbox"
SHEETS = ROOT + r"\results\sheets"
PLAN_EXT = (".png", ".jpg", ".jpeg", ".pdf")
_data = {}


def data():
    if not _data:
        with io.open(ROOT + r"\data\clean\nomad_shells.json", encoding="utf-8") as f:
            _data["shells"] = json.load(f)["shells"]
        with io.open(ROOT + r"\results\generation\room_programs.json", encoding="utf-8") as f:
            _data["programs"] = json.load(f)["programs"]
        _data["reads"] = {}
    return _data


def reload_all():
    """Pick up edits to the Python files without restarting Rhino."""
    reload(layout)
    reload(flags)
    reload(better)
    reload(plan2)
    reload(plan3)


def read_plan(path, facade_m):
    """Run the plan reader once per file + known size (separate Python with the AI model); cached."""
    import System
    key = (path, os.path.getmtime(path), round(facade_m or 0, 2))
    reads = data()["reads"]
    if key in reads:
        return reads[key]
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    stem = os.path.splitext(os.path.basename(path))[0]
    out, prev = os.path.join(CACHE, stem + ".json"), os.path.join(CACHE, stem + "_read.png")
    args = '"%s" "%s" --out "%s" --preview "%s"' % (READER, path, out, prev)
    if facade_m and facade_m > 0:
        args += " --facade-m %.2f" % facade_m
    if os.path.exists(out):                          # never read an old answer if this run fails
        os.remove(out)
    psi = System.Diagnostics.ProcessStartInfo(F3D_PY, args)
    psi.UseShellExecute, psi.CreateNoWindow = False, True
    psi.WorkingDirectory = ROOT
    proc = System.Diagnostics.Process.Start(psi)
    if not proc.WaitForExit(180000):
        proc.Kill()
        return {"ok": False, "reason": "the plan reader took longer than 3 minutes"}
    if proc.ExitCode != 0 or not os.path.exists(out):
        return {"ok": False, "reason": "the plan reader stopped with an error (exit code %d)" % proc.ExitCode}
    with io.open(out, encoding="utf-8") as f:
        res = json.load(f)
    reads[key] = res
    return res


def shop_from_plan(path, facade_m=0, height=2.8):
    r = read_plan(path, float(facade_m or 0))
    if not r.get("ok"):
        return {"ok": False, "reason": r.get("reason", "plan not read")}
    k = 1.0 / r["scale_px_per_m"]
    W, H = r["image_px"][0] * k, r["image_px"][1] * k
    ox, oy = r["origin_px"][0] * k, H - r["origin_px"][1] * k          # outline origin inside the picture
    outline = [(x + ox, y + oy) for x, y in r["outline"]]
    facade = [[[a[0] + ox, a[1] + oy], [b[0] + ox, b[1] + oy]] for a, b in r["facade"]]
    return {"ok": True, "outline": outline, "facade": facade, "height": height, "name": os.path.splitext(os.path.basename(path))[0],
            "source": u"plan %s (scale from %s; %.1f m², %.1f m façade found)%s" % (
                os.path.basename(path), r["scale_method"], r["area_m2"], r["facade_m"],
                u" - WARNING: no known size given, the scale is a guess (often ~50% off)" if not (facade_m and facade_m > 0) else u""),
            "scale_guessed": not (facade_m and facade_m > 0),
            "image": {"path": path, "w": W, "h": H} if not path.lower().endswith(".pdf") else None,
            "read_preview": os.path.join(CACHE, os.path.splitext(os.path.basename(path))[0] + "_read.png")}


def shop_from_curve(pts, facade_pts=None, height=2.8):
    """pts: closed outline [(x, y)...]; facade_pts: function(point) -> True if on the street line, or None."""
    edges = [[list(a), list(b)] for a, b in zip(pts[:-1], pts[1:])]
    if facade_pts is not None:
        facade = [e for e in edges if facade_pts(e[0]) and facade_pts(e[1])]
    else:
        facade = [e for e in edges if math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]) >= 3.0]
    return {"ok": True, "outline": pts, "facade": facade, "height": height, "name": "my_outline", "source": "your outline", "image": None}


def zoning_lookup(text):
    """Step 3 for a Barcelona address or cadastral reference: the matching empty ground-floor premises of the 2024
    census, with its MUC zone (results/zoning/lookup.json, written by src/zoning/zoning.py), or None.
    text: a cadastral reference (e.g. 2249707DF3824G) or "street number" (e.g. "Valencia 640")."""
    path = os.path.join(ROOT, "results", "zoning", "lookup.json")
    if not text or not os.path.exists(path):
        return None
    norm = lambda t: u"".join(c for c in unicodedata.normalize("NFKD", u"%s" % t).upper() if not unicodedata.combining(c)).strip()
    q = norm(text)
    with io.open(path, encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:                                          # 1. cadastral reference
        if r["ref"] and norm(r["ref"]) == q:
            return r
    parts = q.replace(",", " ").split()
    num = [p for p in parts if p.isdigit()]
    street = u" ".join(p for p in parts if not p.isdigit())
    for r in rows:                                          # 2. street + number
        if num and r["num"] == num[0] and street and street in norm(r["street"]):
            return r
    return None


def add_zoning(shop, address):
    """Step 3: attach the zoning of a Barcelona address to the shop (NOMAD then shows a Zoning card first).
    Returns a line for the report."""
    if not address:
        return ""
    r = zoning_lookup(address)
    if r is None:
        return "Zoning: '%s' is not an empty premises in the 2024 census; zoning not checked.\n" % address
    shop["zoning"] = {"zone": r["zone"], "pgm_key": r["pgm_key"], "housing": r["housing"], "why": r["why"],
                      "address": "%s %s" % (r["street"], r["num"]), "barri": r["barri"], "ref": r.get("ref", "")}
    return u"Zoning (step 3): %s %s, %s -> %s (%s)\n" % (r["street"], r["num"], r["zone"], r["housing"], r["why"])


def shop_by_id(shell_id):
    """A dataset shop by its Swiss Dwellings unit id (stable when the cleaned list changes)."""
    shells = data()["shells"]
    for k, s in enumerate(shells):
        if int(s["shell_id"]) == int(shell_id):
            return shop_from_dataset(k)
    return {"ok": False, "reason": "shop %s is not in the cleaned dataset" % shell_id}


def shop_from_dataset(i):
    shells = data()["shells"]
    s = shells[int(i) % len(shells)]
    return {"ok": True, "outline": s["outline"], "facade": s["facade"], "height": s["height_m"], "name": "shop_%d" % s["shell_id"],
            "source": "dataset shop %d (former use: %s)" % (s["shell_id"], s["former_use"][:60]), "image": None}


def generator():
    """plan3 (real flats from the library) when its library is there, else plan2."""
    return plan3 if plan3.library() else plan2


def iterate(shop, mix, programs):
    """The layouts of one shop. plan3 also gets the building's existing portal / stair (shop["existing"]) and the
    weights the user set (shop["weights"])."""
    g = generator()
    if shop.get("scheme") == "shared":                      # shared-space housing (src/generate/shared.py)
        import shared
        return shared.iterations(shop["outline"], shop["facade"], shop["height"], mix, street=shop.get("street"),
                                 existing=shop.get("existing"), weights=shop.get("weights"), patios=shop.get("patios"),
                                 lit_depth=shop.get("lit_depth") or flags.LIT_DEPTH, lit_source="bars" if shop.get("lit_depth") else None)
    if g is plan3:
        return plan3.iterations(shop["outline"], shop["facade"], shop["height"], mix, programs, street=shop.get("street"),
                                existing=shop.get("existing"), weights=shop.get("weights"), patios=shop.get("patios"),
                                lit_depth=shop.get("lit_depth") or flags.LIT_DEPTH, lit_source="bars" if shop.get("lit_depth") else None)
    return g.iterations(shop["outline"], shop["facade"], shop["height"], mix, programs, street=shop.get("street"))


def run(shop, mix, size="typical", lit_depth=flags.LIT_DEPTH, programs=None):
    """Stage 6 + 5: before (as it is) and after (smallest intervention), each checked.
    Returns a case dict: shop, before plan/res, after plan/res."""
    before, its, tried = iterate(shop, mix, programs or data()["programs"])
    after = max([p for _, p, _ in its] or [before], key=lambda p: (p["proposal_ok"], p["compliant"]))   # src/generate/plan2.py
    cell = 0.25 if flags.area(shop["outline"]) < 400 else 0.5
    out = {"shop": shop, "mix": mix, "size": size, "tried": tried, "mix_text": mix_text(mix)}
    for key, plan in (("before", before), ("after", after)):
        res = flags.analyse(shop["outline"], shop["facade"], shop["height"], plan, lit_depth=lit_depth, cell=cell,
                            zoning=shop.get("zoning"))
        res["source"], res["name"], res["mix"], res["size"], res["mix_text"] = shop["source"], shop["name"], mix, size, mix_text(mix)
        out[key] = {"plan": plan, "res": res}
    out["changed"] = after.get("stage6", "")
    return out


def run_story(shop, mix, lit_depth=flags.LIT_DEPTH, programs=None):
    """The demo, stage by stage, for one shop:
    Stage 5 flags on the shop as it is (the flats asked for), then Stage 6 2D iterations (1 to 3), each checked:
      one per strategy that changes the plan (plan3.STRATEGIES): through flats off a passage, real flats off a shared hall
      (as asked, with block-interior flats, most homes); every flat a real plan stretched to fit.
    Stage 7 (3D) is drawn from these plans by nomad_model.py.
    programs: room sizes (default: learned from real flats); layout.with_targets gives the user's flat sizes."""
    progs = programs or data()["programs"]
    o, f, h = shop["outline"], shop["facade"], shop["height"]
    lit_depth = shop.get("lit_depth") or lit_depth          # the daylight prediction for this shop when there is one
    cell = 0.25 if flags.area(o) < 400 else 0.5
    def check(plan, label, m):
        res = flags.analyse(o, f, h, plan, lit_depth=lit_depth, cell=cell, zoning=shop.get("zoning"))
        if plan.get("scheme") == "shared":                  # MPGM 2004 DA2: density may be exceeded for social programmes
            import shared
            for c in res["cards"]:
                if c["rule"] == "density" and not c["ok"]:
                    c.update(ok=True, check=True, value=c["value"] + "; may be exceeded for homes for groups needing social attention",
                             cite=shared.CITE["density"])
        res.update(source=shop["source"], name=shop["name"], mix=m, mix_text=mix_text(m), label=label)
        homes = res["flats_passing"] - sum(1 for u in plan.get("units", []) if u.get("shared") and u.get("ok"))
        return {"plan": plan, "res": res, "label": label, "homes": homes}
    # plan generator v3 (src/generate/plan3.py): real flats from the library, stretched, around a shared hall or passage
    before, its, tried = iterate(shop, mix, progs)
    def own_mix(plan):
        m = {}
        for u in plan["units"]:
            m[u["type"]] = m.get(u["type"], 0) + 1
        return m
    return {"shop": shop, "mix": mix, "mix_text": mix_text(mix), "tried": tried, "story": True,
            "before": check(before, "as it is", mix),
            "iterations": [check(p, "%d · %s" % (k + 1, n), own_mix(p) if p["params"].get("fill") else mix)
                           for k, (n, p, _) in enumerate(its)]}


def run_building(shell, mix, clear_h, programs=None, sizes=None, weights=None):
    """A whole building (an empty warehouse, commercial or office building; src/generate/building.py): the building as
    it is, then one layout per way of laying it out (whole floor; patios cut through it), each with real plans on every
    level, Stage 5 checks on one floor and the building checks of Decret 141/2012 Annex 1 section 2 (Group B).
    Homes = homes passing on one floor x levels."""
    import building
    o = shell["outline"] if shell["outline"][0] == shell["outline"][-1] else shell["outline"] + [shell["outline"][0]]
    f = shell["facade"]
    lays = building.layouts(dict(shell, outline=o), mix, clear_h, sizes=sizes, weights=weights)
    cell = 0.25 if flags.area(o) < 400 else 0.5
    def check(plan, label):
        lv, sh = plan.get("levels", 1), plan.get("storey_h", clear_h)
        clear = sh - (building.SLAB if lv > 1 else 0.0)
        bc = plan.get("building_checks", [])
        n = len(plan.get("units", []))
        plan["placed"] = n * lv                              # homes in the whole building
        plan["requested"] = n * lv if n else sum(mix.values())
        plan["unplaced"] = []
        plan["density_cap"] = int(flags.area(o[:-1]) * lv / 80.0)    # MPGM: built m² / 80
        plan["density_ok"] = n * lv <= plan["density_cap"]
        plan["proposal_ok"] = bool(n) and plan["density_ok"] and all(c["ok"] for c in bc)
        res = flags.analyse(o, f, clear, plan, cell=cell, zoning=shell.get("zoning"), lit_depth=shell.get("lit_depth") or flags.LIT_DEPTH)
        for c in bc:                                         # the building rules as cards (scope: building)
            res["cards"].append({"rule": "b_" + c["rule"], "title": BUILDING_TITLE.get(c["rule"], c["rule"]), "ok": c["ok"],
                                 "check": False, "value": c["text"], "limit": "", "cite": c["cite"], "scope": "building"})
        if res["verdict"] == "YES" and not all(c["ok"] for c in bc):
            res["verdict"] = "PARTLY"
        res.update(source=shell.get("source", "Catastro"), name=shell.get("name", ""), mix=mix, mix_text=mix_text(mix), label=label,
                   levels=lv, storey_h=sh, homes_per_level=res["flats_passing"])
        return {"plan": plan, "res": res, "label": label, "homes": res["flats_passing"] * lv}
    empty = {"units": [], "corridors": [], "patios": [], "levels": 1, "storey_h": clear_h, "building_checks": []}
    return {"shop": dict(shell, outline=o), "mix": mix, "mix_text": mix_text(mix), "story": True, "building": True,
            "before": check(empty, "as it is"),
            "iterations": [check(p, "%d · %s" % (k + 1, n)) for k, (n, p) in enumerate(lays)]}


BUILDING_TITLE = {"height": "Clear height (Group B)", "route": "Accessible route", "access": "Lift landing", "stairs": "Stairs",
                  "lift": "Lift", "lift2": "Second lift", "patio": "Patio size", "community": "Community room"}


def mix_text(mix):
    names = [("studio", "studio"), ("1bed", "1-bed"), ("2bed", "2-bed"), ("3bed", "3-bed")]
    return " + ".join("%d x %s" % (mix[k], n) for k, n in names if mix.get(k)) or "no flats asked"


def inbox_jobs(force=False):
    """Plans dropped in nomad/inbox/. Optional <name>.json next to a plan sets known_facade_m, height,
    n_studio, n_1bed, n_2bed, n_3bed, compact. A plan is done when results/sheets/<name>.png is newer."""
    if not os.path.isdir(INBOX):
        os.makedirs(INBOX)
    jobs = []
    for fn in sorted(os.listdir(INBOX)):
        stem, ext = os.path.splitext(fn)
        if ext.lower() not in PLAN_EXT:
            continue
        path = os.path.join(INBOX, fn)
        cfg = {"known_facade_m": 0, "height": 2.8, "n_studio": 0, "n_1bed": 2, "n_2bed": 1, "n_3bed": 0, "compact": False,
               "address": ""}
        side = os.path.join(INBOX, stem + ".json")
        if os.path.exists(side):
            with io.open(side, encoding="utf-8") as f:
                cfg.update(json.load(f))
        png = os.path.join(SHEETS, stem + ".png")
        newest = max(os.path.getmtime(path), os.path.getmtime(side) if os.path.exists(side) else 0)
        if force or not os.path.exists(png) or os.path.getmtime(png) < newest:
            jobs.append({"path": path, "name": stem, "cfg": cfg})
    return jobs


RECIPES = os.path.join(ROOT, "results", "sheets", "recipes")


def save_case(case, name):
    """Numbers (<name>.json) and a recipe (recipes/<name>.json) that NOMAD.gh redraws into NOMAD.3dm."""
    for d in (SHEETS, RECIPES):
        if not os.path.isdir(d):
            os.makedirs(d)
    def slim(r):
        out = dict(r)
        out["daylight"] = dict((k, v) for k, v in r["daylight"].items() if k != "cells")
        return out
    if case.get("story"):
        summary = {"name": name, "shop": case["shop"]["source"], "mix": case["mix_text"], "before": slim(case["before"]["res"]),
                   "iterations": [{"label": it["label"], "homes": it["homes"], "verdict": it["res"]["verdict"],
                                   "patios": len(it["plan"].get("patios", [])), "res": slim(it["res"])} for it in case["iterations"]]}
    else:
        summary = {"name": name, "shop": case["shop"]["source"], "mix": case["mix_text"], "changed": case["changed"],
                   "before": slim(case["before"]["res"]), "after": slim(case["after"]["res"])}
    recipe = {"name": name, "case": case}                  # the finished case: the file shows exactly what was made
    for path, obj in ((os.path.join(SHEETS, name + ".json"), summary), (os.path.join(RECIPES, name + ".json"), recipe)):
        txt = json.dumps(obj, indent=1, ensure_ascii=False)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(txt if sys.version_info[0] >= 3 else unicode(txt))
    return os.path.join(SHEETS, name + ".json")


def recipes():
    """Every saved experiment, oldest first: [(name, recipe dict)]."""
    if not os.path.isdir(RECIPES):
        return []
    out = []
    for fn in sorted(os.listdir(RECIPES), key=lambda f: os.path.getmtime(os.path.join(RECIPES, f))):
        if fn.endswith(".json"):
            with io.open(os.path.join(RECIPES, fn), encoding="utf-8") as f:
                out.append((fn[:-5], json.load(f)))
    return out
