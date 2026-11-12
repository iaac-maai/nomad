# -*- coding: utf-8 -*-
"""Record every NOMAD experiment (lab book E01-E10) in THE Rhino file, rhino/NOMAD.3dm, so nothing has to be redone.

Runs in a separate Rhino (never while the user has NOMAD.3dm open), makes a backup first
(rhino/backups/NOMAD_<date time>.3dm), then lays out one row per experiment, newest at the bottom:
  layer "07 NOMAD lab book::E0x <title>"   the experiment's text (asked / did / result / learned / decision)
                                            and its figures, embedded as pictures
  layer "06 NOMAD experiments::<case>"     real geometry: E05 generated plans as 3D blocks, E09 before / after
                                            sheets, E10 demo sheets with the 3D model of each layout under its plan
Drawn from saved results only (book/experiments.json, book/figures, results/sheets/recipes): nothing recomputed.
Re-running replaces the rows (the user's own layers are never touched).
Run: powershell -File src\\rhino\\run_in_rhino.ps1 -Script C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\record_experiments.py -Done C:\\Bhavini\\AI\\ADs\\nomad\\logs\\rhino\\record_log.txt
"""
import os, io, json, re, sys, shutil, time, traceback
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import System

ROOT = r"C:\Bhavini\AI\ADs\nomad"
for sub in ("rhino", "check", "generate"):
    d = os.path.join(ROOT, "src", sub)
    if d not in sys.path:
        sys.path.append(d)
FILE = os.path.join(ROOT, "rhino", "NOMAD.3dm")
LOG = os.path.join(ROOT, "logs", "rhino", "record_log.txt")
BOOK = os.path.join(ROOT, "book")
REC = os.path.join(ROOT, "results", "sheets", "recipes")
LAB = "07 NOMAD lab book"
FIG_H, GAP, TEXT_W, ROW_GAP = 30.0, 6.0, 46.0, 22.0
CASES = {"E09": ["E09_shop_79_patio_2x1bed_1x2bed", "E09_shop_154608_deep_2x1bed", "E09_test_plan_145057", "E09_shop_146519_2x1bed_1x2bed"],
         "E10": ["D0_plan_drawing_145057", "D1_shop_146519_YES", "D2_warehouse_154822_patio", "D3_large_shop_152418", "D4_warehouse_154608_NO"]}


def log(msg):
    with open(LOG, "a") as f:
        f.write((msg if isinstance(msg, str) else msg.encode("utf-8")) + "\n")


