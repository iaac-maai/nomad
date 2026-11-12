# -*- coding: utf-8 -*-
"""NOMAD before / after sheet, drawn in Rhino (IronPython 2.7) and saved as a PNG.

Clean on purpose: white paper, no grid, no boxes. Two plans side by side - BEFORE (the shop as it is) and
AFTER (the smallest change, Stage 6) - each tinted by daylight from the façades (and new patios), with its
verdict YES / PARTLY / NO written large and translucent over it. Under the plans: the rules (after),
"How it was checked", "Result" and "What changed", as plain text.

Every sheet goes on its own layer "06 NOMAD experiments::<name>::..." and is placed beside the earlier ones,
so NOMAD.3dm keeps every experiment until you delete it.
   draw(doc, case, name) -> frame box      capture(doc, box, png)      next_origin(doc)
"""
import math, os, datetime
import Rhino
import Rhino.Geometry as rg
import System
import System.Drawing as sd
import flags

PARENT = "06 NOMAD experiments"
SUBLAYERS = ["paper", "daylight", "walls", "flats", "patios", "dims", "text"]
INK, MUTED, OKC, BADC, BLUE = (28, 32, 38), (110, 116, 126), (36, 128, 86), (196, 58, 48), (64, 110, 160)
VCOL = flags.VERDICT_RGB
PATIO_RGB, CORR_RGB = flags.PATIO_RGB, flags.CORRIDOR_RGB
FONT = "Arial"
HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "results", "sheets")


def C(rgb, a=255):
    return sd.Color.FromArgb(a, rgb[0], rgb[1], rgb[2])


# ---------- layers ----------
def _layer(doc, path, rgb=(0, 0, 0)):
    i = doc.Layers.FindByFullPath(path, -1)
    if i >= 0:
        return i
    parts = path.split("::")
    parent_id = System.Guid.Empty
    for k in range(len(parts)):
        sub = "::".join(parts[:k + 1])
        j = doc.Layers.FindByFullPath(sub, -1)
        if j < 0:
            ly = Rhino.DocObjects.Layer()
            ly.Name, ly.Color = parts[k], C(rgb)
            if parent_id != System.Guid.Empty:
                ly.ParentLayerId = parent_id
            j = doc.Layers.Add(ly)
        parent_id = doc.Layers[j].Id
    return doc.Layers.FindByFullPath(path, -1)


def layers_for(doc, name):
    base = PARENT + "::" + name
    return dict((s, _layer(doc, base + "::" + s)) for s in SUBLAYERS)


def clear(doc, name):
    """Remove an earlier drawing of the same experiment (same name) before redrawing it."""
    base = PARENT + "::" + name
    if doc.Layers.FindByFullPath(base, -1) < 0:
        return
    for s in SUBLAYERS:
        i = doc.Layers.FindByFullPath(base + "::" + s, -1)
        if i >= 0:
            for o in doc.Objects.FindByLayer(doc.Layers[i]) or []:
                doc.Objects.Delete(o, True)


def drawn_names(doc):
    """Experiments already drawn in this file (one sub-layer of "06 NOMAD experiments" each, with objects)."""
    i = doc.Layers.FindByFullPath(PARENT, -1)
    if i < 0:
        return []
    pid = doc.Layers[i].Id
    out = []
    for ly in doc.Layers:
        if ly.ParentLayerId == pid and not ly.IsDeleted:
            j = doc.Layers.FindByFullPath(PARENT + "::" + ly.Name + "::paper", -1)
            if j >= 0 and doc.Objects.FindByLayer(doc.Layers[j]):
                out.append(ly.Name)
    return out


def next_origin(doc, gap=12.0):
    """Lower-left corner for a new sheet: to the right of everything already in the file."""
    bb = rg.BoundingBox.Empty
    for o in doc.Objects:
        if o.IsDeleted:
            continue
        b = o.Geometry.GetBoundingBox(True)
        if b.IsValid:
            bb.Union(b)
    if not bb.IsValid:
        return (0.0, 0.0)
    return (bb.Max.X + gap, bb.Min.Y)


