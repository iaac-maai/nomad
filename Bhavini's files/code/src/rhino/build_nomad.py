# -*- coding: utf-8 -*-
"""Build THE master NOMAD files (runs INSIDE Rhino 7, IronPython 2.7, then closes Rhino):
  grasshopper/NOMAD.gh  - one Grasshopper file: read a plan -> shop outline -> flats -> rule checks -> 3D
  rhino/NOMAD.3dm       - one Rhino file with layers for the plan image and traced curves (made once, never overwritten)
Open both with OPEN_NOMAD.cmd. Rebuild:  Rhino.exe /nosplash /runscript="_-RunPythonScript <this file>"

Where the shop comes from (first one that is set wins):
  1. Plan file (PNG/JPG/PDF) + "read plan" switched on: the plan reader finds the outline and façade.
     Give one known size: "known façade m" (longest street façade) or leave 0 to let it estimate (rough).
  2. "Your shop outline" curve set from Rhino (traced or imported DWG/DXF), optional "Street facade" curve.
  3. shop_index: one of the 180 cleaned shops from Swiss Dwellings.
"""
import os, traceback
import Rhino, System, clr

ROOT = r"C:\Bhavini\AI\ADs\nomad"
OUT = os.path.join(ROOT, "grasshopper", "NOMAD.gh")
DOC3DM = os.path.join(ROOT, "rhino", "NOMAD.3dm")
LOG = os.path.join(ROOT, "logs", "rhino", "build_nomad_log.txt")
PY_GUID = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
PREVIEW_GUID = "537b0419-bbc2-4ff4-bf08-afe526367b2c"

SLIDERS = [("known_facade_m", 0, 60, 0, 1), ("shop_index", 0, 187, 0, 0), ("n_studio", 0, 12, 0, 0),
           ("n_1bed", 0, 12, 2, 0), ("n_2bed", 0, 12, 1, 0), ("n_3bed", 0, 12, 0, 0), ("floor_height", 2.6, 5.0, 3.0, 2),
           # the user's flat sizes, m² useful (0 = the sizes learned from 13,444 real flats): layout.with_targets
           ("m2_studio", 0, 60, 0, 0), ("m2_1bed", 0, 80, 0, 0), ("m2_2bed", 0, 110, 0, 0), ("m2_3bed", 0, 140, 0, 0)]
OUTPUTS = ["rooms", "colours", "flats", "shell", "facade", "plan_image", "plan_material", "report", "works", "verdict"]

