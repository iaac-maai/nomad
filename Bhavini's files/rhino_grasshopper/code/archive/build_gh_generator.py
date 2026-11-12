# -*- coding: utf-8 -*-
"""Build the Nomad floor-plan generator Grasshopper definition (runs INSIDE Rhino 7, IronPython 2.7).

Inputs on the canvas:
  - shop_index slider: one of the clean shops from Swiss Dwellings (7_floor_plans/output/clean/nomad_shells.json)
  - "Your shop outline" curve: right-click > Set one curve, pick a closed outline you drew/traced in Rhino.
    When it is set, it is used instead of the dataset shop.
  - "Street facade" curve (optional): the outline edges near this curve count as façade.
    Without it, every outline edge longer than 3 m counts as façade.
  - n_studio, n_1bed, n_2bed, n_3bed sliders: the unit mix you want
  - compact toggle: room sizes at the 25th percentile of rule-passing flats instead of the median
  - floor_height slider
Outputs: rooms in 3D coloured by room type (red = fails a rule), flat outlines, report panel.
Run once in Rhino:  _-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\build_gh_generator.py
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
OUT = os.path.join(ROOT, "rhino_grasshopper", "nomad_plan_generator.gh")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "build_generator_log.txt")
PY_GUID = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
PREVIEW_GUID = "537b0419-bbc2-4ff4-bf08-afe526367b2c"

SLIDERS = [("shop_index", 0, 179, 0, 0), ("n_studio", 0, 12, 0, 0), ("n_1bed", 0, 12, 2, 0),
           ("n_2bed", 0, 12, 1, 0), ("n_3bed", 0, 12, 0, 0), ("floor_height", 2.6, 5.0, 3.0, 2)]
OUTPUTS = ["rooms", "colours", "flats", "shell", "report", "works"]

CODE = r'''# Nomad floor-plan generator: shop outline + unit mix -> flats and rooms, checked against the rulebook
import sys, json, io
P = r"C:\Bhavini\AI\ADs\nomad\7_floor_plans\code"
if P not in sys.path:
    sys.path.append(P)
import layout
reload(layout)
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import System.Drawing as sd

ROOT = r"C:\Bhavini\AI\ADs\nomad"
if "nomad_shells" not in globals():
    with io.open(ROOT + r"\7_floor_plans\output\clean\nomad_shells.json", encoding="utf-8") as f:
        nomad_shells = json.load(f)["shells"]
    with io.open(ROOT + r"\7_floor_plans\output\generation\room_programs.json", encoding="utf-8") as f:
        nomad_programs = json.load(f)["programs"]

def as_curve(x):
    if x is None:
        return None
    if isinstance(x, rg.Curve):
        return x
    try:
        return rs.coercecurve(x)
    except Exception:
        return None

def polyline_pts(crv):
    ok, pl = crv.TryGetPolyline()
    if not ok:
        pl = crv.ToPolyline(0.05, 0.1, 0.5, 100).ToPolyline()
    pts = [(p.X, p.Y) for p in pl]
    if pts and (abs(pts[0][0] - pts[-1][0]) > 1e-6 or abs(pts[0][1] - pts[-1][1]) > 1e-6):
        pts.append(pts[0])
    return pts

shell_crv, facade_crv = as_curve(shop_outline), as_curve(street_facade)
if shell_crv is not None and shell_crv.IsClosed:
    outline = polyline_pts(shell_crv)
    edges = [[list(a), list(b)] for a, b in zip(outline[:-1], outline[1:])]
    if facade_crv is not None:
        def near(p):
            ok, t = facade_crv.ClosestPoint(rg.Point3d(p[0], p[1], 0))
            return ok and facade_crv.PointAt(t).DistanceTo(rg.Point3d(p[0], p[1], 0)) < 0.5
        facade = [e for e in edges if near(e[0]) and near(e[1])]
    else:
        facade = [e for e in edges if ((e[1][0]-e[0][0])**2 + (e[1][1]-e[0][1])**2) ** 0.5 >= 3.0]
    name, height = "your outline", 2.8
else:
    s = nomad_shells[int(shop_index) % len(nomad_shells)]
    outline, facade, height = s["outline"], s["facade"], s["height_m"]
    name = "dataset shop %d (former use: %s)" % (s["shell_id"], s["former_use"][:60])

mix = {"studio": int(n_studio or 0), "1bed": int(n_1bed or 0), "2bed": int(n_2bed or 0), "3bed": int(n_3bed or 0)}
plan = layout.generate(outline, facade, height, mix, nomad_programs, "compact" if compact else "typical")
report = "Shop: %s\n%s" % (name, layout.report(plan))
works = plan["proposal_ok"]

COL = {"living": sd.Color.FromArgb(239, 159, 39), "bed_main": sd.Color.FromArgb(127, 119, 221),
       "bed": sd.Color.FromArgb(175, 169, 236), "kitchen": sd.Color.FromArgb(250, 199, 117),
       "bath": sd.Color.FromArgb(133, 183, 235), "hall": sd.Color.FromArgb(200, 200, 200)}
RED = sd.Color.FromArgb(226, 75, 74)
H = float(floor_height or 3.0) - 0.3

def closed_crv(pts, z=0.0):
    p = [rg.Point3d(x, y, z) for x, y in pts]
    if p[0].DistanceTo(p[-1]) > 1e-6:
        p.append(p[0])
    return rg.PolylineCurve(p)

rooms, colours, flats = [], [], []
for u in plan["units"]:
    if len(u["outline"]) >= 3:
        flats.append(closed_crv(u["outline"], 0.02))
    for r in u["rooms"]:
        if len(r["pts"]) < 3:
            continue
        srf = rg.Surface.CreateExtrusion(closed_crv(r["pts"]), rg.Vector3d(0, 0, H if r["kind"] != "hall" else 0.05))
        if srf is None:
            continue
        b = srf.ToBrep().CapPlanarHoles(0.01)
        if b is None:
            continue
        rooms.append(b)
        colours.append(COL.get(r["kind"], COL["hall"]) if r.get("ok", True) else RED)
shell = closed_crv(outline)
'''


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def build():
    open(LOG, "w").close()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParameterSide
    from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel, GH_BooleanToggle
    from Grasshopper.Kernel.Parameters import Param_Curve
    PointF = System.Drawing.PointF
    doc = GH_Document()

    sources = {}
    for i, (nick, lo, hi, val, dec) in enumerate(SLIDERS):
        s = GH_NumberSlider()
        s.CreateAttributes()
        s.NickName = nick
        s.Slider.DecimalPlaces = dec
        s.Slider.Minimum = System.Decimal(lo)
        s.Slider.Maximum = System.Decimal(hi)
        s.Slider.Value = System.Decimal(val)
        s.Attributes.Pivot = PointF(0, 140 + 30 * i)
        doc.AddObject(s, False)
        sources[nick] = s
    t = GH_BooleanToggle()
    t.CreateAttributes()
    t.NickName = "compact"
    t.Value = False
    t.Attributes.Pivot = PointF(0, 140 + 30 * len(SLIDERS))
    doc.AddObject(t, False)
    sources["compact"] = t
    for j, (nick, label) in enumerate([("shop_outline", "Your shop outline (right-click > Set one curve)"),
                                        ("street_facade", "Street facade (optional)")]):
        c = Param_Curve()
        c.CreateAttributes()
        c.NickName = label
        c.Attributes.Pivot = PointF(0, 20 + 50 * j)
        doc.AddObject(c, False)
        sources[nick] = c

    inputs = ["shop_index", "shop_outline", "street_facade", "n_studio", "n_1bed", "n_2bed", "n_3bed", "compact", "floor_height"]
    py = GH.Instances.ComponentServer.EmitObject(System.Guid(PY_GUID))
    py.CreateAttributes()
    py.Attributes.Pivot = PointF(460, 180)
    doc.AddObject(py, False)
    for p in list(py.Params.Input):
        py.Params.UnregisterInputParameter(p)
    for p in list(py.Params.Output):
        if p.NickName != "out":
            py.Params.UnregisterOutputParameter(p)
    for i, nick in enumerate(inputs):
        p = py.CreateParameter(GH_ParameterSide.Input, i)
        p.NickName = p.Name = nick
        p.Optional = True
        py.Params.RegisterInputParam(p, i)
    base = py.Params.Output.Count
    for j, nick in enumerate(OUTPUTS):
        q = py.CreateParameter(GH_ParameterSide.Output, base + j)
        q.NickName = q.Name = nick
        py.Params.RegisterOutputParam(q, base + j)
    py.Params.OnParametersChanged()
    py.VariableParameterMaintenance()
    py.Code = CODE
    py.NickName = "Nomad plan generator"
    for i, nick in enumerate(inputs):
        py.Params.Input[i].AddSource(sources[nick])

    def out(nick):
        for q in py.Params.Output:
            if q.NickName == nick:
                return q

    pv = GH.Instances.ComponentServer.EmitObject(System.Guid(PREVIEW_GUID))
    pv.CreateAttributes()
    pv.Attributes.Pivot = PointF(820, 120)
    doc.AddObject(pv, False)
    pv.Params.Input[0].AddSource(out("rooms"))
    pv.Params.Input[1].AddSource(out("colours"))

    panel = GH_Panel()
    panel.CreateAttributes()
    panel.Attributes.Pivot = PointF(820, 260)
    panel.Attributes.Bounds = System.Drawing.RectangleF(820, 260, 640, 420)
    doc.AddObject(panel, False)
    panel.AddSource(out("report"))

    ok = GH_DocumentIO(doc).SaveQuiet(OUT)
    log("saved %s: %s" % (OUT, ok))
    gh.OpenDocument(OUT)
    log("opened")


try:
    build()
except Exception:
    log("ERROR\n" + traceback.format_exc())
