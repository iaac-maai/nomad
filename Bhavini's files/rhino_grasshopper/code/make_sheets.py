# -*- coding: utf-8 -*-
"""Make NOMAD before / after sheets in a separate Rhino (never the user's open window), then close it.

Same code as NOMAD.gh (nomad_core + nomad_sheet). For each case below and every plan in nomad/inbox/ it:
  - runs Stage 6 (before / after) and Stage 5 (rule check),
  - draws the sheet, saves 7_floor_plans/output/sheets/<name>.png (picture) + <name>.json (numbers),
  - saves a recipe in 7_floor_plans/output/sheets/recipes/ - NOMAD.gh draws every recipe into rhino_grasshopper/NOMAD.3dm
    (layer "06 NOMAD experiments::<name>"), so all experiments live in the one Rhino file.
Run: powershell -File rhino_grasshopper\code\run_in_rhino.ps1 -Script C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code\make_sheets.py -Done C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\logs\sheets_log.txt
"""
import os, sys, traceback
import Rhino
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
sys.path.append(ROOT + r"\rhino_grasshopper\code")
LOG = ROOT + r"\rhino_grasshopper\logs\sheets_log.txt"
CASES = [  # name, dataset shop index, mix
    ("E09_shop_145057_2x1bed_1x2bed", 0, {"1bed": 2, "2bed": 1}),
    ("E09_shop_146519_2x1bed_1x2bed", 5, {"1bed": 2, "2bed": 1}),
    ("E09_shop_154608_deep_2x1bed", 70, {"1bed": 2}),
    ("E09_shop_79_patio_2x1bed_1x2bed", 79, {"1bed": 2, "2bed": 1}),
    ("E09_shop_178_deep_5x1bed_2x2bed", 178, {"1bed": 5, "2bed": 2}),
]


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def one(core, sheet, name, shop, mix, size="typical"):
    if not shop.get("ok"):
        log("%s: shop not read (%s)" % (name, shop.get("reason")))
        return
    shop["name"] = name
    case = core.run(shop, mix, size)
    box = sheet.draw(sc.doc, case, name)
    png = sheet.capture(sc.doc, box, os.path.join(core.SHEETS, name + ".png"))
    core.save_case(case, name)
    log("%s: before %s %d/%d -> after %s %d/%d (%s) -> %s" % (
        name, case["before"]["res"]["verdict"], case["before"]["res"]["flats_passing"], case["before"]["res"]["flats_asked"],
        case["after"]["res"]["verdict"], case["after"]["res"]["flats_passing"], case["after"]["res"]["flats_asked"], case["changed"], png))


def main():
    open(LOG, "w").close()
    import nomad_core as core
    import nomad_sheet as sheet
    for name, idx, mix in CASES:
        try:
            one(core, sheet, name, core.shop_from_dataset(idx), mix)
        except Exception:
            log("ERROR in %s\n%s" % (name, traceback.format_exc()))
    for job in core.inbox_jobs(force=True):
        c = job["cfg"]
        mix = {"studio": int(c["n_studio"]), "1bed": int(c["n_1bed"]), "2bed": int(c["n_2bed"]), "3bed": int(c["n_3bed"])}
        try:
            one(core, sheet, "E09_" + job["name"], core.shop_from_plan(job["path"], c["known_facade_m"], c["height"]), mix,
                "compact" if c.get("compact") else "typical")
        except Exception:
            log("ERROR in %s\n%s" % (job["name"], traceback.format_exc()))


try:
    main()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
