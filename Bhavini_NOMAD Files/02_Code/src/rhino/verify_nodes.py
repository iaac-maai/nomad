# -*- coding: utf-8 -*-
"""Open grasshopper/NOMAD.gh (the small-components version), set a Barcelona address, run it, and log every
component's errors and warnings and the report panel. Runs inside Rhino 7, then closes Rhino.
Run: powershell -File src\\rhino\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\verify_nodes.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\logs\\rhino\\verify_nodes_log.txt
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
LOG = os.path.join(ROOT, "logs", "rhino", "verify_nodes_log.txt")
ADDRESS = "Valencia 640"


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def verify():
    open(LOG, "w").close()
    Rhino.RhinoApp.GetPlugInObject("Grasshopper").LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_DocumentIO, GH_RuntimeMessageLevel
    from Grasshopper.Kernel.Special import GH_Panel
    io = GH_DocumentIO()
    if not io.Open(os.path.join(ROOT, "grasshopper", "NOMAD.gh")):
        log("could not open NOMAD.gh"); return
    doc = io.Document
    GH.Instances.DocumentServer.AddDocument(doc)
    doc.Enabled = True
    for o in doc.Objects:
        if isinstance(o, GH_Panel) and o.NickName.startswith("address"):
            o.UserText = ADDRESS
            o.ExpireSolution(False)
    doc.NewSolution(True)
    comps = [o for o in doc.Objects if hasattr(o, "Params") and o.NickName[:1].isdigit()]
    log("components: %d" % len(comps))
    bad = 0
    for c in sorted(comps, key=lambda c: int(c.NickName.split(" ")[0])):
        msgs = []
        for lvl in (GH_RuntimeMessageLevel.Error, GH_RuntimeMessageLevel.Warning):
            for m in c.RuntimeMessages(lvl):
                msgs.append("%s: %s" % (lvl, m))
        bad += len([m for m in msgs if m.startswith("Error")])
        log("%-18s inputs %d  %s" % (c.NickName, c.Params.Input.Count, "; ".join(msgs)[:300] if msgs else "ok"))
    for o in doc.Objects:
        if isinstance(o, GH_Panel) and not o.NickName.startswith("address"):
            txt = []
            for br in o.VolatileData.Branches:
                for g in br:
                    txt.append(unicode(g))
            log("REPORT PANEL:\n" + u"\n".join(txt)[:2500])
    log("errors: %d" % bad)


try:
    verify()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
Rhino.RhinoApp.Exit()
