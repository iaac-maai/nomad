# -*- coding: utf-8 -*-
"""Pictures of rhino/NOMAD.3dm as it is (opened read-only, nothing saved): the whole lab book, and the E09 / E10 rows.
Saves logs/rhino/nomad_file_overview.png, nomad_file_E09.png, nomad_file_E10.png. Closes Rhino.
"""
import os, traceback
import Rhino, System
import Rhino.Geometry as rg
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
LOG = os.path.join(ROOT, "logs", "rhino", "file_shot_log.txt")


def log(m):
    with open(LOG, "a") as f:
        f.write(m + "\n")


def shot(doc, bb, path, w=2400):
    view = [v for v in doc.Views if v.ActiveViewport.Name == "Top"][0]
    vp = view.ActiveViewport
    vp.DisplayMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    vp.ZoomBoundingBox(bb)
    view.Redraw()
    vc = Rhino.Display.ViewCapture()
    vc.Width, vc.Height = w, int(w * vp.Size.Height / float(vp.Size.Width))
    vc.DrawGrid = vc.DrawAxes = vc.DrawGridAxes = False
    bmp = vc.CaptureToBitmap(view)
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png)
    bmp.Dispose()
    log("saved " + path)


def layer_box(doc, prefix):
    bb = rg.BoundingBox.Empty
    for o in doc.Objects:
        if o.Attributes.LayerIndex >= 0 and doc.Layers[o.Attributes.LayerIndex].FullPath.startswith(prefix):
            bb.Union(o.Geometry.GetBoundingBox(True))
    return bb


try:
    open(LOG, "w").close()
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % os.path.join(ROOT, "rhino", "NOMAD.3dm"), False)
    doc = Rhino.RhinoDoc.ActiveDoc
    log("%s: %d objects, %d layers" % (doc.Path, doc.Objects.Count, doc.Layers.Count))
    top = [ly.FullPath for ly in doc.Layers if "::" not in ly.FullPath]
    log("top layers: " + ", ".join(top))
    labs = sorted(set(ly.FullPath.split("::")[1] for ly in doc.Layers if ly.FullPath.startswith("07 NOMAD lab book::")))
    log("lab book rows: " + " | ".join(labs))
    all_bb = rg.BoundingBox.Empty
    for o in doc.Objects:
        all_bb.Union(o.Geometry.GetBoundingBox(True))
    shot(doc, all_bb, os.path.join(ROOT, "logs", "rhino", "nomad_file_overview.png"))
    for key, prefix in (("E09", "06 NOMAD experiments::E09_"), ("E10", "06 NOMAD experiments::D2_")):
        bb = layer_box(doc, prefix)
        if bb.IsValid:
            shot(doc, bb, os.path.join(ROOT, "logs", "rhino", "nomad_file_%s.png" % key))
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
