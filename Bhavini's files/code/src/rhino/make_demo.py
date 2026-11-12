# -*- coding: utf-8 -*-
"""NOMAD demo (Stages 4-7) in a separate Rhino, then closes it. Same code as NOMAD.gh.

For each shop: Stage 4 (a plan drawing is read, when the shop comes from one), Stage 5 flags (YES / PARTLY / NO on
the shop as it is), Stage 6 three 2D iterations with the number of homes, Stage 7 a 3D model of each iteration.
Saves results/sheets/<name>.png (2D), <name>_3d_<k>.png (3D), <name>_board.png (both), <name>.json and a recipe,
which NOMAD.gh draws into rhino/NOMAD.3dm (layer "06 NOMAD experiments::<name>").
Run: powershell -File src\\rhino\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\make_demo.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\logs\\rhino\\demo_log.txt
"""
import os, sys, traceback
import Rhino
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
sys.path.append(ROOT + r"\src\rhino")
LOG = ROOT + r"\logs\rhino\demo_log.txt"
DATASET = [  # name, shop id (Swiss Dwellings unit), flats asked for
    ("D1_shop_146519_YES", 146519, {"1bed": 2, "2bed": 1}),
    ("D2_warehouse_154822_patio", 154822, {"1bed": 2, "2bed": 1}),
    ("D3_large_shop_152418", 152418, {"1bed": 5, "2bed": 2}),
    ("D4_warehouse_154608_NO", 154608, {"1bed": 2}),
]
BUILDINGS = [  # name, Catastro ref (src/zoning/warehouses.py), flats asked for, clear height (m)
    ("D5_warehouse_9569407", "9569407DF2896H", {"1bed": 2, "2bed": 1}, 6.0),
    ("D6_warehouse_patios_9318916", "9318916DF2891G", {"1bed": 2, "2bed": 1}, 6.0),
]
PLAN = ("D0_plan_drawing_145057", ROOT + r"\inbox\test_plan_145057.png", 9.9, 2.6, {"1bed": 2})


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def one(core, model, name, shop, mix):
    if not shop.get("ok"):
        log("%s: plan not read (%s)" % (name, shop.get("reason")))
        return
    shop["name"] = name
    story = core.run_story(shop, mix)
    brd = model.draw_demo(sc.doc, story, name, core.SHEETS)
    core.save_case(story, name)
    b = story["before"]["res"]
    log("%s: flags %s (%d/%d) | %s | board %s" % (name, b["verdict"], b["flats_passing"], b["flats_asked"],
        "; ".join("it %s: %d homes %s%s" % (it["label"][0], it["homes"], it["res"]["verdict"], " +patio" if it["plan"].get("patios") else "")
                  for it in story["iterations"]), brd))


def one_building(core, model, name, ref, mix, clear_h):
    import json
    shells = json.load(open(ROOT + r"\results\warehouses\shells.json"))
    shell = dict(shells[ref], name=name, source="Catastro " + ref)
    story = core.run_building(shell, mix, clear_h)
    brd = model.draw_demo(sc.doc, story, name, core.SHEETS)
    core.save_case(story, name)
    log("%s: %s | board %s" % (name, "; ".join("it %s: %d homes on %d levels %s" % (it["label"][0], it["homes"], it["plan"].get("levels", 1),
        it["res"]["verdict"]) for it in story["iterations"]), brd))


def main():
    open(LOG, "w").close()
    import nomad_core as core
    import nomad_model as model
    name, path, fac, h, mix = PLAN
    try:
        one(core, model, name, core.shop_from_plan(path, fac, h), mix)
    except Exception:
        log("ERROR in %s\n%s" % (name, traceback.format_exc()))
    for name, idx, mix in DATASET:
        try:
            one(core, model, name, core.shop_by_id(idx), mix)
        except Exception:
            log("ERROR in %s\n%s" % (name, traceback.format_exc()))
    for name, ref, mix, h in BUILDINGS:
        try:
            one_building(core, model, name, ref, mix, h)
        except Exception:
            log("ERROR in %s\n%s" % (name, traceback.format_exc()))


try:
    main()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
