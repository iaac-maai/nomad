# -*- coding: utf-8 -*-
"""Build rhino_grasshopper/NOMAD.gh as SMALL components (review of 29 Oct 2026: "a node with 15 inputs is not usable").

Runs INSIDE Rhino 7 (IronPython 2.7), then closes Rhino. The old one-component file is kept in old/grasshopper_archive.
Each component does one step and passes its result (a Python object) to the next, left to right:

  1 Read plan      plan_file, read_plan_on, known_facade_m, floor_height          -> plan_shop, note
  2 Shop           plan_shop, shop_outline, street_facade, shop_index, floor_height -> shop, note
  3 Zoning         shop, address                                                   -> shop, note
  4 Flats asked    n_studio, n_1bed, n_2bed, n_3bed                                -> mix
  5 Flat sizes     m2_studio, m2_1bed, m2_2bed, m2_3bed, compact                   -> programs, size
  6 Check+layouts  shop, mix, programs, size                                       -> case, verdict, works, report
  7 Daylight       shop                                                            -> daylight (the daylight model, real shops)
  8 3D preview     shop, case, floor_height                                        -> rooms, colours, flats, shell, facade, plan_image, plan_material
  9 Make           shop, mix, programs, case, make_sheet, make_demo                -> report
 10 This file      run_inbox, show_experiments                                     -> report
The report panel collects every component's text. The logic itself stays in src/ (nomad_core, layout, flags, ...).
Run: powershell -File rhino_grasshopper\\code\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\code\\build_nomad_nodes.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\rhino_grasshopper\\logs\\build_nodes_log.txt
"""
import os, shutil, time, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
OUT = os.path.join(ROOT, "rhino_grasshopper", "NOMAD.gh")
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "build_nodes_log.txt")
PY_GUID = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
PREVIEW_GUID = "537b0419-bbc2-4ff4-bf08-afe526367b2c"

WRAPPER = r'''
# Grasshopper splits a Python dict or list into its items on a wire: pass whole objects in a wrapper, unwrap on arrival
import Grasshopper
def W(x):
    return Grasshopper.Kernel.Types.GH_ObjectWrapper(x) if x is not None else None
def U(x):
    return x.Value if isinstance(x, Grasshopper.Kernel.Types.GH_ObjectWrapper) else x
'''
PRE = r'''import sys, os
P = r"C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code"
if P not in sys.path:
    sys.path.append(P)
import nomad_core as core
'''

