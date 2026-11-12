# -*- coding: utf-8 -*-
"""Draw a facade read by NOMAD (results/facade/<ref>/openings.json) into THE Rhino file, rhino/NOMAD.3dm.

Layer "06 NOMAD experiments::facade <address>" with three parts side by side, right of everything already drawn:
  1 photo straightened   the straightened Catastro photo, at true size in metres (private file only)
  2 facade drawing       outline, floor lines with heights, openings by kind (window, balcony door, door, shopfront, balcony)
  3 3D facade            the wall standing up, 0,40 m thick, openings cut out, glass set back, balcony slabs and railings
Runs in a separate Rhino (never while the user has NOMAD.3dm open); backup first; re-running replaces this layer only.
Run: powershell -File src\\rhino\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\record_facade.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\logs\\rhino\\facade_log.txt
"""
import os, io, json, sys, shutil, time, traceback
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import System
import System.Drawing as sd

ROOT = r"C:\Bhavini\AI\ADs\nomad"
for _s in ("rhino", "check", "generate"):
    sys.path.append(os.path.join(ROOT, "src", _s))
FILE = os.path.join(ROOT, "rhino", "NOMAD.3dm")
LOG = os.path.join(ROOT, "logs", "rhino", "facade_log.txt")
REFS = ["9331705DF2893A"]
COL = {"window": (44, 93, 143), "balcony door": (110, 155, 198), "door": (201, 138, 43), "shopfront": (63, 143, 90),
       "balcony": (196, 71, 58), "wall": (217, 217, 212), "glass": (120, 160, 190), "inferred": (175, 188, 200), "hidden": (63, 143, 90), "line": (138, 138, 133), "ink": (17, 18, 17)}
TOL = 0.001
ONLY_2D = True        # user, 10 Nov: 3D later; redraw the photo + drawing only, leave the 3D layer as it is


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def attrs(doc, layer, rgb):
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = layer
    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    a.ObjectColor = sd.Color.FromArgb(255, rgb[0], rgb[1], rgb[2])
    return a


def rect(doc, layer, x0, y0, x1, y1, rgb, fill=False, solid=None):
    pl = rg.Polyline([rg.Point3d(x0, y0, 0), rg.Point3d(x1, y0, 0), rg.Point3d(x1, y1, 0), rg.Point3d(x0, y1, 0), rg.Point3d(x0, y0, 0)])
    crv = pl.ToNurbsCurve()
    doc.Objects.AddCurve(crv, attrs(doc, layer, rgb))
    if fill and solid is not None:
        hs = rg.Hatch.Create(crv, solid, 0.0, 1.0, TOL)
        for h in hs or []:
            doc.Objects.AddHatch(h, attrs(doc, layer, rgb))


def box(doc, layer, x0, y0, z0, x1, y1, z1, rgb):
    b = rg.Box(rg.BoundingBox(rg.Point3d(x0, y0, z0), rg.Point3d(x1, y1, z1))).ToBrep()
    doc.Objects.AddBrep(b, attrs(doc, layer, rgb))
    return b


def clear(doc, path):
    i = doc.Layers.FindByFullPath(path, -1)
    if i < 0:
        return
    todo = [doc.Layers[i]]
    while todo:
        ly = todo.pop()
        for o in doc.Objects.FindByLayer(ly) or []:
            doc.Objects.Delete(o, True)
        for ch in doc.Layers:
            if ch.ParentLayerId == ly.Id and not ch.IsDeleted:
                todo.append(ch)