def _attr(layer, rgb=None, weight=None):
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = layer
    if rgb is not None:
        a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        a.ObjectColor = C(rgb)
    if weight is not None:
        a.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
        a.PlotWeight = weight
    return a


# ---------- pen ----------
class Pen(object):
    def __init__(self, doc, L, u):
        self.doc, self.L, self.u, self.ids = doc, L, u, []
        self.solid = doc.HatchPatterns.FindName("Solid")
        if self.solid is None:
            doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
            self.solid = doc.HatchPatterns.FindName("Solid")
        self.ds = self._dimstyle()

    def _dimstyle(self):
        name = "NOMAD clean"
        ds = self.doc.DimStyles.FindName(name)
        if ds is None:
            self.doc.DimStyles.Add(name)
            ds = self.doc.DimStyles.FindName(name)
        ds = ds.Duplicate()
        u = self.u
        ds.TextHeight, ds.ArrowLength, ds.TextGap = 0.5 * u, 0.35 * u, 0.2 * u
        ds.ExtensionLineExtension, ds.ExtensionLineOffset = 0.25 * u, 0.25 * u
        ds.LengthFactor, ds.LengthResolution = 100.0, 0          # metres drawn, centimetres written
        try:
            ds.Font = Rhino.DocObjects.Font(FONT)
            ds.ArrowType1 = ds.ArrowType2 = Rhino.DocObjects.DimensionStyle.ArrowType.Tick
        except Exception:
            pass
        self.doc.DimStyles.Modify(ds, ds.Id, True)
        return self.doc.DimStyles.FindName(name)

    def _keep(self, gid):
        if gid != System.Guid.Empty:
            self.ids.append(gid)
        return gid

    def line(self, pts, layer, rgb, w=0.25, z=0.0, closed=False):
        p = [rg.Point3d(x, y, z) for x, y in pts]
        if closed and p[0].DistanceTo(p[-1]) > 1e-9:
            p.append(p[0])
        return self._keep(self.doc.Objects.AddPolyline(p, _attr(self.L[layer], rgb, w)))

    def fill(self, loops, layer, rgb, z=0.0):
        crvs = []
        for pts in loops:
            p = [rg.Point3d(x, y, z) for x, y in pts]
            if p[0].DistanceTo(p[-1]) > 1e-9:
                p.append(p[0])
            crvs.append(rg.PolylineCurve(p))
        for h in rg.Hatch.Create(crvs, self.solid.Index, 0.0, 1.0, 0.001) or []:
            self._keep(self.doc.Objects.AddHatch(h, _attr(self.L[layer], rgb)))

    def text(self, s, x, y, h, rgb=INK, width=None, bold=False, z=0.02, centre=False):
        pl = rg.Plane(rg.Point3d(x, y, z), rg.Vector3d.ZAxis)
        te = rg.TextEntity.Create(s, pl, self.ds, width is not None, width or 0.0, 0.0)
        if te is None:
            return None
        try:
            te.TextHeight = h
            te.Font = Rhino.DocObjects.Font(FONT, Rhino.DocObjects.Font.FontWeight.Bold if bold else Rhino.DocObjects.Font.FontWeight.Normal,
                                            Rhino.DocObjects.Font.FontStyle.Upright, False, False)
            te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Top
            te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center if centre else Rhino.DocObjects.TextHorizontalAlignment.Left
            if width is not None:
                te.FormatWidth = width
                te.TextIsWrapped = True
        except Exception:
            pass
        return self._keep(self.doc.Objects.AddText(te, _attr(self.L["text"], rgb)))

    def dim(self, a, b, off):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-6:
            return
        nx, ny = -dy / L, dx / L
        mid = rg.Point3d((a[0] + b[0]) / 2 + nx * off, (a[1] + b[1]) / 2 + ny * off, 0.01)
        plane = rg.Plane(rg.Point3d(0, 0, 0.01), rg.Vector3d(dx / L, dy / L, 0), rg.Vector3d(nx, ny, 0))
        try:
            d = rg.LinearDimension.Create(Rhino.Geometry.AnnotationType.Aligned, self.ds, plane, rg.Vector3d(dx / L, dy / L, 0),
                                          rg.Point3d(a[0], a[1], 0.01), rg.Point3d(b[0], b[1], 0.01), mid, 0.0)
            if d is not None:
                self._keep(self.doc.Objects.AddLinearDimension(d, _attr(self.L["dims"], MUTED)))
        except Exception:
            pass

    def mark(self, x, y, s, ok):
        if ok:
            self.line([(x, y + 0.5 * s), (x + 0.35 * s, y + 0.15 * s), (x + s, y + 0.9 * s)], "text", OKC, 0.6, 0.03)
        else:
            self.line([(x, y), (x + s, y + s)], "text", BADC, 0.6, 0.03)
            self.line([(x, y + s), (x + s, y)], "text", BADC, 0.6, 0.03)


