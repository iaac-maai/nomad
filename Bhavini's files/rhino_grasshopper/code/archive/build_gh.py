# -*- coding: utf-8 -*-
"""Build the Nomad unit-mix Grasshopper definition (runs INSIDE Rhino 7, IronPython 2.7).

Run once in Rhino:  _-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\build_gh.py
It creates sliders -> GhPython component (calls 7_floor_plans/code/unit_mix.py) -> Custom Preview + Panel,
saves nomad/grasshopper/nomad_unit_mix.gh and opens it. Log: nomad/logs/rhino/build_log.txt
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
OUT = os.path.join(ROOT, "rhino_grasshopper", "nomad_unit_mix.gh")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "build_log.txt")
PY_GUID = "410755b1-224a-4c1e-a407-bf32fb45ea7e"        # GhPython Script component
PREVIEW_GUID = "537b0419-bbc2-4ff4-bf08-afe526367b2c"   # Custom Preview

SLIDERS = [  # nickname, min, max, value, decimals
    ("built_area", 50, 5000, 600, 0),
    ("floors", 1, 10, 1, 0),
    ("facade_length", 3, 200, 30, 1),
    ("efficiency", 0.5, 0.95, 0.80, 2),
    ("floor_height", 2.5, 5.0, 3.0, 2),
    ("share_studio", 0, 10, 1, 0),
    ("share_1bed", 0, 10, 2, 0),
    ("share_2bed", 0, 10, 2, 0),
    ("share_3bed", 0, 10, 0, 0),
    ("area_studio", 30, 80, 40, 0),
    ("area_1bed", 30, 100, 50, 0),
    ("area_2bed", 40, 130, 65, 0),
    ("area_3bed", 50, 160, 85, 0),
]
OUTPUTS = ["units", "colours", "slabs", "report", "total", "limit"]

CODE = r'''# Nomad unit mix: sliders -> rules (7_floor_plans/code/unit_mix.py) -> coloured boxes
import sys
P = r"C:\Bhavini\AI\ADs\nomad\7_floor_plans\code"
if P not in sys.path:
    sys.path.append(P)
import unit_mix
reload(unit_mix)
import Rhino.Geometry as rg
import System.Drawing as sd

TYPES = ["studio", "1bed", "2bed", "3bed"]
mix = {"studio": share_studio, "1bed": share_1bed, "2bed": share_2bed, "3bed": share_3bed}
area = {"studio": area_studio, "1bed": area_1bed, "2bed": area_2bed, "3bed": area_3bed}
mix = dict((k, float(v or 0)) for k, v in mix.items())
area = dict((k, float(v or 40)) for k, v in area.items())
B, F, L, E, H = float(built_area), int(floors), float(facade_length), float(efficiency), float(floor_height)

res = unit_mix.solve(B, F, L, E, mix, area, H)
report = unit_mix.report(res)
total, limit = res["total"], res["limit"]

failing = set()
for ok, txt, cite in res["checks"]:
    if not ok:
        failing.add(txt.split(":")[0])
COL = {"studio": sd.Color.FromArgb(133, 183, 235), "1bed": sd.Color.FromArgb(93, 202, 165),
       "2bed": sd.Color.FromArgb(239, 159, 39), "3bed": sd.Color.FromArgb(127, 119, 221)}
RED = sd.Color.FromArgb(226, 75, 74)

depth = B / F / L                       # floor plate: façade length x depth
units, colours, slabs = [], [], []
for f in range(F):
    z = f * H
    slabs.append(rg.Box(rg.Plane(rg.Point3d(0, 0, z - 0.3), rg.Vector3d.ZAxis),
                        rg.Interval(0, L), rg.Interval(0, depth), rg.Interval(0, 0.3)).ToBrep())
x, f = 0.0, 0
order = []
for t in TYPES:
    order += [t] * res["counts"].get(t, 0)
for t in order:
    w = unit_mix.facade_needed(area[t])           # façade each dwelling needs (S/9, min 3 m)
    if x + w > L + 1e-6:
        x, f = 0.0, f + 1
    if f >= F:
        break
    d = min(depth, (area[t] / E) / w)             # built footprint depth
    box = rg.Box(rg.Plane(rg.Point3d(x, 0, f * H), rg.Vector3d.ZAxis),
                 rg.Interval(0.05, w - 0.05), rg.Interval(0, d), rg.Interval(0, H - 0.35))
    units.append(box.ToBrep())
    colours.append(RED if t in failing else COL[t])
    x += w
'''


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    Rhino.RhinoApp.WriteLine(msg)


def build():
    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    open(LOG, "w").close()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParameterSide
    from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel
    PointF = System.Drawing.PointF

    doc = GH_Document()

    # sliders
    sliders = []
    for i, (nick, lo, hi, val, dec) in enumerate(SLIDERS):
        s = GH_NumberSlider()
        s.CreateAttributes()
        s.NickName = nick
        s.Slider.DecimalPlaces = dec
        s.Slider.Minimum = System.Decimal(lo)
        s.Slider.Maximum = System.Decimal(hi)
        s.Slider.Value = System.Decimal(val)
        s.Attributes.Pivot = PointF(0, 30 * i)
        doc.AddObject(s, False)
        sliders.append(s)
    log("sliders: %d" % len(sliders))

    # GhPython component
    py = GH.Instances.ComponentServer.EmitObject(System.Guid(PY_GUID))
    py.CreateAttributes()
    py.Attributes.Pivot = PointF(420, 150)
    doc.AddObject(py, False)
    for p in list(py.Params.Input):
        py.Params.UnregisterInputParameter(p)
    for p in list(py.Params.Output):
        if p.NickName != "out":
            py.Params.UnregisterOutputParameter(p)
    for i, (nick, _, _, _, _) in enumerate(SLIDERS):
        p = py.CreateParameter(GH_ParameterSide.Input, i)
        p.NickName = p.Name = nick
        py.Params.RegisterInputParam(p, i)
    base = py.Params.Output.Count
    for j, nick in enumerate(OUTPUTS):
        p = py.CreateParameter(GH_ParameterSide.Output, base + j)
        p.NickName = p.Name = nick
        py.Params.RegisterOutputParam(p, base + j)
    py.Params.OnParametersChanged()
    py.VariableParameterMaintenance()
    py.Code = CODE
    py.NickName = "Nomad unit mix"
    for i, s in enumerate(sliders):
        py.Params.Input[i].AddSource(s)
    log("python inputs: %d outputs: %d" % (py.Params.Input.Count, py.Params.Output.Count))

    def out(nick):
        for p in py.Params.Output:
            if p.NickName == nick:
                return p

    # previews: units coloured, slabs grey
    for k, (geo, col) in enumerate([("units", "colours"), ("slabs", None)]):
        pv = GH.Instances.ComponentServer.EmitObject(System.Guid(PREVIEW_GUID))
        pv.CreateAttributes()
        pv.Attributes.Pivot = PointF(760, 100 + 120 * k)
        doc.AddObject(pv, False)
        pv.Params.Input[0].AddSource(out(geo))
        if col:
            pv.Params.Input[1].AddSource(out(col))
        else:
            pv.Params.Input[1].AddVolatileData(GH.Kernel.Data.GH_Path(0), 0,
                                               GH.Kernel.Types.GH_Colour(System.Drawing.Color.FromArgb(180, 180, 180)))

    panel = GH_Panel()
    panel.CreateAttributes()
    panel.Attributes.Pivot = PointF(760, 360)
    panel.Attributes.Bounds = System.Drawing.RectangleF(760, 360, 520, 360)
    doc.AddObject(panel, False)
    panel.AddSource(out("report"))

    io = GH_DocumentIO(doc)
    ok = io.SaveQuiet(OUT)
    log("saved %s: %s" % (OUT, ok))
    gh.OpenDocument(OUT)
    log("opened in Grasshopper")


try:
    build()
except Exception:
    log("ERROR\n" + traceback.format_exc())