def draw(doc, sheet, ref, X0):
    d = os.path.join(ROOT, "results", "facade", ref)
    f = json.load(io.open(os.path.join(d, "openings.json"), encoding="utf-8"))
    W, H, ops, lines = f["facade_m"], f["height_m"], f["openings"], f["floor_lines_m"]
    base = sheet.PARENT + "::facade " + f["address"]
    if ONLY_2D:
        for sub in ("1 photo straightened", "2 facade drawing"):
            clear(doc, base + "::" + sub)
    else:
        clear(doc, base)
    L1 = sheet._layer(doc, base + "::1 photo straightened")
    L2 = sheet._layer(doc, base + "::2 facade drawing")
    L3 = sheet._layer(doc, base + "::3 3D facade")
    pen = sheet.Pen(doc, dict((k, L2) for k in sheet.SUBLAYERS), 1.0)
    solid = doc.HatchPatterns.FindName("Solid").Index
    GAP = 8.0
    # title
    pen.text(u"Facade read from a photo: %s (%s)" % (f["address"], ref), X0, H + 7.0, 1.6, bold=True, width=3 * W + 2 * GAP)
    pen.text(u"Photo straightened automatically (lens bend + vertical lines). Width %.1f m = Catastro street front; height %.1f m = ICGC LiDAR roof. "
             u"Floors from the facade's horizontal lines and balconies. Openings: Grounding DINO, checked bay by bay, snapped to the facade's column grid. %s" % (W, H, f["source"]),
             X0, H + 4.6, 0.7, rgb=(110, 116, 126), width=3 * W + 2 * GAP)
    # 1 photo
    path = os.path.join(d, "facade_photo_m.jpg")
    gid = doc.Objects.AddPictureFrame(rg.Plane(rg.Point3d(X0, 0, 0), rg.Vector3d.ZAxis), path, False, W, H, True, True)
    o = doc.Objects.FindId(gid)
    if o is not None:
        o.Attributes.LayerIndex = L1
        o.CommitChanges()
    pen.text(u"1  Photo, straightened (private)", X0, -1.6, 0.8, bold=True, width=W)
    # 2 drawing
    x2 = X0 + W + GAP
    rect(doc, L2, x2, 0, x2 + W, H, COL["wall"], True, solid)
    rect(doc, L2, x2, 0, x2 + W, H, COL["ink"])
    for i, z in enumerate(lines):
        if i:
            doc.Objects.AddLine(rg.Line(rg.Point3d(x2, z, 0.01), rg.Point3d(x2 + W, z, 0.01)), attrs(doc, L2, COL["line"]))
        pen.text(u"floor %d  +%.2f m" % (i, z), x2 + W + 0.5, z + 0.9, 0.6, width=8.0)
    for op in ops:
        k = op["kind"]
        if k == "balcony":
            rect(doc, L2, x2 + op["x0"], op["sill"], x2 + op["x1"], op["head"], COL["inferred"] if op.get("inferred") else COL[k])
        else:
            rect(doc, L2, x2 + op["x0"], op["sill"], x2 + op["x1"], op["head"], COL["inferred"] if op.get("inferred") else COL.get(k, COL["window"]), True, solid)
    for hd in f.get("hidden") or []:
        x0, z0, x1, z1 = hd["m"]
        rect(doc, L2, x2 + x0, z0, x2 + x1, min(z1, H), COL["hidden"])
        pen.text(u"hidden by a tree", x2 + x0 + 0.3, min(z1, H) - 0.8, 0.5, rgb=COL["hidden"], width=6.0)
    pen.text(u"Light grey-blue = inferred (hidden by a tree, taken from the same column or floor). Green outline = hidden by a tree.",
             x2, -4.4, 0.5, rgb=(110, 116, 126), width=W + 8)
    if f.get("axis"):
        doc.Objects.AddLine(rg.Line(rg.Point3d(x2 + f["axis"], -0.6, 0.02), rg.Point3d(x2 + f["axis"], H + 0.6, 0.02)), attrs(doc, L2, (196, 71, 58)))
        pen.text(u"mirror axis", x2 + f["axis"] + 0.2, H + 1.4, 0.5, rgb=(196, 71, 58), width=5.0)
    pen.text(u"2  Facade drawing (NOMAD)", x2, -1.6, 0.8, bold=True, width=W)
    pen.text(u"%.1f m" % W, x2 + W / 2 - 1.0, -3.0, 0.6, width=6.0)
    if ONLY_2D:
        log("%s: %d openings (2D only)" % (ref, len(ops)))
        return x2 + 2 * W + GAP + 6.0
    # 3 3D: wall in the XZ plane, standing on y = 0 (street side at y = 0, inside y > 0)
    x3 = x2 + W + GAP + 6.0
    T = 0.40
    wall = rg.Box(rg.BoundingBox(rg.Point3d(x3, 0, 0), rg.Point3d(x3 + W, T, H))).ToBrep()
    cutters = []
    for op in ops:
        if op["kind"] != "balcony":
            cutters.append(rg.Box(rg.BoundingBox(rg.Point3d(x3 + op["x0"], -0.1, op["sill"]), rg.Point3d(x3 + op["x1"], T + 0.1, op["head"]))).ToBrep())
    res = rg.Brep.CreateBooleanDifference([wall], cutters, TOL) if cutters else None
    for b in (res or [wall]):
        doc.Objects.AddBrep(b, attrs(doc, L3, COL["wall"]))
    for op in ops:
        k = op["kind"]
        if k == "balcony":
            box(doc, L3, x3 + op["x0"], -0.9, op["sill"], x3 + op["x1"], 0, op["sill"] + 0.15, (138, 138, 133))
            box(doc, L3, x3 + op["x0"], -0.92, op["sill"] + 0.15, x3 + op["x1"], -0.88, op["sill"] + 1.0, COL["inferred"] if op.get("inferred") else COL[k])
        else:
            pane = rg.Brep.CreateFromCornerPoints(rg.Point3d(x3 + op["x0"], 0.25, op["sill"]), rg.Point3d(x3 + op["x1"], 0.25, op["sill"]),
                                                  rg.Point3d(x3 + op["x1"], 0.25, op["head"]), rg.Point3d(x3 + op["x0"], 0.25, op["head"]), TOL)
            doc.Objects.AddBrep(pane, attrs(doc, L3, COL["inferred"] if op.get("inferred") else COL.get(k, COL["window"])))
    for z in lines[1:]:                                    # floor slabs behind the wall, so the floors read in 3D
        box(doc, L3, x3, T, z - 0.15, x3 + W, T + 6.0, z, (200, 200, 195))
    pen.text(u"3  The same facade in 3D, openings cut in the wall", x3, -1.6, 0.8, bold=True, width=W)
    log("%s: %d openings, wall pieces %d" % (ref, len(ops), len(res or [wall])))
    return x3 + W


