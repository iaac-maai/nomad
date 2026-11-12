# -*- coding: utf-8 -*-
"""NOMAD Stage 7: a 3D model of each Stage 6 iteration, built in Rhino (IronPython 2.7).
7.1 zoning = build(): each room a solid block.  7.2 walls = build_walls(): the same rooms as walls with
doors and windows (see that function).

Per iteration: each room a solid coloured block (living orange, bedrooms purple, kitchen yellow, bath blue,
hall low and grey; red = fails a rule), a thin slab for the shop, a blue strip along the street façade,
light-blue patio floors open to the sky and a grey shared corridor. Each model goes on
"06 NOMAD experiments::<name>::3d iteration k", right under its 2D plan, so the Rhino file shows plan + model.
   build(doc, shop, plan, move, layer) -> [ids]      capture(doc, ids, png)
"""
import os
import Rhino
import Rhino.Geometry as rg
import System
import System.Drawing as sd

H_ROOM, SLAB = 2.7, 0.15       # rooms as solid blocks 2,70 m high (as in the first 3D views)
import flags
COL = flags.ROOM_RGB                                          # the E05 colours (plans, 3D, slides)
RED, WALL, GLASS, PATIO, CORR, SLABC = flags.FAIL_RGB, (250, 250, 248), flags.FACADE_RGB, flags.PATIO_RGB, flags.CORRIDOR_RGB, (245, 245, 243)


def _attr(doc, layer, rgb, clean=False):
    a = Rhino.DocObjects.ObjectAttributes()
    if clean:
        a.WireDensity = -1                                    # no isocurves: only the real edges are drawn
    a.LayerIndex = layer
    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    a.ObjectColor = sd.Color.FromArgb(rgb[0], rgb[1], rgb[2])
    return a


def _crv(pts, z, mv):
    p = [rg.Point3d(x + mv[0], y + mv[1], z) for x, y in pts]
    if p[0].DistanceTo(p[-1]) > 1e-6:
        p.append(p[0])
    return rg.PolylineCurve(p)


def _floor(pts, z, mv):
    b = rg.Brep.CreatePlanarBreps(_crv(pts, z, mv), 0.001)
    return b[0] if b else None


def _walls(pts, z0, h, mv):
    srf = rg.Surface.CreateExtrusion(_crv(pts, z0, mv), rg.Vector3d(0, 0, h))
    return srf.ToBrep() if srf is not None else None


def layer(doc, path):
    import nomad_sheet
    return nomad_sheet._layer(doc, path)


ZOFF = [0.0]                      # height of the level being drawn (whole buildings: one storey above another)


def _block(pts, z0, h, mv):
    """A solid room block (closed extrusion of the room outline)."""
    z0 = z0 + ZOFF[0]
    srf = rg.Surface.CreateExtrusion(_crv(pts, z0, mv), rg.Vector3d(0, 0, h))
    b = srf.ToBrep().CapPlanarHoles(0.001) if srf is not None else None
    if b is not None and b.SolidOrientation == rg.BrepSolidOrientation.Inward:
        b.Flip()                                              # faces point out, so Shaded mode lights the tops
    return b


def build(doc, shop, plan, mv, lay):
    """Add the model of one plan, moved by mv = (dx, dy): each room a solid coloured block (red = fails a rule),
    the hall low, a thin light slab for the shop, a blue strip on the street façade, light-blue patios and a grey
    shared corridor. Returns the object ids."""
    ids = []
    add = lambda g, rgb: ids.append(doc.Objects.AddBrep(g, _attr(doc, lay, rgb))) if g is not None else None
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    add(_block(pts, -SLAB, SLAB, mv), SLABC)
    for a, b in shop["facade"]:                                # the street façade: a low blue strip on its edge
        ln = rg.LineCurve(rg.Point3d(a[0] + mv[0], a[1] + mv[1], 0), rg.Point3d(b[0] + mv[0], b[1] + mv[1], 0))
        s = rg.Surface.CreateExtrusion(ln, rg.Vector3d(0, 0, 0.35))
        if s is not None:
            add(s.ToBrep(), GLASS)
    for q in plan.get("patios", []):
        add(_block(q["pts"], 0.0, 0.03, mv), PATIO)
    for q in plan.get("corridors", []):
        add(_block(q["pts"], 0.0, 0.04, mv), CORR)
    for u in plan.get("units", []):
        for r in u["rooms"]:
            if len(r["pts"]) < 3:
                continue
            ok = r.get("ok", True) and u.get("ok", True)
            h = 0.08 if r["kind"] == "hall" else H_ROOM
            add(_block(r["pts"], 0.0, h, mv), COL.get(r["kind"], COL["hall"]) if ok else RED)
    return [g for g in ids if g != System.Guid.Empty]