def metrics():
    """The same numbers the lab book fills in (src/book/build_book.py), read from the result files."""
    import csv
    m = {}
    with io.open(os.path.join(ROOT, "results", "dashboard", "dashboard_data", "headline.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = float(r["value"])
            m[r["metric"]] = ("%d%%" % round(100 * v)) if v < 1 else "{:,}".format(int(round(v)))
    ev = json.load(io.open(os.path.join(ROOT, "results", "plan_reading", "eval_summary.json"), encoding="utf-8"))
    m["reader_iou_given"] = "%.2f" % ev["scale given"]["median_iou"]
    m["reader_area10_given"] = "%d%%" % round(100 * ev["scale given"]["area_within_10pct"])
    m["reader_scale_err"] = "%d%%" % round(100 * ev["scale estimated"]["median_scale_error"])
    cmp_dir = os.path.join(ROOT, "results", "plan_reading", "compare")
    for fn in os.listdir(cmp_dir):
        if fn.endswith(".json"):
            plans, walls = fn[:-5].split("__")
            d = json.load(io.open(os.path.join(cmp_dir, fn), encoding="utf-8"))["scale given"]
            m["race_%s_%s" % (walls, "messy" if "messy" in plans else "clean")] = "%d%%" % round(100 * d["area_within_10pct"])
    s5 = json.load(io.open(os.path.join(ROOT, "results", "flags", "summary.json"), encoding="utf-8"))
    v = s5["2 x 1-bed + 1 x 2-bed"]
    m.update(s5_yes=str(v["verdicts"].get("YES", 0)), s5_partly=str(v["verdicts"].get("PARTLY", 0)), s5_no=str(v["verdicts"].get("NO", 0)),
             s5_fit_fail=str(v["cards_failed"].get("Flats that fit", 0)), s5_dark20=str(s5["daylight"]["shops_with_over_20pct_dark"]))
    s6 = json.load(io.open(os.path.join(ROOT, "results", "generation", "stage6_summary.json"), encoding="utf-8"))
    a, b = s6["2 x 1-bed + 1 x 2-bed"], s6["5 x 1-bed + 2 x 2-bed"]
    m.update(s6_works_v1=str(a["works_v1"]), s6_works_after=str(a["works_after"]), s6_flats_v1=str(a["passing_flats_v1"]),
             s6_flats_after=str(a["passing_flats_after"]), s6_flats_v1_big=str(b["passing_flats_v1"]), s6_flats_after_big=str(b["passing_flats_after"]))
    si = json.load(io.open(os.path.join(ROOT, "results", "generation", "iterations_summary.json"), encoding="utf-8"))
    f5, it = si["stage5_flags_as_it_is"], si["iterations"]
    m.update(it_flag_yes=str(f5.get("YES", 0)), it_flag_partly=str(f5.get("PARTLY", 0)), it_flag_no=str(f5.get("NO", 0)),
             it1_homes=str(it["1 as asked"]["homes"]), it2_homes=str(it["2 as asked, compact rooms"]["homes"]),
             it3_homes=str(it["3 most homes"]["homes"]), it3_yes=str(it["3 most homes"]["verdicts"].get("YES", 0)),
             it3_any=str(it["3 most homes"]["shops_with_at_least_one_home"]))
    m["repos_found"] = "31"
    return m


def fill(t, m):
    return re.sub(r"\{([a-z0-9_]+)\}", lambda g: m.get(g.group(1), g.group(0)), t)


def clear_layer_tree(doc, path):
    i = doc.Layers.FindByFullPath(path, -1)
    if i < 0:
        return
    root = doc.Layers[i]
    todo = [root]
    while todo:
        ly = todo.pop()
        for o in doc.Objects.FindByLayer(ly) or []:
            doc.Objects.Delete(o, True)
        for ch in doc.Layers:
            if ch.ParentLayerId == ly.Id and not ch.IsDeleted:
                todo.append(ch)


def picture(doc, layer, path, x, y, h):
    """A figure as an embedded picture frame, h metres high, lower-left at (x, y). Returns its width."""
    bmp = System.Drawing.Bitmap(path)
    w = h * bmp.Width / float(bmp.Height)
    bmp.Dispose()
    gid = doc.Objects.AddPictureFrame(rg.Plane(rg.Point3d(x, y, 0), rg.Vector3d.ZAxis), path, False, w, h, True, True)
    o = doc.Objects.FindId(gid)
    if o is not None:
        o.Attributes.LayerIndex = layer
        o.CommitChanges()
    return w


def text_block(pen, e, m, x, ytop):
    """The lab-book entry as text: title, question, and the four parts, left of the figures."""
    h = 0.9
    pen.text(u"%s  ·  %s" % (e["id"], e["title"]), x, ytop, 1.8, bold=True, width=TEXT_W)
    pen.text(u"Stage %s  ·  %s" % (e["stage"], e["date"]), x, ytop - 4.6, h, rgb=(110, 116, 126), width=TEXT_W)
    y = ytop - 6.6
    for head, body in ((u"Question", fill(e["question"], m)), (u"What we did", u"\n".join(u"- " + fill(t, m) for t in e["did"])),
                       (u"Result", fill(e["result"], m)), (u"What we learned", u"\n".join(u"- " + fill(t, m) for t in e["learned"])),
                       (u"Decision", fill(e["decision"], m))):
        pen.text(head, x, y, h, bold=True, width=TEXT_W)
        lines = sum(1 + len(t) // 62 for t in body.split(u"\n"))
        pen.text(body, x, y - 1.4, 0.75, width=TEXT_W)
        y -= 1.4 + lines * 1.25 + 1.6
    return ytop - y


def main():
    open(LOG, "w").close()
    import nomad_core as core
    import nomad_sheet as sheet
    import nomad_model as model
    bdir = os.path.join(ROOT, "rhino", "backups")
    if not os.path.isdir(bdir):
        os.makedirs(bdir)
    backup = os.path.join(bdir, "NOMAD_%s.3dm" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(FILE, backup)
    log("backup: " + backup)
    Rhino.RhinoApp.RunScript('_-Open "%s" _Enter' % FILE, False)
    doc = Rhino.RhinoDoc.ActiveDoc
    log("opened %s: %d objects" % (doc.Path, doc.Objects.Count))
    clear_layer_tree(doc, LAB)
    for names in CASES.values():
        for n in names:
            sheet.clear(doc, n)
            for k in (1, 2, 3):
                for sub in ("3d iteration %d", "walls iteration %d"):
                    i = doc.Layers.FindByFullPath(sheet.PARENT + "::" + n + "::" + sub % k, -1)
                    if i >= 0:
                        for o in doc.Objects.FindByLayer(doc.Layers[i]) or []:
                            doc.Objects.Delete(o, True)
    ex = json.load(io.open(os.path.join(BOOK, "experiments.json"), encoding="utf-8"))["experiments"]
    m = metrics()
    ytop = 0.0
    for e in ex:
        lay = sheet._layer(doc, LAB + "::" + e["id"] + " " + e["title"][:48])
        L = dict((k, lay) for k in sheet.SUBLAYERS)
        pen = sheet.Pen(doc, L, 1.0)
        th = text_block(pen, e, m, 0.0, ytop)
        x, row_h = TEXT_W + GAP, max(th, FIG_H + 4.0)
        for fname, cap in e["figures"]:
            path = os.path.join(BOOK, "figures", fname)
            if not os.path.exists(path):
                continue
            w = picture(doc, lay, path, x, ytop - FIG_H, FIG_H)
            pen.text(cap, x, ytop - FIG_H - 1.2, 0.75, rgb=(110, 116, 126), width=max(w, 20.0))
            x += w + GAP
        # real geometry for the later experiments
        if e["id"] == "E05":
            data = json.load(io.open(os.path.join(ROOT, "results", "generation", "sample_plans.json"), encoding="utf-8"))["samples"]
            picks = [d for d in data if d["plan"].get("proposal_ok")][:6]
            lay3 = sheet._layer(doc, LAB + "::" + e["id"] + " " + e["title"][:48] + "::3d models")
            for smp in picks:
                s_ = smp["shell"]
                xs = [p[0] for p in s_["outline"]]
                ys = [p[1] for p in s_["outline"]]
                mv = (x - min(xs), ytop - FIG_H - min(ys))
                model.build(doc, {"outline": s_["outline"], "facade": s_["facade"]}, smp["plan"], mv, lay3)
                x += (max(xs) - min(xs)) + GAP
        if e["id"] in CASES:
            for n in CASES[e["id"]]:
                rp = os.path.join(REC, n + ".json")
                if not os.path.exists(rp):
                    log("missing recipe " + n)
                    continue
                case = json.load(io.open(rp, encoding="utf-8"))["case"]
                if case.get("story"):
                    bb = model.draw_demo(doc, case, n, core.SHEETS, capture_pngs=False, origin=(x, 0.0))
                else:
                    bb = sheet.draw(doc, case, n, origin=(x, 0.0))
                # move the sheet into this experiment's row (top aligned)
                xf = rg.Transform.Translation(0, ytop - bb.Max.Y, 0)
                for o in list(doc.Objects):
                    if o.Attributes.LayerIndex >= 0:
                        lp = doc.Layers[o.Attributes.LayerIndex].FullPath
                        if lp.startswith(sheet.PARENT + "::" + n + "::"):
                            doc.Objects.Transform(o, xf, True)
                row_h = max(row_h, bb.Max.Y - bb.Min.Y + 4.0)
                x += (bb.Max.X - bb.Min.X) + GAP
                log("  drew %s" % n)
        log("%s: row %.0f m high, %.0f m wide" % (e["id"], row_h, x))
        ytop -= row_h + ROW_GAP
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