CODE = r'''# NOMAD: plan -> shop outline -> before / after (Stage 6) -> rule check (Stage 5) -> 3D   (see grasshopper/README.md)
# The logic lives in src/rhino/nomad_core.py, src/generate/better.py + layout.py, src/check/flags.py, src/rhino/nomad_sheet.py
import sys, os, time
P = r"C:\Bhavini\AI\ADs\nomad\src\rhino"
if P not in sys.path:
    sys.path.append(P)
import nomad_core as core
import nomad_sheet as sheet
import nomad_model as model
reload(core)
core.reload_all()
reload(sheet)
reload(model)
import flags
import layout
import Rhino
import Rhino.Geometry as rg
import Rhino.Display as rd
import rhinoscriptsyntax as rs
import System.Drawing as sd

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
    pts = [(q.X, q.Y) for q in pl]
    if pts and (abs(pts[0][0] - pts[-1][0]) > 1e-6 or abs(pts[0][1] - pts[-1][1]) > 1e-6):
        pts.append(pts[0])
    return pts

H_CLEAR = float(floor_height or 3.0) - 0.3
mix = {"studio": int(n_studio or 0), "1bed": int(n_1bed or 0), "2bed": int(n_2bed or 0), "3bed": int(n_3bed or 0)}
sizes = dict((k, float(v)) for k, v in (("studio", m2_studio), ("1bed", m2_1bed), ("2bed", m2_2bed), ("3bed", m2_3bed)) if v and float(v) > 0)
progs = layout.with_targets(core.data()["programs"], sizes) if sizes else None     # None = learned sizes
size = "compact" if compact else "typical"

# 1. the shop: plan file > your curve > dataset
shop, note = None, ""
plan_path = str(plan_file).strip('"') if plan_file else ""
if plan_path and read_plan_on and os.path.exists(plan_path):
    shop = core.shop_from_plan(plan_path, float(known_facade_m or 0), H_CLEAR)
    if not shop.get("ok"):
        note = "Plan reader could not read the file: %s\n" % shop.get("reason")
        shop = None
    else:
        note = "Plan read: %s shows what the reader found.\n" % shop["read_preview"]
crv, fcrv = as_curve(shop_outline), as_curve(street_facade)
if shop is None and crv is not None and crv.IsClosed:
    near = None
    if fcrv is not None:
        def near(q):
            ok, t = fcrv.ClosestPoint(rg.Point3d(q[0], q[1], 0))
            return ok and fcrv.PointAt(t).DistanceTo(rg.Point3d(q[0], q[1], 0)) < 0.5
    shop = core.shop_from_curve(polyline_pts(crv), near, H_CLEAR)
if shop is None:
    shop = core.shop_from_dataset(shop_index)
note += core.add_zoning(shop, str(address).strip() if address else "")   # step 3: zoning of a Barcelona address

# 2. Stage 6 before / after + Stage 5 rule check
case = core.run(shop, mix, size, programs=progs)
B, A = case["before"], case["after"]
plan = A["plan"]
report = "Shop: %s\n%sBEFORE (as it is): %s, %d of %d flats pass\nAFTER: %s, %d of %d flats pass  -  %s\n%s\n\n%s" % (
    shop["source"], note, B["res"]["verdict"], B["res"]["flats_passing"], B["res"]["flats_asked"],
    A["res"]["verdict"], A["res"]["flats_passing"], A["res"]["flats_asked"], case["changed"],
    "\n".join(plan.get("interventions", [])), flags.summary_text(A["res"]))
works = plan["proposal_ok"]
verdict = "%s -> %s" % (B["res"]["verdict"], A["res"]["verdict"])

# 3. sheets in NOMAD.3dm (layer "06 NOMAD experiments", one sub-layer per experiment, kept until you delete them)
doc = Rhino.RhinoDoc.ActiveDoc
if make_sheet:
    name = "%s_%s" % (shop["name"], time.strftime("%Y%m%d_%H%M%S"))
    box = sheet.draw(doc, case, name)
    png = sheet.capture(doc, box, os.path.join(core.SHEETS, name + ".png"))
    core.save_case(case, name)
    report = "Sheet added to this file (layer 06 NOMAD experiments::%s) and saved: %s\n%s" % (name, png, report)
if make_demo:
    name = "%s_demo_%s" % (shop["name"], time.strftime("%Y%m%d_%H%M%S"))
    story = core.run_story(shop, mix, programs=progs)
    brd = model.draw_demo(doc, story, name, core.SHEETS)
    core.save_case(story, name)
    report = "Demo added to this file (layer 06 NOMAD experiments::%s): Stage 5 flags, Stage 6 three iterations (%s homes), Stage 7 3D. Board: %s" % (
        name, " / ".join(str(it["homes"]) for it in story["iterations"]), brd) + chr(10) + report
if run_inbox:
    done = []
    for job in core.inbox_jobs():
        c = job["cfg"]
        jm = {"studio": int(c["n_studio"]), "1bed": int(c["n_1bed"]), "2bed": int(c["n_2bed"]), "3bed": int(c["n_3bed"])}
        js = core.shop_from_plan(job["path"], c["known_facade_m"], c["height"])
        if not js.get("ok"):
            done.append("%s: not read (%s)" % (job["name"], js.get("reason")))
            continue
        core.add_zoning(js, c.get("address", ""))
        jc = core.run(js, jm, "compact" if c.get("compact") else "typical")
        b = sheet.draw(doc, jc, job["name"])
        sheet.capture(doc, b, os.path.join(core.SHEETS, job["name"] + ".png"))
        core.save_case(jc, job["name"])
        done.append("%s: %s -> %s" % (job["name"], jc["before"]["res"]["verdict"], jc["after"]["res"]["verdict"]))
    report = "Inbox %s: %s\n%s" % (core.INBOX, "; ".join(done) or "nothing new", report)
if show_experiments:
    have = set(sheet.drawn_names(doc))
    added = []
    for name, rec in core.recipes():
        if name in have:
            continue
        rc = rec.get("case") or core.run(rec["shop"], rec["mix"], rec.get("size", "typical"))   # drawn as it was made
        if rc.get("story"):
            model.draw_demo(doc, rc, name, core.SHEETS, capture_pngs=False)
        else:
            sheet.draw(doc, rc, name)
        added.append(name)
    if added:
        report = "Experiments added to this file: %s (save NOMAD.3dm to keep them)\n%s" % (", ".join(added), report)

# 4. 3D preview of AFTER (red = fails a rule; light blue = new patio; grey = shared corridor)
COL = {"living": sd.Color.FromArgb(239, 159, 39), "bed_main": sd.Color.FromArgb(127, 119, 221),
       "bed": sd.Color.FromArgb(175, 169, 236), "kitchen": sd.Color.FromArgb(250, 199, 117),
       "bath": sd.Color.FromArgb(133, 183, 235), "hall": sd.Color.FromArgb(200, 200, 200)}
RED, PATIO, CORR = sd.Color.FromArgb(226, 75, 74), sd.Color.FromArgb(160, 205, 235), sd.Color.FromArgb(215, 215, 210)

def closed_crv(pts, z=0.0):
    q = [rg.Point3d(x, y, z) for x, y in pts]
    if q[0].DistanceTo(q[-1]) > 1e-6:
        q.append(q[0])
    return rg.PolylineCurve(q)

def box_of(pts, h, z=0.0):
    srf = rg.Surface.CreateExtrusion(closed_crv(pts, z), rg.Vector3d(0, 0, h))
    return srf.ToBrep().CapPlanarHoles(0.01) if srf is not None else None

rooms, colours, flats = [], [], []
for u in plan["units"]:
    if len(u["outline"]) >= 3:
        flats.append(closed_crv(u["outline"], 0.02))
    for r in u["rooms"]:
        if len(r["pts"]) < 3:
            continue
        b = box_of(r["pts"], H_CLEAR if r["kind"] != "hall" else 0.05)
        if b is None:
            continue
        rooms.append(b)
        colours.append(COL.get(r["kind"], COL["hall"]) if (r.get("ok", True) and u.get("ok", True)) else RED)
for q in plan.get("patios", []):
    b = box_of(q["pts"], 0.02)
    if b is not None:
        rooms.append(b)
        colours.append(PATIO)
for q in plan.get("corridors", []):
    b = box_of(q["pts"], 0.04)
    if b is not None:
        rooms.append(b)
        colours.append(CORR)
shell = closed_crv(shop["outline"])
facade = [rg.LineCurve(rg.Point3d(a[0], a[1], 0.05), rg.Point3d(b[0], b[1], 0.05)) for a, b in shop["facade"]]
plan_image, plan_material = None, None
if shop.get("image"):
    im = shop["image"]
    plan_image = rg.Brep.CreateFromCornerPoints(rg.Point3d(0, 0, -0.02), rg.Point3d(im["w"], 0, -0.02),
                                                 rg.Point3d(im["w"], im["h"], -0.02), rg.Point3d(0, im["h"], -0.02), 0.001)
    plan_material = rd.DisplayMaterial()
    plan_material.SetBitmapTexture(im["path"], True)
'''


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def make_3dm():
    """Create rhino/NOMAD.3dm once with named layers; never overwrite the user's file."""
    if os.path.exists(DOC3DM):
        log("NOMAD.3dm exists: kept as is")
        return
    if not os.path.isdir(os.path.dirname(DOC3DM)):
        os.makedirs(os.path.dirname(DOC3DM))
    f3 = Rhino.FileIO.File3dm()
    f3.Settings.ModelUnitSystem = Rhino.UnitSystem.Meters
    for name, col in [("01 Plan image", System.Drawing.Color.Gray), ("02 Shop outline (traced)", System.Drawing.Color.Red),
                      ("03 Street facade", System.Drawing.Color.Blue), ("04 Notes", System.Drawing.Color.Black)]:
        ly = Rhino.DocObjects.Layer()
        ly.Name, ly.Color = name, col
        f3.AllLayers.Add(ly)
    ok = f3.Write(DOC3DM, 7)
    log("NOMAD.3dm created: %s" % ok)