# ---------- Stage 7b: walls, doors and windows (the zoning blocks turned into a built model) ----------
T_OUT, T_IN = 0.30, 0.10          # shell wall / partition thickness, m
SILL, HEAD = 0.90, 2.40           # windows: 0,90 m sill to 2,40 m head (1,5 m tall, as layout.py assumes)
DOOR_W, DOOR_H, ENTRY_W = 0.80, 2.10, 0.90
WIN_FRAC = 0.60                   # new façade window = 60% of the room width (layout.py)
WALLC, GLASSC, DOORC = (238, 238, 234), (170, 205, 235), (120, 124, 130)


def _box(a, b, t, z0, z1, mv, off=0.0):
    """A wall piece from a to b (2D), thickness t, between heights z0 and z1, its centre line moved off to the left."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = (dx * dx + dy * dy) ** 0.5
    if L < 0.02 or z1 - z0 < 0.02:
        return None
    lx, ly = -dy / L, dx / L
    a, b = (a[0] + lx * off, a[1] + ly * off), (b[0] + lx * off, b[1] + ly * off)
    nx, ny = lx * t / 2.0, ly * t / 2.0
    pts = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    return _block(pts, z0, z1 - z0, mv)


GAP = 0.25                        # rooms are drawn ~20 cm apart (the wall zone): tolerance for "same wall"


def _on(p, a, b, tol=GAP):
    return _d(p, (a, b)) < tol


def _edges(pts):
    n = len(pts)
    return [(tuple(pts[i]), tuple(pts[(i + 1) % n])) for i in range(n) if _seg_len(pts[i], pts[(i + 1) % n]) > 0.05]


def _shared(e, f, tol=GAP):
    """Where two edges lie on one line and overlap: (centre of the overlap, its length), else None."""
    (a, b), (c, d) = e, f
    L = _seg_len(a, b)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    off = lambda p: abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux)     # distance from the line through a, b
    if off(c) > tol or off(d) > tol:
        return None
    tc = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
    td = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy
    lo, hi = max(0.0, min(tc, td)), min(L, max(tc, td))
    if hi - lo < 0.2:
        return None
    m = (lo + hi) / 2.0
    sgn = 1.0 if ((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > 0 else -1.0   # centre of the gap between the two rooms
    g = (off(c) + off(d)) / 4.0
    return ((a[0] + ux * m + uy * g * sgn, a[1] + uy * m - ux * g * sgn), hi - lo)


def _openings(shop, plan):
    """Every door and window as (centre point, width, z0, z1, kind). Each flat is entered from the street
    (layout.py): an entry door in the hall's façade wall, or at one end of the living room's. Windows: each
    room's façade wall (not halls), 60% of its width. Doors: each room to its flat's hall, else to the living."""
    fac = [(tuple(a), tuple(b)) for a, b in shop["facade"]]
    on_fac = lambda e: any(_on(e[0], a, b, 0.2) and _on(e[1], a, b, 0.2) for a, b in fac)
    mid = lambda e, t: (e[0][0] + (e[1][0] - e[0][0]) * t, e[0][1] + (e[1][1] - e[0][1]) * t)
    ops = []
    for u in plan.get("units", []):
        rooms = [r for r in u["rooms"] if len(r["pts"]) >= 3]
        fronts = [(r, e) for r in rooms for e in _edges(r["pts"]) if on_fac(e)]
        if u.get("lib"):                                   # a real plan (plan3): its own doors and entrance; windows on the façade
            if u.get("entrance"):
                ops.append((tuple(u["entrance"]), max(ENTRY_W, 0.8), 0.0, DOOR_H, "entry"))
            for d in u.get("doors", []):
                ops.append((tuple(d["at"]), max(d["w"], 0.7), 0.0, DOOR_H, "door"))
            for r, e in fronts:
                if r["kind"] not in ("hall", "storage"):
                    L = _seg_len(*e)
                    ops.append((mid(e, 0.5), min(WIN_FRAC * L, L - 0.4), SILL, HEAD, "window"))
            continue
        entry = ([x for x in fronts if x[0]["kind"] == "hall" and _seg_len(*x[1]) > ENTRY_W + 0.2] +
                 [x for x in fronts if x[0]["kind"] == "living" and _seg_len(*x[1]) > ENTRY_W + 1.5])[:1]
        for r, e in fronts:
            L = _seg_len(*e)
            if entry and e == entry[0][1]:
                if r["kind"] == "hall":
                    ops.append((mid(e, 0.5), ENTRY_W, 0.0, DOOR_H, "entry"))
                    continue
                t0 = 0.25 + ENTRY_W                            # living: door near one end, window in the rest
                ops.append((mid(e, (0.25 + ENTRY_W / 2.0) / L), ENTRY_W, 0.0, DOOR_H, "entry"))
                rest = L - t0 - 0.3
                ops.append((mid(e, (t0 + 0.3 + rest / 2.0) / L), min(WIN_FRAC * L, rest - 0.3), SILL, HEAD, "window"))
                continue
            if r["kind"] != "hall":
                ops.append((mid(e, 0.5), min(WIN_FRAC * L, L - 0.4), SILL, HEAD, "window"))
        hub = [r for r in rooms if r["kind"] == "hall"] + [r for r in rooms if r["kind"] == "living"]
        for r in rooms:
            if hub and r is hub[0]:
                continue
            best = None
            for h in [x for x in hub if x is not r]:
                for e in _edges(r["pts"]):
                    for f in _edges(h["pts"]):
                        sh = _shared(e, f)
                        if sh and sh[1] >= DOOR_W + 0.2 and (best is None or sh[1] > best[1]):
                            best = sh
                if best:
                    break
            if best:
                ops.append((best[0], DOOR_W, 0.0, DOOR_H, "door"))
    return [o for o in ops if o[1] >= 0.3]                    # drop slivers on very short façade edges


def _wall_run(a, b, t, ops, mv, H, off=0.0):
    """One wall segment with its openings cut out: returns [(brep, kind)] (kind wall / glass / door)."""
    L = _seg_len(a, b)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    P = lambda s: (a[0] + ux * s, a[1] + uy * s)
    cuts = []
    for c, w, z0, z1, kind in ops:
        if _d(c, (a, b)) < GAP:
            s = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
            lo, hi = max(0.0, s - w / 2.0), min(L, s + w / 2.0)
            if hi - lo > 0.1:
                cuts.append((lo, hi, z0, z1, kind))
    cuts.sort()
    out, s = [], 0.0
    for lo, hi, z0, z1, kind in cuts:
        if lo > s:
            out.append((_box(P(s), P(lo), t, 0.0, H, mv, off), "wall"))
        out.append((_box(P(lo), P(hi), t, 0.0, z0, mv, off), "wall"))          # below the sill
        out.append((_box(P(lo), P(hi), t, z1, H, mv, off), "wall"))            # above the head
        if kind == "window":
            out.append((_box(P(lo), P(hi), 0.03, z0, z1, mv, off), "glass"))
        s = max(s, hi)
    if s < L:
        out.append((_box(P(s), P(L), t, 0.0, H, mv, off), "wall"))
    return out


FURN_H = {"wardrobe": 2.20, "fridge": 1.80, "worktop": 0.90, "bed_double": 0.50, "bed_single": 0.50, "sofa": 0.80,
          "table": 0.75, "wc": 0.40, "basin": 0.85, "shower": 0.06, "washer": 0.85}   # typical heights (wardrobe: 3.10.1)
FURNC = (245, 245, 242)


CORE = (150, 154, 160)


def build_walls(doc, shop, plan, mv, lay):
    """Stage 7b: the same layout as walls (shell 30 cm, partitions 10 cm, 2,70 m high, no roof), doors cut
    to the hall, windows 1,5 m tall in the street façade as light-blue glass, each room floor in its E05 colour
    (red = fails a rule), patios light blue, the corridor grey, the furniture off-white. A whole building
    (7_floor_plans/code/building.py) gets the same floor on every level and its stair + lift cores full height. Returns the object ids."""
    lv = plan.get("levels", 1)
    if lv > 1:
        one = dict(plan, levels=1)
        ids = build_walls(doc, shop, one, mv, lay)
        try:
            for k in range(1, lv):
                ZOFF[0] = k * plan.get("storey_h", 3.0)
                ids += build_walls(doc, shop, dict(one, patios=[]), mv, lay)
        finally:
            ZOFF[0] = 0.0
        for c in plan.get("cores", []):
            g = _block(c["pts"], 0.0, lv * plan.get("storey_h", 3.0), mv)
            if g is not None:
                ids.append(doc.Objects.AddBrep(g, _attr(doc, lay, CORE, True)))
        return [g for g in ids if g != System.Guid.Empty]
    ids = []
    add = lambda g, rgb: ids.append(doc.Objects.AddBrep(g, _attr(doc, lay, rgb, True))) if g is not None else None
    H = H_ROOM
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    add(_block(pts, -SLAB, SLAB, mv), SLABC)
    for q in plan.get("patios", []):
        add(_block(q["pts"], 0.0, 0.03, mv), PATIO)
    for q in plan.get("corridors", []):
        add(_block(q["pts"], 0.0, 0.03, mv), CORR)
    ops = _openings(shop, plan)
    shell = _edges(pts)
    on_shell = lambda e: any(_on(e[0], a, b) and _on(e[1], a, b) for a, b in shell)
    for u in plan.get("units", []):
        for r in u["rooms"]:
            if len(r["pts"]) < 3:
                continue
            ok = r.get("ok", True) and u.get("ok", True)
            add(_block(r["pts"], 0.0, 0.04, mv), COL.get(r["kind"], COL["hall"]) if ok else RED)   # coloured floor
            q = r["pts"]
            area2 = sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))
            out = -T_IN / 2.0 if area2 > 0 else T_IN / 2.0      # partition just outside the room: two neighbours fill the gap
            for e in _edges(q):
                if on_shell(e):
                    continue                                  # the shell wall is drawn once, below
                for g, kind in _wall_run(e[0], e[1], T_IN, ops, mv, H, out):
                    add(g, GLASSC if kind == "glass" else WALLC)
    for a, b in shell:
        for g, kind in _wall_run(a, b, T_OUT, ops, mv, H):
            add(g, GLASSC if kind == "glass" else WALLC)
    for u in plan.get("units", []):                             # furniture (7_floor_plans/code/furnish.py) at its usual height
        for x in u.get("furniture", []):
            add(_block(x["pts"], 0.04, FURN_H.get(x["kind"], 0.75), mv), FURNC)
    return [g for g in ids if g != System.Guid.Empty]


def _seg_len(a, b):
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def _d(p, s):
    (ax, ay), (bx, by) = s
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return ((p[0] - ax - t * dx) ** 2 + (p[1] - ay - t * dy) ** 2) ** 0.5


def _content_box(bmp, step=3):
    """Bounding box (x0, y0, x1, y1) of the non-transparent pixels of a captured bitmap (fast: read the bytes once)."""
    from System.Runtime.InteropServices import Marshal
    W, H = bmp.Width, bmp.Height
    data = bmp.LockBits(sd.Rectangle(0, 0, W, H), sd.Imaging.ImageLockMode.ReadOnly, sd.Imaging.PixelFormat.Format32bppArgb)
    n = data.Stride * H
    buf = System.Array.CreateInstance(System.Byte, n)
    Marshal.Copy(data.Scan0, buf, 0, n)
    stride = data.Stride
    bmp.UnlockBits(data)
    x0, y0, x1, y1 = W, H, 0, 0
    for y in range(0, H, step):
        row = y * stride
        for x in range(0, W, step):
            if buf[row + 4 * x + 3] > 10:                      # alpha: something was drawn here
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 <= x0 or y1 <= y0:
        return (0, 0, W, H)
    return (max(0, x0 - step), max(0, y0 - step), min(W, x1 + step), min(H, y1 + step))


def capture(doc, ids, path, width=1600, height=1100, steep=False):
    """A 3D view (from the south-west, above) of these objects only, white background, saved as PNG.
    steep: look down more (for the walls model, so the room floors show between the walls)."""
    bb = rg.BoundingBox.Empty
    for g in ids:
        o = doc.Objects.FindId(g)
        if o is not None:
            bb.Union(o.Geometry.GetBoundingBox(True))
    if not bb.IsValid:
        return None
    view = None
    for v in doc.Views:
        if v.ActiveViewport.Name == "Perspective":
            view = v
    view = view or doc.Views.ActiveView
    vp = view.ActiveViewport
    if not vp.IsPerspectiveProjection:
        vp.ChangeToPerspectiveProjection(True, 50.0)
    mode = Rhino.Display.DisplayModeDescription.FindByName("Shaded")
    if mode is not None:
        vp.DisplayMode = mode
    c = bb.Center
    span = max(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y)
    up = 1.5 if steep else 0.6
    vp.SetCameraLocations(c, rg.Point3d(c.X - 0.55 * span, c.Y - 0.75 * span, c.Z + up * span) if steep else
                          rg.Point3d(c.X - 0.85 * span, c.Y - 1.15 * span, c.Z + up * span))
    # show only this model while capturing
    hidden = []
    keep = set(ids)
    for o in doc.Objects:
        if o.Id not in keep and o.Visible:
            hidden.append(o.Id)
    for g in hidden:
        doc.Objects.Hide(g, True)
    vc = Rhino.Display.ViewCapture()
    vc.Width, vc.Height = width, height
    try:
        view.Size = sd.Size(width, height)                   # same shape as the picture, so the zoom fills it
    except Exception:
        pass
    vp.ZoomBoundingBox(bb)
    # zoom so the model fills ~90% of the picture: measure its 8 corners on screen
    corners = bb.GetCorners()
    pts = [vp.WorldToClient(q) for q in corners]
    sw, sh = vp.Size.Width, vp.Size.Height
    pw = max(q.X for q in pts) - min(q.X for q in pts)
    ph = max(q.Y for q in pts) - min(q.Y for q in pts)
    if pw > 1 and ph > 1:
        vp.Magnify(max(0.5, min(4.0, 0.9 * min(sw / pw, sh / ph))), False)
    for _ in range(3):                                       # let Rhino switch to Shaded before the picture
        view.Redraw()
        Rhino.RhinoApp.Wait()
    vc.ScaleScreenItems = False
    vc.DrawAxes = vc.DrawGrid = vc.DrawGridAxes = False
    vc.TransparentBackground = True
    bmp = vc.CaptureToBitmap(view)
    for g in hidden:
        doc.Objects.Show(g, True)
    if bmp is None:
        return None
    box = _content_box(bmp)                                   # crop to the model so it fills its slot on the board
    pad = 24
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    out = sd.Bitmap(w, h)
    g = sd.Graphics.FromImage(out)
    g.Clear(sd.Color.White)
    g.DrawImage(bmp, sd.Rectangle(pad, pad, box[2] - box[0], box[3] - box[1]),
                sd.Rectangle(box[0], box[1], box[2] - box[0], box[3] - box[1]), sd.GraphicsUnit.Pixel)
    g.Dispose()
    bmp.Dispose()
    out.Save(path, sd.Imaging.ImageFormat.Png)
    out.Dispose()
    doc.Views.Redraw()
    return path


def board(sheet_png, rows, path):
    """Presentation board: the 2D sheet on top, then one row of 3D pictures per stage.
    rows = [(heading, [png per iteration], [label per iteration])]."""
    top = sd.Bitmap(sheet_png)
    W = top.Width
    n = max([len(r[1]) for r in rows] + [1])
    cell_w = W // n
    cell_h = int(cell_w * 0.7)
    head = 70
    out = sd.Bitmap(W, top.Height + len(rows) * (head + cell_h + 40))
    g = sd.Graphics.FromImage(out)
    g.Clear(sd.Color.White)
    g.InterpolationMode = sd.Drawing2D.InterpolationMode.HighQualityBicubic
    g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit
    g.DrawImage(top, 0, 0, W, top.Height)
    f_head = sd.Font("Arial", 26.0, sd.FontStyle.Bold, sd.GraphicsUnit.Pixel)
    f_lab = sd.Font("Arial", 20.0, sd.FontStyle.Regular, sd.GraphicsUnit.Pixel)
    ink = sd.SolidBrush(sd.Color.FromArgb(28, 32, 38))
    y = top.Height
    for heading, pngs, labels in rows:
        g.DrawString(heading, f_head, ink, 40.0, float(y + 12))
        for k, p in enumerate(pngs):
            if not p or not os.path.exists(p):
                continue
            im = sd.Bitmap(p)
            s = min(float(cell_w - 20) / im.Width, float(cell_h - 30) / im.Height)
            w, h = int(im.Width * s), int(im.Height * s)
            g.DrawImage(im, k * cell_w + (cell_w - w) // 2, y + head, w, h)
            if k < len(labels):
                g.DrawString(labels[k], f_lab, ink, float(k * cell_w + 40), float(y + head + cell_h - 24))
            im.Dispose()
        y += head + cell_h + 40
    for o in (f_head, f_lab, ink, g):
        o.Dispose()
    top.Dispose()
    out.Save(path, sd.Imaging.ImageFormat.Png)
    out.Dispose()
    return path


def draw_demo(doc, story, name, sheets_dir, capture_pngs=True, origin=None):
    """Stage 5 + 6 sheet; under each iteration its Stage 7.1 zoning model (room blocks) and, under that, its
    Stage 7.2 model (walls, doors, windows); pictures and the board. Returns the board path (or, without
    pictures, the frame box including the models)."""
    import nomad_sheet
    box, offs, shift = nomad_sheet.draw_story(doc, story, name, origin=origin)
    pngs = {}
    if capture_pngs:
        pngs["sheet"] = nomad_sheet.capture(doc, box, os.path.join(sheets_dir, name + ".png"))
    shop = story["shop"]
    pts = shop["outline"]
    H = max(p[1] for p in pts) - min(p[1] for p in pts)
    down = (box.Max.Y - box.Min.Y) + 0.6 * H + 6.0               # zoning models sit under the sheet
    down2 = down + H + 8.0                                        # walls models under the zoning models
    models, walls = [], []
    for k, it in enumerate(story["iterations"]):
        for sub, lst, fn, dn in (("3d iteration %d", models, build, down), ("walls iteration %d", walls, build_walls, down2)):
            lay = nomad_sheet._layer(doc, nomad_sheet.PARENT + "::" + name + "::" + sub % (k + 1))
            for o in doc.Objects.FindByLayer(doc.Layers[lay]) or []:
                doc.Objects.Delete(o, True)
            lst.append(fn(doc, shop, it["plan"], (shift[0] + offs[k], shift[1] - dn), lay))
    if not capture_pngs:
        bb = rg.BoundingBox(box.Min, box.Max)
        for ids in models + walls:
            for g in ids:
                o = doc.Objects.FindId(g)
                if o is not None:
                    bb.Union(o.Geometry.GetBoundingBox(True))
        return bb
    shots = [capture(doc, ids, os.path.join(sheets_dir, "%s_3d_%d.png" % (name, k + 1))) for k, ids in enumerate(models)]
    wshots = [capture(doc, ids, os.path.join(sheets_dir, "%s_walls_%d.png" % (name, k + 1)), steep=True) for k, ids in enumerate(walls)]
    labels = [u"Iteration %s · %d home%s · %s" % (it["label"], it["homes"], "" if it["homes"] == 1 else "s", it["res"]["verdict"])
              for it in story["iterations"]]
    return board(pngs["sheet"], [(u"STAGE 7.1 · zoning: the rooms of each iteration (Rhino)", shots, labels),
                                 (u"STAGE 7.2 · walls, doors and windows (Rhino)", wshots, labels)],
                 os.path.join(sheets_dir, name + "_board.png"))
