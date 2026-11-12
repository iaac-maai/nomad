# -*- coding: utf-8 -*-
"""Build the Nomad dataset viewer Grasshopper definition (runs INSIDE Rhino 7, IronPython 2.7).

A slider picks one of the 300 sample units checked by 7_floor_plans/code/check_swiss_dwellings.py
(4_laws_and_rules/output/rule_tests/sd_sample.json); the GhPython component draws its rooms (green = passes the room rules,
red = fails, grey = other rooms) and a Panel lists every rule with PASS/FAIL.
Run once in Rhino:  _-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\build_gh_viewer.py
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
OUT = os.path.join(ROOT, "rhino_grasshopper", "nomad_dataset_viewer.gh")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "build_viewer_log.txt")
PY_GUID = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
PREVIEW_GUID = "537b0419-bbc2-4ff4-bf08-afe526367b2c"

CODE = r'''# Nomad dataset viewer: one real floor plan (Swiss Dwellings) checked against the Nomad rulebook
import json, io
import Rhino.Geometry as rg
import System.Drawing as sd
P = r"C:\Bhavini\AI\ADs\nomad\4_laws_and_rules\output\rule_tests\sd_sample.json"
if "nomad_sample" not in globals():
    with io.open(P, encoding="utf-8") as f:
        nomad_sample = json.load(f)
data = nomad_sample
u = data["units"][int(unit_index) % len(data["units"])]
GREEN, RED, GREY = sd.Color.FromArgb(93, 202, 165), sd.Color.FromArgb(226, 75, 74), sd.Color.FromArgb(200, 200, 200)
MAIN = ("BEDROOM", "ROOM", "LIVING_ROOM", "LIVING_DINING", "KITCHEN_DINING", "DINING")
rooms, colours, labels, points = [], [], [], []
for r in u["rooms"]:
    pl = rg.Polyline([rg.Point3d(x, y, 0) for x, y in r["xy"]])
    crv = pl.ToNurbsCurve()
    breps = rg.Brep.CreatePlanarBreps(crv, 0.001)
    if not breps:
        continue
    rooms.append(breps[0])
    colours.append(GREY if r["type"] not in MAIN else (GREEN if r["ok"] else RED))
    c = rg.AreaMassProperties.Compute(crv).Centroid
    points.append(c)
    labels.append("%s %.1f m2" % (r["type"].lower(), r["area"]))
lines = ["Unit %d (%s) - %.1f m2 useful, %d bedrooms" % (u["unit_id"], u["usage"], u["useful_m2"], u["bedrooms"])]
for k, ok in sorted(u["rules"].items()):
    lines.append("%s  %s" % ("PASS" if ok else "FAIL", data["rules"][k]))
report = "\n".join(lines)
'''


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg.encode("utf-8") if isinstance(msg, unicode) else msg)
        f.write("\n")


def build():
    open(LOG, "w").close()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParameterSide
    from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel
    PointF = System.Drawing.PointF
    doc = GH_Document()

    s = GH_NumberSlider()
    s.CreateAttributes()
    s.NickName = "unit_index"
    s.Slider.DecimalPlaces = 0
    s.Slider.Minimum = System.Decimal(0)
    s.Slider.Maximum = System.Decimal(299)
    s.Slider.Value = System.Decimal(0)
    s.Attributes.Pivot = PointF(0, 100)
    doc.AddObject(s, False)

    py = GH.Instances.ComponentServer.EmitObject(System.Guid(PY_GUID))
    py.CreateAttributes()
    py.Attributes.Pivot = PointF(300, 100)
    doc.AddObject(py, False)
    for p in list(py.Params.Input):
        py.Params.UnregisterInputParameter(p)
    for p in list(py.Params.Output):
        if p.NickName != "out":
            py.Params.UnregisterOutputParameter(p)
    p = py.CreateParameter(GH_ParameterSide.Input, 0)
    p.NickName = p.Name = "unit_index"
    py.Params.RegisterInputParam(p, 0)
    names = ["rooms", "colours", "labels", "points", "report"]
    base = py.Params.Output.Count
    for j, nick in enumerate(names):
        q = py.CreateParameter(GH_ParameterSide.Output, base + j)
        q.NickName = q.Name = nick
        py.Params.RegisterOutputParam(q, base + j)
    py.Params.OnParametersChanged()
    py.VariableParameterMaintenance()
    py.Code = CODE
    py.NickName = "Nomad dataset viewer"
    py.Params.Input[0].AddSource(s)

    def out(nick):
        for q in py.Params.Output:
            if q.NickName == nick:
                return q

    pv = GH.Instances.ComponentServer.EmitObject(System.Guid(PREVIEW_GUID))
    pv.CreateAttributes()
    pv.Attributes.Pivot = PointF(620, 60)
    doc.AddObject(pv, False)
    pv.Params.Input[0].AddSource(out("rooms"))
    pv.Params.Input[1].AddSource(out("colours"))

    panel = GH_Panel()
    panel.CreateAttributes()
    panel.Attributes.Pivot = PointF(620, 200)
    panel.Attributes.Bounds = System.Drawing.RectangleF(620, 200, 620, 300)
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
