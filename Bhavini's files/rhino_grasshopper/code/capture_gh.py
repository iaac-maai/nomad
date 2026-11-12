# -*- coding: utf-8 -*-
"""Screenshot of the working NOMAD.gh definition (for the presentation), in a separate Rhino that closes itself.
The definition is opened, solved on a dataset shop (with "experiments in this file" off, so nothing is drawn into
a file), zoomed to fit and saved as presentation/img/nomad_gh.png.
Run: powershell -File rhino_grasshopper\\code\\run_in_rhino.ps1 -Script <this file> -Done C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\logs\\gh_shot_log.txt
"""
import os, sys, traceback
import Rhino, System, clr
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "gh_shot_log.txt")
OUT = os.path.join(ROOT, "presentation", "img", "nomad_gh.png")


def log(m):
    with open(LOG, "a") as f:
        f.write(m + "\n")


def run():
    open(LOG, "w").close()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_DocumentIO
    io = GH_DocumentIO()
    io.Open(os.path.join(ROOT, "rhino_grasshopper", "NOMAD.gh"))
    doc = io.Document
    for o in doc.Objects:
        if o.NickName == "experiments in this file":
            o.Value = False
        if o.NickName == "shop_index":
            o.Slider.Value = System.Decimal(5)
    gh.ShowEditor()
    ed = GH.Instances.DocumentEditor
    ed.WindowState = System.Windows.Forms.FormWindowState.Normal
    ed.Size = System.Drawing.Size(2200, 1250)
    GH.Instances.DocumentServer.AddDocument(doc)
    canvas = GH.Instances.ActiveCanvas
    canvas.Document = doc
    doc.Enabled = True
    doc.NewSolution(True)
    for _ in range(5):
        Rhino.RhinoApp.Wait()
    bb = doc.BoundingBox(False)
    vw, vh = canvas.Width, canvas.Height
    z = min(vw / (bb.Width + 80.0), vh / (bb.Height + 80.0))
    canvas.Viewport.Zoom = z
    canvas.Viewport.MidPoint = System.Drawing.PointF(bb.X + bb.Width / 2.0, bb.Y + bb.Height / 2.0)
    canvas.Refresh()
    for _ in range(5):
        Rhino.RhinoApp.Wait()
    bmp = System.Drawing.Bitmap(canvas.Width, canvas.Height)
    canvas.DrawToBitmap(bmp, System.Drawing.Rectangle(0, 0, canvas.Width, canvas.Height))
    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    bmp.Save(OUT, System.Drawing.Imaging.ImageFormat.Png)
    log("saved %s (%d x %d), zoom %.2f" % (OUT, bmp.Width, bmp.Height, z))


try:
    run()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
