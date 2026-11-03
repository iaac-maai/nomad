"""Nomad - draw saved NOMAD results (results/sheets/recipes/*.json) as clean plans and 3D views, in the colour
scheme of the first generated plans (lab book E05): orange living, purple bedrooms, yellow kitchen, blue bath, grey
hall, red = fails a rule, a thick blue line on the street façade. Under the rooms a very light daylight gradient
(pale yellow at the windows, white, soft blue-grey where it is dark) shows the zoning without hiding the plan.

Nothing is recomputed: the plans are drawn exactly as NOMAD made them in Rhino (same geometry, same checks).
Outputs: results/figures/<case>_<panel>_plan.png and <case>_<panel>_3d.png
Run: .venv/Scripts/python src/book/draw_cases.py [case name ...]
"""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "check"))
import flags  # noqa: E402

REC = ROOT / "results" / "sheets" / "recipes"
OUT = ROOT / "results" / "figures"
INK = "#1d2733"


def c(rgb, a=1.0):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, a)


def _poly(pts):
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def gradient(ax, shop, plan, res):
    """The daylight zoning as one smooth image clipped to the shop outline (very light)."""
    day = res["daylight"]
    outline = _poly(shop["outline"])
    light = list(shop["facade"])
    for pt in plan.get("patios", []):
        q = pt["pts"]
        light += [[q[i], q[(i + 1) % len(q)]] for i in range(len(q))]
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    step = 0.25
    gx = np.arange(min(xs), max(xs) + step, step)
    gy = np.arange(min(ys), max(ys) + step, step)
    img = np.ones((len(gy), len(gx), 4))
    for j, y in enumerate(gy):
        for i, x in enumerate(gx):
            d = min(flags._seg_dist(x, y, a, b) for a, b in light) if light else 99.0
            img[j, i] = c(flags.band_colour(d, day["lit_depth"], day["service_depth"]))
    im = ax.imshow(img, extent=(gx[0] - step / 2, gx[-1] + step / 2, gy[0] - step / 2, gy[-1] + step / 2),
                   origin="lower", interpolation="bilinear", zorder=0)
    clip = Polygon(outline, closed=True, transform=ax.transData)
    im.set_clip_path(clip)


def plan_png(shop, plan, res, path, labels=True, size=4.2):
    outline = _poly(shop["outline"])
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    W, H = max(xs) - min(xs), max(ys) - min(ys)
    fig, ax = plt.subplots(figsize=(size, size * H / max(W, 1e-6)) if H < W else (size * W / max(H, 1e-6), size))
    gradient(ax, shop, plan, res)
    for q in plan.get("corridors", []):
        ax.add_patch(Polygon(_poly(q["pts"]), closed=True, facecolor=c(flags.CORRIDOR_RGB), edgecolor="none", zorder=1))
    for pt in plan.get("patios", []):
        q = _poly(pt["pts"])
        ax.add_patch(Polygon(q, closed=True, facecolor=c(flags.PATIO_RGB), edgecolor=c(flags.FACADE_RGB, 0.8), lw=0.8, zorder=2))
        ax.text(sum(p[0] for p in q) / len(q), sum(p[1] for p in q) / len(q), "patio\n%.0f m²" % pt["area"],
                ha="center", va="center", fontsize=5.5, color=c(flags.FACADE_RGB), zorder=6)
    for i, u in enumerate(plan.get("units", [])):
        for r in u["rooms"]:
            if len(r["pts"]) < 3:
                continue
            ok = r.get("ok", True) and u.get("ok", True)
            col = flags.ROOM_RGB.get(r["kind"], flags.ROOM_RGB["hall"]) if ok else flags.FAIL_RGB
            ax.add_patch(Polygon(_poly(r["pts"]), closed=True, facecolor=c(col, 0.62), edgecolor=c((70, 74, 82), 0.9),
                                 lw=0.45, joinstyle="miter", zorder=3))
        if len(u["outline"]) >= 3:
            q = _poly(u["outline"])
            ax.add_patch(Polygon(q, closed=True, facecolor="none", edgecolor=INK, lw=1.1, joinstyle="miter", zorder=4))
            if labels:
                ax.text(sum(p[0] for p in q) / len(q), sum(p[1] for p in q) / len(q), "F%d" % (i + 1), ha="center",
                        va="center", fontsize=6, color=INK, fontweight="bold", zorder=6)
    ax.add_patch(Polygon(outline, closed=True, facecolor="none", edgecolor=c((90, 90, 90)), lw=1.4, joinstyle="miter", zorder=5))
    for a, b in shop["facade"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color=c(flags.FACADE_RGB), lw=3.2, solid_capstyle="butt", zorder=5)
    pad = 0.03 * max(W, H)
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def model_png(shop, plan, path, size=4.2):
    """E05.3 style: each room a solid coloured block, shop outline, blue façade line, patios and corridor on the floor."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    outline = _poly(shop["outline"])
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    Hh = 2.8
    fig = plt.figure(figsize=(size, size * 0.8))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot([p[0] for p in outline + outline[:1]], [p[1] for p in outline + outline[:1]], 0, color="#777", lw=0.8)
    for q in plan.get("patios", []) + plan.get("corridors", []):
        pts = _poly(q["pts"])
        col = flags.PATIO_RGB if "area" in q else flags.CORRIDOR_RGB
        ax.add_collection3d(Poly3DCollection([[(x, y, 0.02) for x, y in pts]], facecolor=c(col), edgecolor="none"))
    for u in plan.get("units", []):
        for r in u["rooms"]:
            if len(r["pts"]) < 3:
                continue
            ok = r.get("ok", True) and u.get("ok", True)
            col = flags.ROOM_RGB.get(r["kind"], flags.ROOM_RGB["hall"]) if ok else flags.FAIL_RGB
            h = 0.05 if r["kind"] == "hall" else Hh
            p = _poly(r["pts"])
            faces = [[(x, y, h) for x, y in p]]
            faces += [[(p[k][0], p[k][1], 0), (p[(k + 1) % len(p)][0], p[(k + 1) % len(p)][1], 0),
                       (p[(k + 1) % len(p)][0], p[(k + 1) % len(p)][1], h), (p[k][0], p[k][1], h)] for k in range(len(p))]
            ax.add_collection3d(Poly3DCollection(faces, facecolor=c(col), edgecolor="#444", linewidth=0.3, alpha=0.95))
    for a, b in shop["facade"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], [0.06, 0.06], color=c(flags.FACADE_RGB), linewidth=2.5)
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_zlim(0, Hh)
    ax.set_box_aspect((dx, dy, Hh), zoom=0.95)
    ax.view_init(elev=32, azim=-60)
    ax.set_axis_off()
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.0, facecolor="white")
    plt.close(fig)


def draw(name):
    rec = json.load(open(REC / (name + ".json"), encoding="utf-8"))
    case = rec["case"]
    shop = case["shop"]
    OUT.mkdir(parents=True, exist_ok=True)
    panels = [("p0", case["before"])] + [("p%d" % (k + 1), it) for k, it in enumerate(case.get("iterations", []))]
    if not case.get("story"):
        panels = [("before", case["before"]), ("after", case["after"])]
    for key, side in panels:
        plan_png(shop, side["plan"], side["res"], OUT / ("%s_%s_plan.png" % (name, key)))
        if key != "p0" and key != "before":
            model_png(shop, side["plan"], OUT / ("%s_%s_3d.png" % (name, key)))
    print("drew", name, len(panels), "panels")


if __name__ == "__main__":
    names = sys.argv[1:] or [p.stem for p in sorted(REC.glob("*.json"))]
    for n in names:
        draw(n)
