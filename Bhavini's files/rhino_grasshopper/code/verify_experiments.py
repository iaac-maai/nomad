# -*- coding: utf-8 -*-
"""Check that NOMAD.gh puts every saved experiment into the Rhino file, on a COPY of rhino_grasshopper/NOMAD.3dm
(rhino_grasshopper/logs/NOMAD_copy_test.3dm), so the user's open file is never touched. Then closes Rhino.
Run: powershell -File rhino_grasshopper\\code\\run_in_rhino.ps1 -Script <this file> -Done C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\logs\\experiments_log.txt
"""
import os, shutil, traceback
import Rhino, System, clr
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
LOG = ROOT + r"\rhino_grasshopper\logs\experiments_log.txt"
COPY = ROOT + r"\rhino_grasshopper\logs\NOMAD_copy_test.3dm"


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def run():
    open(LOG, "w").close()
    shutil.copy2(ROOT + r"\rhino_grasshopper\NOMAD.3dm", COPY)
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % COPY, False)
    doc = Rhino.RhinoDoc.ActiveDoc
    log("opened %s: %d objects, %d layers" % (doc.Path, doc.Objects.Count, doc.Layers.Count))
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel
    io = GH_DocumentIO()
    io.Open(ROOT + r"\rhino_grasshopper\NOMAD.gh")
    g = io.Document
    g.Enabled = True
    g.NewSolution(True)
    for obj in g.Objects:
        if obj.NickName == "NOMAD":
            for lvl in (GH_RuntimeMessageLevel.Error, GH_RuntimeMessageLevel.Warning):
                for m in obj.RuntimeMessages(lvl):
                    log("%s: %s" % (lvl, m))
            for p in obj.Params.Output:
                if p.NickName in ("report", "verdict") and p.VolatileDataCount:
                    for item in p.VolatileData.AllData(True):
                        log(unicode(item).encode("utf-8")[:1500])
    import sys as _s
    for sub in ("rhino_grasshopper\\code", "6_check_the_shop\\code", "7_floor_plans\\code"):              # opening a file can reset the script engine's path
        d = os.path.join(ROOT, sub)
        if d not in _s.path:
            _s.path.append(d)
    import nomad_sheet
    names = nomad_sheet.drawn_names(doc)
    log("experiments now in the file: %d -> %s" % (len(names), ", ".join(names)))
    log("objects now: %d" % doc.Objects.Count)
    Rhino.RhinoApp.RunScript("_-Save _Enter", False)
    log("saved the copy: %s (%d bytes)" % (COPY, os.path.getsize(COPY)))


import sys
sys.path.append(ROOT + r"\rhino_grasshopper\code")
try:
    run()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
