# -*- coding: utf-8 -*-
"""Open rhino_grasshopper/NOMAD.3dm read-only (nothing saved) and list where its pictures point. Log: logs/check_pictures_log.txt"""
import os
import Rhino
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
FILE = os.path.join(ROOT, "rhino_grasshopper", "NOMAD.3dm")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "check_pictures_log.txt")
open(LOG, "w").close()


def log(m):
    with open(LOG, "a") as f:
        f.write(m + "\n")


try:
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % FILE, False)
    doc = sc.doc
    dirs, missing = {}, 0
    for i in range(doc.Materials.Count):
        m = doc.Materials[i]
        for t in (m.GetTextures() if m else []):
            if t and t.FileName:
                d = os.path.dirname(t.FileName)
                dirs[d] = dirs.get(d, 0) + 1
                missing += not os.path.exists(t.FileName)
    for d, n in sorted(dirs.items()):
        log("%3d  %s" % (n, d))
    log("pictures whose file is not on disk (kept inside the .3dm): %d" % missing)
    log("stray results folder: %s" % os.path.exists(os.path.join(ROOT, "results")))
    Rhino.RhinoApp.RunScript("_-New _None", False)
    log("done")
except Exception as e:
    log("ERROR %s" % e)