NODES = [
    ("1 Read plan", ["plan_file", "read_plan_on", "known_facade_m", "floor_height"], ["plan_shop", "note"], PRE + r'''
# reads a plan drawing (PNG/JPG/PDF): outline + street facade (2_building/code/read_plan.py)
plan_shop, note = None, ""
path = str(plan_file).strip('"') if plan_file else ""
if path and read_plan_on and os.path.exists(path):
    s = core.shop_from_plan(path, float(known_facade_m or 0), float(floor_height or 3.0) - 0.3)
    if s.get("ok"):
        plan_shop, note = s, "Plan read: %s shows what the reader found." % s["read_preview"]
    else:
        note = "Plan reader could not read the file: %s" % s.get("reason")
'''),
    ("2 Shop", ["plan_shop", "shop_outline", "street_facade", "shop_index", "floor_height"], ["shop", "note"], PRE + r'''
# the shop: a read plan > your curve > a dataset shop
import Rhino.Geometry as rg
def pts_of(crv):
    ok, pl = crv.TryGetPolyline()
    if not ok:
        pl = crv.ToPolyline(0.05, 0.1, 0.5, 100).ToPolyline()
    q = [(p.X, p.Y) for p in pl]
    if q and q[0] != q[-1]:
        q.append(q[0])
    return q
shop, note = plan_shop, ""
if shop is None and shop_outline is not None and shop_outline.IsClosed:
    near = None
    if street_facade is not None:
        def near(q):
            ok, t = street_facade.ClosestPoint(rg.Point3d(q[0], q[1], 0))
            return ok and street_facade.PointAt(t).DistanceTo(rg.Point3d(q[0], q[1], 0)) < 0.5
    shop = core.shop_from_curve(pts_of(shop_outline), near, float(floor_height or 3.0) - 0.3)
    note = "Shop: your outline."
if shop is None:
    shop = core.shop_from_dataset(shop_index or 0)
    note = "Shop: dataset shop %s." % shop.get("name")
'''),
    ("3 Zoning", ["shop", "address"], ["shop_z", "note"], PRE + r'''
# step 3: the zone of a Barcelona address or cadastral reference (MUC map, PGM art. 225.7)
shop_z = dict(shop) if shop else None
note = core.add_zoning(shop_z, str(address).strip() if address else "") if shop_z else ""
'''),
    ("4 Flats asked", ["n_studio", "n_1bed", "n_2bed", "n_3bed"], ["mix"], r'''
mix = {"studio": int(n_studio or 0), "1bed": int(n_1bed or 0), "2bed": int(n_2bed or 0), "3bed": int(n_3bed or 0)}
'''),
    ("5 Flat sizes", ["m2_studio", "m2_1bed", "m2_2bed", "m2_3bed", "compact"], ["programs", "size"], PRE + r'''
# m² per flat type (0 = the sizes learned from 13,444 real flats that pass every rule)
import layout
sizes = dict((k, float(v)) for k, v in (("studio", m2_studio), ("1bed", m2_1bed), ("2bed", m2_2bed), ("3bed", m2_3bed)) if v and float(v) > 0)
programs = layout.with_targets(core.data()["programs"], sizes) if sizes else None
size = "compact" if compact else "typical"
'''),
    ("6 Check + layouts", ["shop", "mix", "programs", "size"], ["case", "verdict", "works", "report"], PRE + r'''
# step 6 check (rule cards, YES / PARTLY / NO) + the smallest change that houses more flats
import flags
case = core.run(shop, mix, size or "typical", programs=programs)
B, A = case["before"], case["after"]
verdict = "%s -> %s" % (B["res"]["verdict"], A["res"]["verdict"])
works = A["plan"]["proposal_ok"]
report = "BEFORE (as it is): %s, %d of %d flats pass\nAFTER: %s, %d of %d flats pass  -  %s\n%s\n\n%s" % (
    B["res"]["verdict"], B["res"]["flats_passing"], B["res"]["flats_asked"], A["res"]["verdict"], A["res"]["flats_passing"],
    A["res"]["flats_asked"], case["changed"], "\n".join(A["plan"].get("interventions", [])), flags.summary_text(A["res"]))
'''),
    ("7 Daylight", ["shop"], ["daylight"], r'''
# Bars's daylight model (iaac-maai/nomad exp1, 50 Ladybug/Honeybee runs + XGBoost), predicted for the real Barcelona
# shops by 5_daylight/code/bars_daylight.py. Read here by cadastral reference (give an address in "3 Zoning").
import json, io
f = r"C:\Bhavini\AI\ADs\nomad\5_daylight\output\lit_depth.json"
z = (shop or {}).get("zoning") or {}
ref = (z.get("ref") or "")[:14]
daylight = "Daylight: give a Barcelona address in 3 Zoning to see Bars's prediction (real shops only)."
if ref and os.path.exists(f):
    d = json.load(io.open(f, encoding="utf-8")).get(ref)
    if d:
        daylight = "Daylight (the daylight model): mean daylight factor %.1f %%; DF >= 2 %% reaches %.1f m in from the window%s." % (
            d["df"], d["lit_depth"], "" if d["in_range"] else " (outside the range the model was trained on: indicative)")
    else:
        daylight = "Daylight: this shop is not among the 1,650 real shops modelled."
''' .replace("import json, io", "import os, json, io")),
    ("8 3D preview", ["shop", "case", "floor_height"], ["rooms", "colours", "flats", "shell", "facade", "plan_image", "plan_material"], r'''
# the AFTER layout as coloured room blocks (red = fails a rule; light blue = new patio; grey = shared corridor)
import Rhino.Geometry as rg
import Rhino.Display as rd
import System.Drawing as sd
H = float(floor_height or 3.0) - 0.3
COL = {"living": sd.Color.FromArgb(239, 159, 39), "bed_main": sd.Color.FromArgb(127, 119, 221), "bed": sd.Color.FromArgb(175, 169, 236),
       "kitchen": sd.Color.FromArgb(250, 199, 117), "bath": sd.Color.FromArgb(133, 183, 235), "hall": sd.Color.FromArgb(200, 200, 200)}
RED, PATIO, CORR = sd.Color.FromArgb(226, 75, 74), sd.Color.FromArgb(160, 205, 235), sd.Color.FromArgb(215, 215, 210)
def crv(pts, z=0.0):
    q = [rg.Point3d(x, y, z) for x, y in pts]
    if q[0].DistanceTo(q[-1]) > 1e-6:
        q.append(q[0])
    return rg.PolylineCurve(q)
def box(pts, h, z=0.0):
    s = rg.Surface.CreateExtrusion(crv(pts, z), rg.Vector3d(0, 0, h))
    return s.ToBrep().CapPlanarHoles(0.01) if s is not None else None
rooms, colours, flats = [], [], []
plan = case["after"]["plan"] if case else {"units": []}
for u in plan["units"]:
    if len(u["outline"]) >= 3:
        flats.append(crv(u["outline"], 0.02))
    for r in u["rooms"]:
        if len(r["pts"]) >= 3:
            b = box(r["pts"], H if r["kind"] != "hall" else 0.05)
            if b is not None:
                rooms.append(b)
                colours.append(COL.get(r["kind"], COL["hall"]) if (r.get("ok", True) and u.get("ok", True)) else RED)
for key, col, h in (("patios", PATIO, 0.02), ("corridors", CORR, 0.04)):
    for q in plan.get(key, []):
        b = box(q["pts"], h)
        if b is not None:
            rooms.append(b); colours.append(col)
shell = crv(shop["outline"]) if shop else None
facade = [rg.LineCurve(rg.Point3d(a[0], a[1], 0.05), rg.Point3d(b[0], b[1], 0.05)) for a, b in (shop or {}).get("facade", [])]
plan_image, plan_material = None, None
if shop and shop.get("image"):
    im = shop["image"]
    plan_image = rg.Brep.CreateFromCornerPoints(rg.Point3d(0, 0, -0.02), rg.Point3d(im["w"], 0, -0.02), rg.Point3d(im["w"], im["h"], -0.02),
                                                 rg.Point3d(0, im["h"], -0.02), 0.001)
    plan_material = rd.DisplayMaterial()
    plan_material.SetBitmapTexture(im["path"], True)
'''),
    ("9 Make", ["shop", "mix", "programs", "case", "make_sheet", "make_demo"], ["report"], PRE + r'''
# sheets and demos into THIS Rhino file (layer "06 NOMAD experiments::<name>", kept until you delete them)
import time, Rhino
import nomad_sheet as sheet
import nomad_model as model
doc = Rhino.RhinoDoc.ActiveDoc
report = ""
if make_sheet and case:
    name = "%s_%s" % (shop["name"], time.strftime("%Y%m%d_%H%M%S"))
    png = sheet.capture(doc, sheet.draw(doc, case, name), os.path.join(core.SHEETS, name + ".png"))
    core.save_case(case, name)
    report += "Sheet added (layer 06 NOMAD experiments::%s): %s\n" % (name, png)
if make_demo and shop:
    name = "%s_demo_%s" % (shop["name"], time.strftime("%Y%m%d_%H%M%S"))
    story = core.run_story(shop, mix, programs=programs)
    brd = model.draw_demo(doc, story, name, core.SHEETS)
    core.save_case(story, name)
    report += "Demo added (layer 06 NOMAD experiments::%s): three layouts (%s homes), zoning + walls in 3D. Board: %s\n" % (
        name, " / ".join(str(it["homes"]) for it in story["iterations"]), brd)
'''),
    ("10 This file", ["run_inbox", "show_experiments"], ["report"], PRE + r'''
# the inbox (plans dropped in data/inbox) and every recorded experiment drawn into this file
import Rhino
import nomad_sheet as sheet
import nomad_model as model
doc = Rhino.RhinoDoc.ActiveDoc
report = ""
if run_inbox:
    done = []
    for job in core.inbox_jobs():
        c = job["cfg"]
        jm = {"studio": int(c["n_studio"]), "1bed": int(c["n_1bed"]), "2bed": int(c["n_2bed"]), "3bed": int(c["n_3bed"])}
        js = core.shop_from_plan(job["path"], c["known_facade_m"], c["height"])
        if not js.get("ok"):
            done.append("%s: not read (%s)" % (job["name"], js.get("reason"))); continue
        core.add_zoning(js, c.get("address", ""))
        jc = core.run(js, jm, "compact" if c.get("compact") else "typical")
        sheet.capture(doc, sheet.draw(doc, jc, job["name"]), os.path.join(core.SHEETS, job["name"] + ".png"))
        core.save_case(jc, job["name"])
        done.append("%s: %s -> %s" % (job["name"], jc["before"]["res"]["verdict"], jc["after"]["res"]["verdict"]))
    report += "Inbox %s: %s\n" % (core.INBOX, "; ".join(done) or "nothing new")
if show_experiments:
    have, added = set(sheet.drawn_names(doc)), []
    for name, rec in core.recipes():
        if name in have:
            continue
        rc = rec.get("case") or core.run(rec["shop"], rec["mix"], rec.get("size", "typical"))
        if rc.get("story"):
            model.draw_demo(doc, rc, name, core.SHEETS, capture_pngs=False)
        else:
            sheet.draw(doc, rc, name)
        added.append(name)
    if added:
        report += "Experiments added to this file: %s (save NOMAD.3dm to keep them)\n" % ", ".join(added)
'''),
]
# where each component's inputs come from: a user control (name) or an earlier component's output ("node.out")
WIRES = {
    "1 Read plan": {"plan_file": "plan_file", "read_plan_on": "read_plan_on", "known_facade_m": "known_facade_m", "floor_height": "floor_height"},
    "2 Shop": {"plan_shop": "1 Read plan.plan_shop", "shop_outline": "shop_outline", "street_facade": "street_facade",
               "shop_index": "shop_index", "floor_height": "floor_height"},
    "3 Zoning": {"shop": "2 Shop.shop", "address": "address"},
    "4 Flats asked": {"n_studio": "n_studio", "n_1bed": "n_1bed", "n_2bed": "n_2bed", "n_3bed": "n_3bed"},
    "5 Flat sizes": {"m2_studio": "m2_studio", "m2_1bed": "m2_1bed", "m2_2bed": "m2_2bed", "m2_3bed": "m2_3bed", "compact": "compact"},
    "6 Check + layouts": {"shop": "3 Zoning.shop_z", "mix": "4 Flats asked.mix", "programs": "5 Flat sizes.programs", "size": "5 Flat sizes.size"},
    "7 Daylight": {"shop": "3 Zoning.shop_z"},
    "8 3D preview": {"shop": "3 Zoning.shop_z", "case": "6 Check + layouts.case", "floor_height": "floor_height"},
    "9 Make": {"shop": "3 Zoning.shop_z", "mix": "4 Flats asked.mix", "programs": "5 Flat sizes.programs", "case": "6 Check + layouts.case",
               "make_sheet": "make_sheet", "make_demo": "make_demo"},
    "10 This file": {"run_inbox": "run_inbox", "show_experiments": "show_experiments"},
}
COL_X = {"1 Read plan": 420, "2 Shop": 640, "3 Zoning": 860, "4 Flats asked": 420, "5 Flat sizes": 420, "6 Check + layouts": 1080,
         "7 Daylight": 1080, "8 3D preview": 1300, "9 Make": 1300, "10 This file": 420}