# ---------- plan pieces ----------
def _outward(poly, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if flags._inside(mx + nx * 0.05, my + ny * 0.05, poly):
        nx, ny = -nx, -ny
    return nx, ny


def _walls(pen, pts, wt=0.30):
    crv = rg.PolylineCurve([rg.Point3d(x, y, 0) for x, y in pts] + [rg.Point3d(pts[0][0], pts[0][1], 0)])
    best = None
    for d in (wt, -wt):
        try:
            offs = crv.Offset(rg.Plane.WorldXY, d, 0.001, rg.CurveOffsetCornerStyle.Sharp)
        except Exception:
            offs = None
        if offs and len(offs) == 1 and offs[0].IsClosed:
            a = rg.AreaMassProperties.Compute(offs[0])
            if a and (best is None or a.Area > best[0]):
                best = (a.Area, offs[0])
    ring = None
    if best is not None:
        breps = rg.Brep.CreatePlanarBreps([best[1], crv], 0.001)    # outer + inner loop -> a ring (inside stays open)
        if breps and len(breps) == 1 and breps[0].Faces.Count == 1 and breps[0].Faces[0].Loops.Count == 2:
            ring = breps[0]
    if ring is None:                                            # could not make a clean ring: draw the outline only
        pen.line(pts, "walls", (44, 50, 58), 0.7, 0.004, closed=True)
        return
    pen._keep(pen.doc.Objects.AddBrep(ring, _attr(pen.L["walls"], (44, 50, 58))))


def _picture(pen, shop, res, plan, verdict, name, dx):
    """Daylight gradient (one pixel per cell, smoothed, clipped to the outline), the plan drawing on top when there
    is one, patios in light blue, and the verdict written large and translucent. Added as a picture frame."""
    day = res["daylight"]
    cell = day["cell"]
    outline = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    light = list(shop["facade"])
    for pt in plan.get("patios", []):
        q = pt["pts"]
        light += [[q[i], q[(i + 1) % len(q)]] for i in range(len(q))]
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    gx0, gy0 = min(xs) - cell, min(ys) - cell
    nx, ny = int((max(xs) - gx0) / cell) + 2, int((max(ys) - gy0) / cell) + 2
    small = sd.Bitmap(nx, ny)
    for i in range(nx):
        for j in range(ny):
            x, y = gx0 + (i + 0.5) * cell, gy0 + (j + 0.5) * cell
            d = min(flags._seg_dist(x, y, a, b) for a, b in light) if light else 99.0
            small.SetPixel(i, ny - 1 - j, C(flags.band_colour(d, day["lit_depth"], day["service_depth"])))
    img = shop.get("image")
    if img:
        src = sd.Bitmap(img["path"])
        Wp, Hp = src.Width, src.Height
        k = img["w"] / float(Wp)
        wx0, wy0, ww, wh = 0.0, 0.0, img["w"], img["h"]
    else:
        src, k = None, 1.0 / 40.0
        wx0, wy0 = min(xs) - 0.5, min(ys) - 0.5
        ww, wh = max(xs) + 0.5 - wx0, max(ys) + 0.5 - wy0
        Wp, Hp = int(ww / k), int(wh / k)
    px = lambda x, y: sd.PointF(float((x - wx0) / k), float((wy0 + wh - y) / k))
    big = sd.Bitmap(Wp, Hp)
    g = sd.Graphics.FromImage(big)
    g.Clear(sd.Color.White)
    path = sd.Drawing2D.GraphicsPath()
    path.AddPolygon(System.Array[sd.PointF]([px(p[0], p[1]) for p in outline]))
    g.SetClip(path)
    g.InterpolationMode = sd.Drawing2D.InterpolationMode.HighQualityBilinear
    g.PixelOffsetMode = sd.Drawing2D.PixelOffsetMode.Half
    tl = px(gx0, gy0 + ny * cell)
    g.DrawImage(small, sd.RectangleF(tl.X, tl.Y, float(nx * cell / k), float(ny * cell / k)))
    g.ResetClip()
    for un in plan.get("units", []):                           # rooms filled in the E05 colours, translucent
        for r in un["rooms"]:
            if len(r["pts"]) < 3:
                continue
            ok = r.get("ok", True) and un.get("ok", True)
            rb = sd.SolidBrush(C(flags.ROOM_RGB.get(r["kind"], flags.ROOM_RGB["hall"]) if ok else flags.FAIL_RGB, 158))
            g.FillPolygon(rb, System.Array[sd.PointF]([px(q[0], q[1]) for q in r["pts"]]))
            rb.Dispose()
    pb = sd.SolidBrush(C(PATIO_RGB))
    for pt in plan.get("patios", []):
        g.FillPolygon(pb, System.Array[sd.PointF]([px(q[0], q[1]) for q in pt["pts"]]))
    pb.Dispose()
    if src is not None:
        ia = sd.Imaging.ImageAttributes()
        ia.SetColorKey(sd.Color.FromArgb(175, 175, 175), sd.Color.FromArgb(255, 255, 255))
        g.DrawImage(src, sd.Rectangle(0, 0, Wp, Hp), 0, 0, Wp, Hp, sd.GraphicsUnit.Pixel, ia)
        src.Dispose()
    for obj in (path, g):                        # free the drawing objects (Rhino keeps running for hours)
        obj.Dispose()
    pic_dir = os.path.join(SHEETS, "pictures")              # the tinted plans the sheets show (one per plan)
    if not os.path.isdir(pic_dir):
        os.makedirs(pic_dir)
    fn = os.path.join(pic_dir, name + ".png")
    big.Save(fn, sd.Imaging.ImageFormat.Png)
    big.Dispose()
    small.Dispose()
    gid = pen.doc.Objects.AddPictureFrame(rg.Plane(rg.Point3d(wx0 + dx, wy0, -0.03), rg.Vector3d.ZAxis), fn, False, ww, wh, True, True)   # embedded: the file keeps the picture
    o = pen.doc.Objects.FindId(gid)
    if o is not None:
        o.Attributes.LayerIndex = pen.L["daylight"]
        o.CommitChanges()
        pen._keep(gid)


def _verdict_below(pen, x, y, verdict, detail):
    """The verdict under a plan: the word large in its colour, one plain line of detail under it."""
    u = pen.u
    h = 0.55 * u
    pen.text(verdict, x, y, h, VCOL[verdict], bold=True)
    pen.text(u"·  " + detail, x + (len(verdict) * 0.72 + 0.6) * h, y, h, INK)


def _plan(pen, shop, side, dx, name):
    """One plan (before or after), shifted dx metres to the right."""
    u = pen.u
    plan, res = side["plan"], side["res"]
    mv = lambda pts: [(p[0] + dx, p[1]) for p in pts]
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    _picture(pen, shop, res, plan, res["verdict"], name, dx)
    if not shop.get("image"):
        _walls(pen, mv(pts))
    for a, b in shop["facade"]:                                   # street façade: a solid blue band on the wall
        nx, ny = _outward(pts, a, b)
        pen.fill([mv([(a[0], a[1]), (b[0], b[1]), (b[0] + nx * 0.3, b[1] + ny * 0.3), (a[0] + nx * 0.3, a[1] + ny * 0.3)])],
                 "walls", flags.FACADE_RGB, 0.006)
    for q in plan.get("corridors", []):
        pen.fill([mv(q["pts"])], "patios", CORR_RGB, 0.002)
    for i, un in enumerate(plan.get("units", [])):
        bad = not un.get("ok", True)
        for r in un["rooms"]:
            if len(r["pts"]) < 3:
                continue
            pen.line(mv(r["pts"]), "flats", BADC if not r.get("ok", True) else (88, 92, 100), 0.18, 0.01, closed=True)
            if min(r["w"], r["d"]) >= 2.6 * u and r["kind"] != "hall":
                cx = sum(p[0] for p in r["pts"]) / len(r["pts"]) + dx
                cy = sum(p[1] for p in r["pts"]) / len(r["pts"])
                pen.text(r["name"], cx, cy + 0.25 * u, 0.36 * u, MUTED, centre=True)
        if len(un["outline"]) >= 3:
            pen.line(mv(un["outline"]), "flats", BADC if bad else INK, 0.5, 0.012, closed=True)
            ux = sum(p[0] for p in un["outline"]) / len(un["outline"]) + dx
            uy = sum(p[1] for p in un["outline"]) / len(un["outline"])
            pen.text(u"F%d %s" % (i + 1, un["type"].replace("bed", "-bed")), ux, uy - 0.35 * u, 0.42 * u, BADC if bad else INK, bold=True, centre=True)
    for pt in plan.get("patios", []):
        q = pt["pts"]
        cx, cy = sum(p[0] for p in q) / len(q) + dx, sum(p[1] for p in q) / len(q)
        pen.line(mv(q), "patios", BLUE, 0.25, 0.012, closed=True)
        pen.text(u"patio %.0f m²" % pt["area"], cx, cy + 0.2 * u, 0.4 * u, BLUE, centre=True)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pen.dim((min(xs) + dx, min(ys)), (max(xs) + dx, min(ys)), -1.6 * u)
    pen.dim((min(xs) + dx, max(ys)), (min(xs) + dx, min(ys)), -1.6 * u)


def _rule_lines(pen, res, x, y, width):
    u = pen.u
    h = 0.42 * u
    for c in res["cards"]:
        pen.mark(x, y - 0.9 * h, 0.7 * h, c["ok"])
        pen.text(u"%s: %s %s" % (c["title"], c["value"], c["limit"]), x + 1.3 * h, y, h, INK if c["ok"] else BADC, width=width - 1.3 * h)
        lines = 1 + int(len(u"%s: %s %s" % (c["title"], c["value"], c["limit"])) * 0.55 * h / max(width - 1.3 * h, 1.0))
        pen.text(c["cite"], x + 1.3 * h, y - (1.35 * lines) * h, 0.78 * h, MUTED, width=width - 1.3 * h)
        y -= (1.35 * lines + 1.6) * h
    return y


def _after_head(case):
    a, b = case["after"], case["before"]["res"]
    if a["plan"].get("patios"):
        kinds = sorted(set(p["kind"] for p in a["plan"]["patios"]))
        return u"AFTER · smallest change: " + ", ".join(kinds) + u" + shared corridor"
    if b["verdict"] == "YES":
        return u"AFTER · no change needed"
    return u"AFTER · no building work helps"


# ---------- the sheet ----------
def draw(doc, case, name, origin=None, title=None):
    """Before / after sheet for one case; placed at origin (lower-left), or beside earlier sheets."""
    clear(doc, name)
    L = layers_for(doc, name)
    shop = case["shop"]
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    W, H = x1 - x0, y1 - y0
    gap = max(6.0, 0.35 * W)
    u = max(2 * W + gap, H * 1.6, 16.0) / 55.0
    pen = Pen(doc, L, u)
    dx = W + gap
    b, a = case["before"]["res"], case["after"]["res"]
    if origin is None:
        origin = next_origin(doc)

    # header
    top = y1 + 6.5 * u
    pen.text(title or u"NOMAD · before and after", x0, top, 1.25 * u, INK, bold=True)
    pen.text(u"%s  ·  %.0f m²  ·  asked: %s" % (shop.get("name", name), a["shop_m2"], case["mix_text"]), x0, top - 1.85 * u, 0.6 * u, MUTED)

    # the two plans
    for side, d, head, sub in ((case["before"], 0.0, u"BEFORE · as it is", b), (case["after"], dx, _after_head(case), a)):
        pen.text(head, x0 + d, y1 + 2.4 * u, 0.62 * u, INK, bold=True)
        _plan(pen, shop, side, d, name + ("_after" if d else "_before"))
        _verdict_below(pen, x0 + d, y0 - 2.5 * u, sub["verdict"],
                       u"%d of %d flats pass every rule" % (sub["flats_passing"], sub["flats_asked"]))

    # text under the plans: rules (after) | how it was checked | result + what changed
    ty = y0 - 4.6 * u
    colw = (2 * W + gap) / 3.0 - u
    pen.text(u"Rules after the change", x0, ty, 0.55 * u, INK, bold=True)
    end1 = _rule_lines(pen, a, x0, ty - 1.1 * u, colw)
    cx = x0 + colw + 1.5 * u
    day = a["daylight"]
    pen.text(u"How it was checked", cx, ty, 0.55 * u, INK, bold=True)
    pen.text(u"Rhino 7 + Grasshopper (NOMAD.gh). The colours show daylight: warm near a window or patio, pale at %.1f m "
             u"(a design assumption, not a law), grey for the service band, dark where no daylight reaches. "
             u"Each flat is checked against Decret 141/2012 Annex 1 and the Barcelona MPGM 2004; each rule names its article. "
             u"Stage 6 tries the shop as it is, then adds patios and a shared corridor one at a time and keeps the change "
             u"that houses the most flats with the least work (%d layout%s tried)." % (day["lit_depth"], case.get("tried", 1),
                                                                                "" if case.get("tried", 1) == 1 else "s"),
             cx, ty - 1.1 * u, 0.42 * u, INK, width=colw)
    rx = cx + colw + 1.5 * u
    pen.text(u"Result", rx, ty, 0.55 * u, INK, bold=True)
    pen.text(u"Before: %s, %d of %d flats. After: %s, %d of %d flats.\nDaylight after: lit %.0f m² (%.0f%%), service %.0f m², "
             u"dark %.0f m² of %.0f m². Housing: %.0f m²." % (b["verdict"], b["flats_passing"], b["flats_asked"], a["verdict"],
                                                            a["flats_passing"], a["flats_asked"], day["area"]["lit"], 100 * day["share"]["lit"],
                                                            day["area"]["service"], day["area"]["dark"], a["shop_m2"], a["housing_m2"]),
             rx, ty - 1.1 * u, 0.42 * u, INK, width=colw)
    if a.get("interventions"):
        pen.text(u"What changed", rx, ty - 5.4 * u, 0.55 * u, INK, bold=True)
        pen.text(u"\n".join(a["interventions"]) + u"\nAssumed: the patio can be cut through the ground-floor roof (check on site); "
                 u"a room on a patio of this size counts as lit (confirm with the authority).", rx, ty - 6.5 * u, 0.4 * u, INK, width=colw)
    yb = min(end1, ty - 13.0 * u) - 1.0 * u
    pen.text(u"NOMAD // IAAC MAAI // %s // dimensions in cm // %s" % (datetime.date.today().isoformat(), shop.get("source", "")),
             x0, yb, 0.34 * u, MUTED)

    # white paper behind everything (for the picture), then move the sheet to its place in the file
    fx0, fx1, fy0, fy1 = x0 - 3 * u, x0 + 2 * W + gap + 3 * u, yb - 1.2 * u, top + 1.5 * u
    pen.fill([[(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]], "paper", (255, 255, 255), -0.06)
    ox, oy = origin
    xf = rg.Transform.Translation(ox - fx0, oy - fy0, 0)
    for gid in pen.ids:
        doc.Objects.Transform(gid, xf, True)
    doc.Views.Redraw()
    return rg.BoundingBox(rg.Point3d(ox, oy, 0), rg.Point3d(ox + fx1 - fx0, oy + fy1 - fy0, 0))


def capture(doc, box, path, width=3000):
    """Top view zoomed to one sheet, saved as PNG and cropped to it."""
    view = None
    for v in doc.Views:
        if v.ActiveViewport.Name == "Top":
            view = v
    view = view or doc.Views.ActiveView
    vp = view.ActiveViewport
    vp.SetProjection(Rhino.Display.DefinedViewportProjection.Top, "Top", False)
    try:
        vp.DisplayMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    except Exception:
        pass
    vp.ZoomBoundingBox(box)
    view.Redraw()
    size = vp.Size
    h = int(width * float(size.Height) / max(size.Width, 1))
    vc = Rhino.Display.ViewCapture()
    vc.Width, vc.Height = width, h
    vc.ScaleScreenItems = False
    vc.DrawAxes = vc.DrawGrid = vc.DrawGridAxes = False
    vc.TransparentBackground = False
    bmp = vc.CaptureToBitmap(view)
    if bmp is None:
        return None
    s = float(width) / size.Width
    c0 = vp.WorldToClient(rg.Point3d(box.Min.X, box.Max.Y, 0))
    c1 = vp.WorldToClient(rg.Point3d(box.Max.X, box.Min.Y, 0))
    rx, ry = max(0, int(c0.X * s) + 2), max(0, int(c0.Y * s) + 2)
    rw, rh = min(width - rx, int((c1.X - c0.X) * s) - 4), min(h - ry, int((c1.Y - c0.Y) * s) - 4)
    if rw > 50 and rh > 50:
        crop = bmp.Clone(sd.Rectangle(rx, ry, rw, rh), bmp.PixelFormat)
        bmp.Dispose()
        bmp = crop
    bmp.Save(path, sd.Imaging.ImageFormat.Png)
    bmp.Dispose()
    return path


# ---------- the demo sheet: Stage 5 flags + Stage 6 three iterations ----------
def draw_story(doc, case, name, origin=None, title=None):
    """One row of plans: STAGE 5 flags (the shop as it is) and STAGE 6 iterations 1-3, each with its verdict
    and number of homes; under them the rules, how it was checked and a results table.
    Returns (frame box, [x offset of each iteration plan], plan box size) so Stage 7 can put the 3D under each one."""
    clear(doc, name)
    L = layers_for(doc, name)
    shop = case["shop"]
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    W, H = x1 - x0, y1 - y0
    gap = max(5.0, 0.3 * W)
    n = 1 + len(case["iterations"])
    total = n * W + (n - 1) * gap
    u = max(total, H * 2.2, 24.0) / 70.0
    pen = Pen(doc, L, u)
    if origin is None:
        origin = next_origin(doc)
    b = case["before"]["res"]

    top = y1 + 6.5 * u
    pen.text(title or u"NOMAD · from a shop to homes", x0, top, 1.25 * u, INK, bold=True)
    pen.text(u"%s  ·  %.0f m²  ·  asked: %s" % (shop.get("name", name), b["shop_m2"], case["mix_text"]), x0, top - 1.85 * u, 0.6 * u, MUTED)
    panels = [(u"STAGE 5 · FLAGS · the shop as it is", case["before"])] + \
             [(u"STAGE 6 · " + it["label"], it) for it in case["iterations"]]
    offs = []
    for k, (head, side) in enumerate(panels):
        d = k * (W + gap)
        r = side["res"]
        pen.text(head, x0 + d, y1 + 2.4 * u, 0.55 * u, INK, bold=True)
        line = (u"%d of %d flats pass" % (r["flats_passing"], r["flats_asked"]) if k == 0 else
                u"%d home%s" % (side["homes"], "" if side["homes"] == 1 else "s"))
        if k and side["plan"].get("patios"):
            line += u" · + patio & corridor"
        _plan(pen, shop, side, d, name + "_p%d" % k)
        _verdict_below(pen, x0 + d, y0 - 2.5 * u, r["verdict"], line)
        if k:
            offs.append(d)

    ty = y0 - 4.6 * u
    colw = total / 3.0 - u
    pen.text(u"Stage 5 rules, the shop as it is", x0, ty, 0.55 * u, INK, bold=True)
    end1 = _rule_lines(pen, b, x0, ty - 1.1 * u, colw)
    cx = x0 + colw + 1.5 * u
    pen.text(u"How it was checked", cx, ty, 0.55 * u, INK, bold=True)
    pen.text(u"Rhino 7 + Grasshopper (NOMAD.gh). Stage 5 checks the shop against Decret 141/2012 Annex 1 and the Barcelona "
             u"MPGM 2004; each rule names its article. Stage 6 draws three 2D options: 1 the flats asked for, 2 the same "
             u"with compact (still legal) room sizes, 3 as many homes as fit. Each may add a light patio (Decret 141/2012 "
             u"Annex 1 2.5.1) and a 1,20 m shared corridor (CTE DB-SUA Anejo A) when that houses more flats. "
             u"Colours: daylight from windows and patios (lit to %.1f m is a design assumption, not a law)." % b["daylight"]["lit_depth"],
             cx, ty - 1.1 * u, 0.42 * u, INK, width=colw)
    rx = cx + colw + 1.5 * u
    pen.text(u"Result", rx, ty, 0.55 * u, INK, bold=True)
    rows = [u"As it is: %s (%d of %d flats asked)" % (b["verdict"], b["flats_passing"], b["flats_asked"])]
    for it in case["iterations"]:
        r = it["res"]
        rows.append(u"Iteration %s: %d home%s, %s%s" % (it["label"], it["homes"], "" if it["homes"] == 1 else "s", r["verdict"],
                                                       u", patio + corridor" if it["plan"].get("patios") else u""))
    best = max(case["iterations"], key=lambda it: it["homes"])
    rows.append(u"\nMost homes: %d, in %.0f m² of housing out of %.0f m²." % (best["homes"], best["res"]["housing_m2"], b["shop_m2"]))
    pen.text(u"\n".join(rows), rx, ty - 1.1 * u, 0.45 * u, INK, width=colw)
    pen.text(u"Assumed: flats are entered from the street or the corridor; a patio can be cut through the ground-floor roof "
             u"(check on site); a room on a patio counts as lit (confirm with the authority).", rx, ty - 7.6 * u, 0.36 * u, MUTED, width=colw)
    yb = min(end1, ty - 11.0 * u) - 1.0 * u
    pen.text(u"NOMAD // IAAC MAAI // %s // dimensions in cm // %s" % (datetime.date.today().isoformat(), shop.get("source", "")),
             x0, yb, 0.34 * u, MUTED)
    fx0, fx1, fy0, fy1 = x0 - 3 * u, x0 + total + 3 * u, yb - 1.2 * u, top + 1.5 * u
    pen.fill([[(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]], "paper", (255, 255, 255), -0.06)
    ox, oy = origin
    xf = rg.Transform.Translation(ox - fx0, oy - fy0, 0)
    for gid in pen.ids:
        doc.Objects.Transform(gid, xf, True)
    doc.Views.Redraw()
    box = rg.BoundingBox(rg.Point3d(ox, oy, 0), rg.Point3d(ox + fx1 - fx0, oy + fy1 - fy0, 0))
    shift = (ox - fx0, oy - fy0)
    return box, offs, shift