def main():
    open(LOG, "w").close()
    import nomad_sheet as sheet
    bdir = os.path.join(ROOT, "rhino", "backups")
    if not os.path.isdir(bdir):
        os.makedirs(bdir)
    backup = os.path.join(bdir, "NOMAD_%s.3dm" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(FILE, backup)
    log("backup: " + backup)
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % FILE, False)
    doc = Rhino.RhinoDoc.ActiveDoc
    log("opened %s: %d objects" % (doc.Path, doc.Objects.Count))
    old = rg.BoundingBox.Empty                             # draw where it was before (same place in the file)
    for ref in REFS:
        a = json.load(io.open(os.path.join(ROOT, "results", "facade", ref, "openings.json"), encoding="utf-8"))["address"]
        i = doc.Layers.FindByFullPath(sheet.PARENT + "::facade " + a + "::1 photo straightened", -1)
        if i >= 0:
            for o in doc.Objects.FindByLayer(doc.Layers[i]) or []:
                old.Union(o.Geometry.GetBoundingBox(True))
    if old.IsValid:
        X0 = old.Min.X
    else:
        bb = rg.BoundingBox.Empty
        for o in doc.Objects:
            bb.Union(o.Geometry.GetBoundingBox(True))
        X0 = (bb.Max.X if bb.IsValid else 0.0) + 60.0
    for ref in REFS:
        X0 = draw(doc, sheet, ref, X0) + 30.0
    doc.Views.Redraw()
    Rhino.RhinoApp.RunScript("_-Save _Enter", False)
    log("saved %s (%d objects, %.1f MB)" % (FILE, doc.Objects.Count, os.path.getsize(FILE) / 1e6))


try:
    main()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