def build():
    open(LOG, "w").close()
    compile(CODE, "NOMAD component", "exec")          # never save a NOMAD.gh whose script has a syntax error
    make_3dm()
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParameterSide
    from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel, GH_BooleanToggle
    from Grasshopper.Kernel.Parameters import Param_Curve, Param_FilePath
    PointF = System.Drawing.PointF
    doc = GH_Document()
    src = {}

    fp = Param_FilePath()
    fp.CreateAttributes()
    fp.NickName = "Plan file (right-click > Set one file path)"
    fp.Attributes.Pivot = PointF(0, 0)
    doc.AddObject(fp, False)
    src["plan_file"] = fp
    for j, (nick, label, on, y) in enumerate([("read_plan_on", "read plan", False, 40), ("compact", "compact rooms", False, 300),
                                              ("make_sheet", "make sheet", False, 500), ("run_inbox", "run inbox", False, 540),
                                              ("show_experiments", "experiments in this file", True, 580),
                                              ("make_demo", "make demo (stages 5-7)", False, 620)]):
        t = GH_BooleanToggle()
        t.CreateAttributes()
        t.NickName, t.Value = label, on
        t.Attributes.Pivot = PointF(0, y)
        doc.AddObject(t, False)
        src[nick] = t
    for j, (nick, label) in enumerate([("shop_outline", "Your shop outline (right-click > Set one curve)"),
                                        ("street_facade", "Street facade (optional)")]):
        c = Param_Curve()
        c.CreateAttributes()
        c.NickName = label
        c.Attributes.Pivot = PointF(0, 110 + 40 * j)
        doc.AddObject(c, False)
        src[nick] = c
    ys = {"known_facade_m": 75, "shop_index": 190, "n_studio": 330, "n_1bed": 360, "n_2bed": 390, "n_3bed": 420, "floor_height": 450,
          "m2_studio": 670, "m2_1bed": 700, "m2_2bed": 730, "m2_3bed": 760}
    for nick, lo, hi, val, dec in SLIDERS:
        s = GH_NumberSlider()
        s.CreateAttributes()
        s.NickName = nick
        s.Slider.DecimalPlaces = dec
        s.Slider.Minimum, s.Slider.Maximum, s.Slider.Value = System.Decimal(lo), System.Decimal(hi), System.Decimal(val)
        s.Attributes.Pivot = PointF(0, ys[nick])
        doc.AddObject(s, False)
        src[nick] = s

    adr = GH_Panel()                                      # step 3: a Barcelona address or cadastral reference (optional)
    adr.CreateAttributes()
    adr.NickName = "address or cadastral ref (Barcelona, optional)"
    adr.UserText = ""
    adr.Attributes.Pivot = PointF(0, 230)
    adr.Attributes.Bounds = System.Drawing.RectangleF(0, 230, 260, 40)
    doc.AddObject(adr, False)
    src["address"] = adr
    inputs = ["plan_file", "read_plan_on", "known_facade_m", "shop_outline", "street_facade", "shop_index", "address",
              "n_studio", "n_1bed", "n_2bed", "n_3bed", "compact", "floor_height", "make_sheet", "run_inbox", "show_experiments", "make_demo",
              "m2_studio", "m2_1bed", "m2_2bed", "m2_3bed"]
    py = GH.Instances.ComponentServer.EmitObject(System.Guid(PY_GUID))
    py.CreateAttributes()
    py.Attributes.Pivot = PointF(500, 200)
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
    py.NickName = "NOMAD"
    for i, nick in enumerate(inputs):
        py.Params.Input[i].AddSource(src[nick])

    def out(nick):
        for q in py.Params.Output:
            if q.NickName == nick:
                return q

    for k, (geo, mat) in enumerate([("rooms", "colours"), ("plan_image", "plan_material")]):
        pv = GH.Instances.ComponentServer.EmitObject(System.Guid(PREVIEW_GUID))
        pv.CreateAttributes()
        pv.Attributes.Pivot = PointF(880, 100 + 110 * k)
        doc.AddObject(pv, False)
        pv.Params.Input[0].AddSource(out(geo))
        pv.Params.Input[1].AddSource(out(mat))
    panel = GH_Panel()
    panel.CreateAttributes()
    panel.Attributes.Pivot = PointF(880, 340)
    panel.Attributes.Bounds = System.Drawing.RectangleF(880, 340, 760, 560)
    doc.AddObject(panel, False)
    panel.AddSource(out("report"))
    pviews = [o for o in doc.Objects if o.ComponentGuid == System.Guid(PREVIEW_GUID)]
    # labelled groups, so the definition reads like the pipeline (and on the slides)
    from Grasshopper.Kernel.Special import GH_Group
    groups = [(u"1 · THE SHOP: plan file, your outline or a dataset shop (+ address: zoning)", (233, 238, 245),
               [src[k] for k in ("plan_file", "read_plan_on", "known_facade_m", "shop_outline", "street_facade", "shop_index", "address")]),
              (u"2 · FLATS ASKED FOR: how many, and how big (m², 0 = learned)", (245, 238, 228),
               [src[k] for k in ("n_studio", "n_1bed", "n_2bed", "n_3bed", "compact", "floor_height", "m2_studio", "m2_1bed", "m2_2bed", "m2_3bed")]),
              (u"3 · NOMAD: zoning (step 3) + check (step 6) → layouts + 3D (step 7)", (243, 221, 210), [py]),
              (u"4 · MAKE: sheet, inbox, experiments in the file, demo", (236, 242, 232),
               [src[k] for k in ("make_sheet", "run_inbox", "show_experiments", "make_demo")]),
              (u"5 · PREVIEW IN RHINO + REPORT", (240, 240, 240), pviews + [panel])]
    for name, col, objs in groups:
        g = GH_Group()
        g.CreateAttributes()
        g.NickName = name
        g.Colour = System.Drawing.Color.FromArgb(170, col[0], col[1], col[2])
        for o in objs:
            g.AddObject(o.InstanceGuid)
        doc.AddObject(g, False)
    ok = GH_DocumentIO(doc).SaveQuiet(OUT)
    log("saved %s: %s" % (OUT, ok))


try:
    build()
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
Rhino.RhinoApp.Exit()