COL_Y = {"1 Read plan": 40, "2 Shop": 120, "3 Zoning": 200, "4 Flats asked": 360, "5 Flat sizes": 520, "6 Check + layouts": 300,
         "7 Daylight": 160, "8 3D preview": 300, "9 Make": 600, "10 This file": 700}
SLIDERS = [("known_facade_m", 0, 60, 0, 1, 80), ("shop_index", 0, 187, 0, 0, 200), ("n_studio", 0, 12, 0, 0, 340), ("n_1bed", 0, 12, 2, 0, 370),
           ("n_2bed", 0, 12, 1, 0, 400), ("n_3bed", 0, 12, 0, 0, 430), ("floor_height", 2.6, 5.0, 3.0, 2, 120),
           ("m2_studio", 0, 60, 0, 0, 500), ("m2_1bed", 0, 80, 0, 0, 530), ("m2_2bed", 0, 110, 0, 0, 560), ("m2_3bed", 0, 140, 0, 0, 590)]
TOGGLES = [("read_plan_on", "read plan", False, 40), ("compact", "compact rooms", False, 620), ("make_sheet", "make sheet", False, 680),
           ("make_demo", "make demo (stages 5-7)", False, 710), ("run_inbox", "run inbox", False, 760), ("show_experiments", "experiments in this file", True, 790)]


