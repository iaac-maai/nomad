# -*- coding: utf-8 -*-
"""NOMAD: redraw the demos already in rhino_grasshopper/NOMAD.3dm with the current engine, in a separate Rhino that then closes.

NOMAD.gh only draws demos that are not in the file yet, so older drawings stay until they are redrawn. For each demo
recipe (7_floor_plans/output/sheets/recipes, written by make_demo.py), every object under "06 NOMAD experiments::<name>" is removed
and the demo is drawn again (to the right of what is in the file, as NOMAD.gh places new ones). A copy of the file is kept first as old/rhino/NOMAD_before_redraw.3dm.
Only run it while NOMAD.3dm is closed.
Run: powershell -File rhino_grasshopper\\code\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\redraw_demos.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\logs\\redraw_log.txt
"""
import os, shutil, sys, traceback
import Rhino
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
sys.path.append(ROOT + r"\rhino_grasshopper\code")
LOG = ROOT + r"\rhino_grasshopper\logs\redraw_log.txt"
FILE = ROOT + r"\rhino_grasshopper\NOMAD.3dm"
DEMOS = ("D0_", "D1_", "D2_", "D3_", "D4_", "D5_", "D6_")


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def under(doc, base):
    """Every object on the layer `base` or any layer below it."""
    i = doc.Layers.FindByFullPath(base, -1)
    if i < 0:
        return []
    out = []
    for ly in doc.Layers:
        if not ly.IsDeleted and (ly.FullPath == base or ly.FullPath.startswith(base + "::")):
            out += list(doc.Objects.FindByLayer(ly) or [])
    return out


def main():
    open(LOG, "w").close()
    shutil.copy2(FILE, ROOT + r"\old\rhino\NOMAD_before_redraw.3dm")
    Rhino.RhinoApp.RunScript('_-Open "%s"' % FILE, False)
    doc = Rhino.RhinoDoc.ActiveDoc
    sc.doc = doc
    import nomad_core as core
    import nomad_model as model
    import nomad_sheet as sheet
    for name, rec in core.recipes():
        if not name.startswith(DEMOS):
            continue
        try:
            base = sheet.PARENT + "::" + name
            objs = under(doc, base)
            for o in objs:
                doc.Objects.Delete(o, True)
            rc = rec.get("case") or core.run(rec["shop"], rec["mix"], rec.get("size", "typical"))
            if not rc.get("story"):
                log("%s: no story in its recipe, skipped" % name)
                continue
            model.draw_demo(doc, rc, name, core.SHEETS, capture_pngs=False)
            log("%s: removed %d old objects, redrawn" % (name, len(objs)))
        except Exception:
            log("ERROR in %s\n%s" % (name, traceback.format_exc()))
    Rhino.RhinoApp.RunScript('_-Save _Enter', False)
    log("saved %s" % FILE)


try:
    main()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
Rhino.RhinoDoc.ActiveDoc.Modified = False
Rhino.RhinoApp.Exit()
