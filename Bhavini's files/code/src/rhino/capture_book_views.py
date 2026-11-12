# -*- coding: utf-8 -*-
"""Take pictures of NOMAD.gh's results for the lab book (book/figures/rhino_*.png).

Runs in a separate Rhino that opens no file, so rhino/NOMAD.3dm is never touched; it closes itself.
For each case it sets the NOMAD inputs, solves, adds the coloured rooms to the empty document,
captures a top and a 3D view, then clears the document.
Run:  Rhino.exe /nosplash /runscript="_-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\capture_book_views.py"
"""
import os, io, json, math, traceback
import Rhino, System, clr
import Rhino.Geometry as rg
import scriptcontext as sc

ROOT = r"C:\Bhavini\AI\ADs\nomad"
GHFILE = os.path.join(ROOT, "grasshopper", "NOMAD.gh")
OUT = os.path.join(ROOT, "book", "figures")
LOG = os.path.join(ROOT, "logs", "rhino", "capture_log.txt")
PLAN = (os.path.join(ROOT, r"data\datasets\test_plans\145057.png"), 145057)
CASES = [  # name, settings
    ("rhino_dataset_shop_2x1bed_1x2bed", {"shop_index": 5, "n_1bed": 2, "n_2bed": 1}),
    ("rhino_dataset_shop_5x1bed_2x2bed", {"shop_index": 42, "n_1bed": 5, "n_2bed": 2}),
    ("rhino_plan_image_1bed", {"plan": True, "n_1bed": 1, "n_2bed": 0}),
]


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def longest_facade(sid):
    with io.open(ROOT + r"\data\clean\nomad_shells.json", encoding="utf-8") as f:
        s = [x for x in json.load(f)["shells"] if x["shell_id"] == sid][0]
    return max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in s["facade"])


def set_inputs(doc, GH, st):
    for obj in doc.Objects:
        n = obj.NickName
        if st.get("plan") and n.startswith("Plan file"):
            obj.PersistentData.Clear()
            obj.PersistentData.Append(GH.Kernel.Types.GH_String(PLAN[0]))
        elif n == "read plan":
            obj.Value = bool(st.get("plan"))
        elif n == "known_facade_m" and st.get("plan"):
            obj.Slider.Value = System.Decimal(round(longest_facade(PLAN[1]), 1))
        elif n in st and hasattr(obj, "Slider"):
            obj.Slider.Value = System.Decimal(st[n])


def output(doc, nick, name):
    for obj in doc.Objects:
        if obj.NickName == nick:
            for p in obj.Params.Output:
                if p.NickName == name:
                    return [g for g in p.VolatileData.AllData(True)]
    return []


def capture(view, path, top):
    view.ActiveViewport.DisplayMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    if top:
        view.ActiveViewport.SetProjection(Rhino.Display.DefinedViewportProjection.Top, "Top", False)
    else:
        view.ActiveViewport.SetProjection(Rhino.Display.DefinedViewportProjection.Perspective, "Perspective", False)
        vp = view.ActiveViewport
        vp.SetCameraLocations(rg.Point3d(0, 0, 0), rg.Point3d(-25, -35, 30))
    view.ActiveViewport.ZoomExtents()
    sc.doc.Views.Redraw()
    bmp = view.CaptureToBitmap(System.Drawing.Size(1400, 1000))
    bmp.Save(path, System.Drawing.Imaging.ImageFormat.Png)
    log("saved " + path)


def run():
    open(LOG, "w").close()
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_DocumentIO
    view = sc.doc.Views.ActiveView
    for name, st in CASES:
        io_ = GH_DocumentIO()
        io_.Open(GHFILE)
        doc = io_.Document
        doc.Enabled = True
        set_inputs(doc, GH, st)
        doc.NewSolution(True)
        rooms = output(doc, "NOMAD", "rooms")
        cols = output(doc, "NOMAD", "colours")
        shell = output(doc, "NOMAD", "shell")
        facade = output(doc, "NOMAD", "facade")
        log("%s: %d rooms" % (name, len(rooms)))
        ids = []
        for i, g in enumerate(rooms):
            a = Rhino.DocObjects.ObjectAttributes()
            a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            if i < len(cols):
                a.ObjectColor = cols[i].Value
            ids.append(sc.doc.Objects.AddBrep(g.Value, a))
        for g, c in [(x, System.Drawing.Color.Gray) for x in shell] + [(x, System.Drawing.Color.RoyalBlue) for x in facade]:
            a = Rhino.DocObjects.ObjectAttributes()
            a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            a.ObjectColor = c
            a.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
            ids.append(sc.doc.Objects.AddCurve(g.Value, a))
        capture(view, os.path.join(OUT, name + "_top.png"), True)
        capture(view, os.path.join(OUT, name + "_3d.png"), False)
        for i in ids:
            sc.doc.Objects.Delete(i, True)
        doc.Enabled = False
    log("done")


try:
    run()
except Exception:
    log("ERROR\n" + traceback.format_exc())
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