UNWRAP = {'2 Shop': ['plan_shop'], '3 Zoning': ['shop'], '6 Check + layouts': ['shop', 'mix', 'programs'], '7 Daylight': ['shop'], '8 3D preview': ['shop', 'case'], '9 Make': ['shop', 'mix', 'programs', 'case']}
WRAPOUT = {'1 Read plan': ['plan_shop'], '2 Shop': ['shop'], '3 Zoning': ['shop_z'], '4 Flats asked': ['mix'], '5 Flat sizes': ['programs'], '6 Check + layouts': ['case']}
NODES = [(n, i, o, WRAPPER + "".join("%s = U(%s)\n" % (v, v) for v in UNWRAP.get(n, [])) + c + "".join("%s = W(%s)\n" % (v, v) for v in WRAPOUT.get(n, [])))
         for n, i, o, c in NODES]


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def build():
    open(LOG, "w").close()
    for name, ins, outs, code in NODES:
        compile(code, name, "exec")                          # never save a file whose scripts do not compile
    if os.path.exists(OUT):
        arch = os.path.join(ROOT, "old", "grasshopper_archive", "NOMAD_one_component_%s.gh" % time.strftime("%Y%m%d_%H%M"))
        shutil.copy2(OUT, arch)
        log("old file kept: " + arch)
    Rhino.RhinoApp.GetPlugInObject("Grasshopper").LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParameterSide
    from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel, GH_BooleanToggle, GH_Group
    from Grasshopper.Kernel.Parameters import Param_Curve, Param_FilePath
    PointF = System.Drawing.PointF
    doc = GH_Document()
    src = {}

    def add(o, x, y):
        o.CreateAttributes(); o.Attributes.Pivot = PointF(x, y); doc.AddObject(o, False); return o
    fp = add(Param_FilePath(), 0, 0); fp.NickName = "Plan file (right-click > Set one file path)"; src["plan_file"] = fp
    for nick, label, on, y in TOGGLES:
        t = GH_BooleanToggle(); t.CreateAttributes(); t.NickName, t.Value = label, on; t.Attributes.Pivot = PointF(0, y); doc.AddObject(t, False); src[nick] = t
    for j, (nick, label) in enumerate([("shop_outline", "Your shop outline (right-click > Set one curve)"), ("street_facade", "Street facade (optional)")]):
        c = add(Param_Curve(), 0, 150 + 30 * j); c.NickName = label; src[nick] = c
    for nick, lo, hi, val, dec, y in SLIDERS:
        s = GH_NumberSlider(); s.CreateAttributes(); s.NickName = nick; s.Slider.DecimalPlaces = dec
        s.Slider.Minimum, s.Slider.Maximum, s.Slider.Value = System.Decimal(lo), System.Decimal(hi), System.Decimal(val)
        s.Attributes.Pivot = PointF(0, y); doc.AddObject(s, False); src[nick] = s
    adr = GH_Panel(); adr.CreateAttributes(); adr.NickName = "address or cadastral ref (Barcelona, optional)"; adr.UserText = ""
    adr.Attributes.Pivot = PointF(0, 240); adr.Attributes.Bounds = System.Drawing.RectangleF(0, 240, 240, 40); doc.AddObject(adr, False); src["address"] = adr

    comp = {}
    for name, ins, outs, code in NODES:
        py = GH.Instances.ComponentServer.EmitObject(System.Guid(PY_GUID))
        py.CreateAttributes(); py.Attributes.Pivot = PointF(COL_X[name], COL_Y[name]); doc.AddObject(py, False)
        for p in list(py.Params.Input):
            py.Params.UnregisterInputParameter(p)
        for p in list(py.Params.Output):
            if p.NickName != "out":
                py.Params.UnregisterOutputParameter(p)
        for i, nick in enumerate(ins):
            p = py.CreateParameter(GH_ParameterSide.Input, i); p.NickName = p.Name = nick; p.Optional = True; py.Params.RegisterInputParam(p, i)
        base = py.Params.Output.Count
        for j, nick in enumerate(outs):
            q = py.CreateParameter(GH_ParameterSide.Output, base + j); q.NickName = q.Name = nick; py.Params.RegisterOutputParam(q, base + j)
        py.Params.OnParametersChanged(); py.VariableParameterMaintenance()
        py.Code = code
        py.NickName = name
        comp[name] = py

    def output(ref):
        node, nick = ref.split(".")
        for q in comp[node].Params.Output:
            if q.NickName == nick:
                return q
    for name, ins, outs, code in NODES:
        for i, nick in enumerate(ins):
            s = WIRES[name][nick]
            comp[name].Params.Input[i].AddSource(output(s) if "." in s else src[s])

    pvs = []
    for k, (geo, mat) in enumerate([("rooms", "colours"), ("plan_image", "plan_material")]):
        pv = GH.Instances.ComponentServer.EmitObject(System.Guid(PREVIEW_GUID))
        pv.CreateAttributes(); pv.Attributes.Pivot = PointF(1560, 280 + 110 * k); doc.AddObject(pv, False)
        pv.Params.Input[0].AddSource(output("8 3D preview." + geo)); pv.Params.Input[1].AddSource(output("8 3D preview." + mat)); pvs.append(pv)
    panel = GH_Panel(); panel.CreateAttributes(); panel.Attributes.Pivot = PointF(1560, 520)
    panel.Attributes.Bounds = System.Drawing.RectangleF(1560, 520, 700, 520); doc.AddObject(panel, False)
    for ref in ("2 Shop.note", "1 Read plan.note", "3 Zoning.note", "7 Daylight.daylight", "6 Check + layouts.report", "9 Make.report", "10 This file.report"):
        panel.AddSource(output(ref))
    groups = [(u"1 · THE SHOP", (233, 238, 245), [src[k] for k in ("plan_file", "read_plan_on", "known_facade_m", "shop_outline", "street_facade",
                                                                   "shop_index", "address", "floor_height")] + [comp["1 Read plan"], comp["2 Shop"], comp["3 Zoning"]]),
              (u"2 · FLATS ASKED FOR", (245, 238, 228), [src[k] for k in ("n_studio", "n_1bed", "n_2bed", "n_3bed", "m2_studio", "m2_1bed",
                                                                         "m2_2bed", "m2_3bed", "compact")] + [comp["4 Flats asked"], comp["5 Flat sizes"]]),
              (u"3 · CHECK, DAYLIGHT, LAYOUTS", (243, 221, 210), [comp["6 Check + layouts"], comp["7 Daylight"]]),
              (u"4 · 3D AND MAKE", (236, 242, 232), [comp["8 3D preview"], comp["9 Make"], src["make_sheet"], src["make_demo"]] + pvs),
              (u"5 · THIS FILE", (240, 240, 240), [comp["10 This file"], src["run_inbox"], src["show_experiments"]]),
              (u"REPORT", (250, 250, 250), [panel])]
    for name, col, objs in groups:
        g = GH_Group(); g.CreateAttributes(); g.NickName = name; g.Colour = System.Drawing.Color.FromArgb(170, col[0], col[1], col[2])
        for o in objs:
            g.AddObject(o.InstanceGuid)
        doc.AddObject(g, False)
    ok = GH_DocumentIO(doc).SaveQuiet(OUT)
    log("saved %s: %s (%d components)" % (OUT, ok, len(NODES)))


try:
    build()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
Rhino.RhinoApp.Exit()
