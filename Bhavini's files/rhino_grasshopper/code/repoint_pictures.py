# -*- coding: utf-8 -*-
"""Point every picture in rhino_grasshopper/NOMAD.3dm at its file in the new folders (12 Nov 2026 reorganisation).
Rhino puts a missing embedded picture back at its old address when the file opens; with the old addresses it was
re-creating a stray results/ folder. Run in a separate Rhino (rhino_grasshopper/code/run_in_rhino.ps1), NOMAD.3dm closed."""
import os
import Rhino
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
FILE = os.path.join(ROOT, "rhino_grasshopper", "NOMAD.3dm")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "repoint_log.txt")
MAP = [("\\results\\sheets\\", "\\7_floor_plans\\output\\sheets\\"),
       ("\\results\\figures\\", "\\7_floor_plans\\output\\figures\\"),
       ("\\results\\facade\\", "\\3_facade\\output\\"),
       ("\\results\\generation\\", "\\7_floor_plans\\output\\generation\\"),
       ("\\results\\real_shops\\", "\\2_building\\output\\real_shops\\"),
       ("\\book\\figures\\", "\\lab_book\\figures\\"),
       ("\\docs\\presentation\\", "\\presentation\\")]


def log(m):
    with open(LOG, "a") as f:
        f.write(m + "\n")


def new_path(p):
    for a, b in MAP:
        if a.lower() in p.lower():
            i = p.lower().index(a.lower())
            return p[:i] + b + p[i + len(a):]
    return None


open(LOG, "w").close()
try:
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % FILE, False)
    doc = sc.doc
    n, seen = 0, 0
    for i in range(doc.Materials.Count):
        m = doc.Materials[i]
        if m is None or m.IsDeleted:
            continue
        changed = False
        for t in m.GetTextures():
            if t is None:
                continue
            seen += 1
            q = new_path(t.FileName or "")
            if q:
                t.FileReference = Rhino.FileIO.FileReference.CreateFromFullPath(q)
                m.SetTexture(t, t.TextureType)
                changed = True
                n += 1
        if changed:
            m.CommitChanges()
            doc.Materials.Modify(m, i, True)
    left = [t.FileName for i in range(doc.Materials.Count) if doc.Materials[i] for t in doc.Materials[i].GetTextures()
            if t and new_path(t.FileName or "")]
    log("textures seen %d, repointed %d, still old %d" % (seen, n, len(left)))
    Rhino.RhinoApp.RunScript("_-Save _Enter", False)
    log("done")
except Exception as e:
    log("ERROR %s" % e)
