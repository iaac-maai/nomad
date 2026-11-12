# -*- coding: utf-8 -*-
"""Pictures of the facade layers in rhino_grasshopper/NOMAD.3dm (opened, nothing saved): top view of photo + drawing, and a
perspective of the 3D facade. Saves rhino_grasshopper/logs/facade_top.png, facade_3d.png. Closes Rhino."""
import os, traceback
import Rhino, System
import Rhino.Geometry as rg
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "facade_shot_log.txt")
PREFIX = "06 NOMAD experiments::facade "


def log(m):
    with open(LOG, "a") as f:
        f.write(m + "\n")


def box(doc, part):
    bb = rg.BoundingBox.Empty
    for o in doc.Objects:
        if o.Attributes.LayerIndex >= 0:
            p = doc.Layers[o.Attributes.LayerIndex].FullPath
            if p.startswith(PREFIX) and part in p:
                bb.Union(o.Geometry.GetBoundingBox(True))
    return bb


def capture(view, path, w=2400):
    vp = view.ActiveViewport
    vc = Rhino.Display.ViewCapture()
    vc.Width, vc.Height = w, int(w * vp.Size.Height / float(vp.Size.Width))
    vc.DrawGrid = vc.DrawAxes = vc.DrawGridAxes = False
    bmp = vc.CaptureToBitmap(view)
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png)
    bmp.Dispose()
    log("saved " + path)


try:
    open(LOG, "w").close()
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % os.path.join(ROOT, "rhino_grasshopper", "NOMAD.3dm"), False)
    doc = Rhino.RhinoDoc.ActiveDoc
    top = [v for v in doc.Views if v.ActiveViewport.Name == "Top"][0]
    top.ActiveViewport.DisplayMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    bb = box(doc, "")
    bb.Inflate(3)
    top.ActiveViewport.ZoomBoundingBox(bb)
    top.Redraw()
    capture(top, os.path.join(ROOT, "rhino_grasshopper", "logs", "facade_top.png"))
    per = [v for v in doc.Views if v.ActiveViewport.Name == "Perspective"][0]
    vp = per.ActiveViewport
    vp.DisplayMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    b3 = box(doc, "3 3D facade")
    c = b3.Center
    vp.SetCameraLocations(c, rg.Point3d(c.X - 22, c.Y - 38, c.Z - 4))
    vp.ZoomBoundingBox(b3)
    per.Redraw()
    capture(per, os.path.join(ROOT, "rhino_grasshopper", "logs", "facade_3d.png"), 1800)
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
