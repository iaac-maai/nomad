# -*- coding: utf-8 -*-
"""Open nomad_unit_mix.gh in Grasshopper, run it, and write what the Nomad component produced
(errors, number of boxes, report text) to rhino_grasshopper/logs/verify_log.txt. Runs inside Rhino 7, then closes Rhino.
Run:  Rhino.exe /nosplash /runscript="_-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\verify_gh.py"
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
FILES = [("NOMAD.gh", "NOMAD")]
TEST_PLAN = (r"C:\Bhavini\AI\ADs\nomad\7_floor_plans\input\datasets\test_plans\145057.png", 145057)
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "verify_log.txt")


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def verify():
    open(LOG, "w").close()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel
    for name, nick in FILES:
        path = os.path.join(ROOT, "rhino_grasshopper", name)
        if not os.path.exists(path):
            log("missing " + name)
            continue
        log("=== " + name)
        check(GH_DocumentIO, GH_RuntimeMessageLevel, path, nick)
        log("=== " + name + " with a drawn 12 x 15 m outline, street facade on one 12 m side, 2 x 1-bed")
        check(GH_DocumentIO, GH_RuntimeMessageLevel, path, nick, own_outline=True)
        log("=== " + name + " reading the plan image " + TEST_PLAN[0])
        check(GH_DocumentIO, GH_RuntimeMessageLevel, path, nick, plan=True)
    log("done")


def set_plan(doc, GH):
    import json, io, math
    with io.open(ROOT + r"\7_floor_plans\output\clean\nomad_shells.json", encoding="utf-8") as f:
        s = [x for x in json.load(f)["shells"] if x["shell_id"] == TEST_PLAN[1]][0]
    longest = max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in s["facade"])
    log("known longest facade given: %.2f m" % longest)
    for obj in doc.Objects:
        if obj.NickName.startswith("Plan file"):
            obj.PersistentData.Clear()
            obj.PersistentData.Append(GH.Kernel.Types.GH_String(TEST_PLAN[0]))
        elif obj.NickName == "read plan":
            obj.Value = True
        elif obj.NickName == "known_facade_m":
            obj.Slider.Value = System.Decimal(round(longest, 1))
        elif obj.NickName == "n_2bed":
            obj.Slider.Value = System.Decimal(0)
        elif obj.NickName == "make sheet":
            obj.Value = True


def set_own_outline(doc, GH):
    import Rhino.Geometry as rg
    rect = rg.PolylineCurve([rg.Point3d(0, 0, 0), rg.Point3d(12, 0, 0), rg.Point3d(12, 15, 0),
                             rg.Point3d(0, 15, 0), rg.Point3d(0, 0, 0)])
    street = rg.LineCurve(rg.Point3d(0, 0, 0), rg.Point3d(12, 0, 0))
    for obj in doc.Objects:
        if obj.NickName.startswith("Your shop outline"):
            obj.PersistentData.Clear()
            obj.PersistentData.Append(GH.Kernel.Types.GH_Curve(rect))
        elif obj.NickName.startswith("Street facade"):
            obj.PersistentData.Clear()
            obj.PersistentData.Append(GH.Kernel.Types.GH_Curve(street))
        elif obj.NickName == "n_2bed":
            obj.Slider.Value = System.Decimal(0)


def check(GH_DocumentIO, GH_RuntimeMessageLevel, path, nick, own_outline=False, plan=False):
    io = GH_DocumentIO()
    io.Open(path)
    doc = io.Document
    doc.Enabled = True
    import Grasshopper as GH
    if own_outline:
        set_own_outline(doc, GH)
    if plan:
        set_plan(doc, GH)
    doc.NewSolution(True)
    for obj in doc.Objects:
        if obj.NickName == nick:
            for lvl in (GH_RuntimeMessageLevel.Error, GH_RuntimeMessageLevel.Warning):
                for m in obj.RuntimeMessages(lvl):
                    log("%s: %s" % (lvl, m))
            for p in obj.Params.Output:
                log("output %-8s items: %d" % (p.NickName, p.VolatileDataCount))
                if p.NickName in ("report", "out") and p.VolatileDataCount:
                    for item in p.VolatileData.AllData(True):
                        log(unicode(item).encode("utf-8"))


try:
    verify()
except Exception:
    log("ERROR\n" + traceback.format_exc())
Rhino.RhinoApp.Exit()
