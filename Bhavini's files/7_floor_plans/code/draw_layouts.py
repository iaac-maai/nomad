"""Nomad - draw the layouts NOMAD makes for a few shops, side by side, to judge them by eye.

Rooms in the E05 colours, the street façade thick blue, patios light blue, corridors grey, each flat outlined in black
with its number. Used to compare the generator before and after a change.
Run: .venv/Scripts/python 7_floor_plans/code/draw_layouts.py [tag]   -> 7_floor_plans/output/generation/layouts_<tag>.png
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly

ROOT = Path(__file__).resolve().parents[2]
for p in ("rhino_grasshopper/code", "7_floor_plans/code", "6_check_the_shop/code"):
    sys.path.insert(0, str(ROOT / p))
import nomad_core as core  # noqa: E402

COL = {"living": "#F09F26", "bed_main": "#8078DE", "bed": "#B0A8ED", "kitchen": "#FAC775", "bath": "#85B8EB",
       "hall": "#CCCCCC", "corridor": "#D8D6D0", "patio": "#A0CDEB"}
MIX = {"1bed": 2, "2bed": 1}
REF_BACK = "0310212DF3801A"                                          # a deep Eixample shop with a block-interior façade


def shops():
    """Two test shops (Swiss Dwellings) and two real Barcelona shops: a narrow-deep one and a wide one."""
    out = [core.shop_by_id(146519), core.shop_by_id(152418)]
    S = json.load(open(ROOT / "2_building/output/real_shops/shells.json", encoding="utf-8"))
    for ref in ("2249707DF3824G", "7823505DF2872D", REF_BACK):
        s = S.get(ref)
        if s:
            out.append({"ok": True, "outline": s["outline"], "facade": s["facade"], "street": s["street"], "height": 2.7, "name": "BCN_" + ref,
                        "source": ref, "image": None})
    return out


def draw(ax, shop, plan, title):
    ax.add_patch(MPoly(shop["outline"], closed=True, fc="#ECE8F2", ec="#555", lw=1.2, hatch="..", alpha=0.9))   # other use
    for q in plan.get("patios", []):
        ax.add_patch(MPoly(q["pts"], closed=True, fc=COL["patio"], ec="#555", lw=0.6))
    for q in plan.get("corridors", []):
        ax.add_patch(MPoly(q["pts"], closed=True, fc=COL["corridor"], ec="#777", lw=0.6, hatch="//"))
    for i, u in enumerate(plan.get("units", [])):
        for r in u["rooms"]:
            if len(r["pts"]) >= 3:
                ax.add_patch(MPoly(r["pts"], closed=True, fc=COL.get(r["kind"], "#ddd"), ec="white", lw=0.8))
        if len(u["outline"]) >= 3:
            ax.add_patch(MPoly(u["outline"], closed=True, fill=False, ec="black", lw=1.6))
            xs, ys = zip(*u["outline"])
            ax.text(sum(xs) / len(xs), sum(ys) / len(ys), "F%d\n%s" % (i + 1, u["type"]), ha="center", va="center", fontsize=7,
                    color="#222" if u.get("ok") else "#C4473A", fontweight="bold")
    for a, b in shop["facade"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#2C5D8F", lw=3.5, solid_capstyle="butt")
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title, fontsize=8)


def main(tag="now"):
    sh = shops()
    fig, axes = plt.subplots(len(sh), 4, figsize=(16, 4.2 * len(sh)))
    for row, shop in zip(axes, sh):
        if tag == "before":
            story = core.run_story(shop, MIX)
            plans = [("as it is", story["before"]["plan"])] + [(it["label"], it["plan"]) for it in story["iterations"]]
        else:
            import plan2
            before, its, tried = plan2.iterations(shop["outline"], shop["facade"], shop["height"], MIX, core.data()["programs"],
                                                  street=shop.get("street"))
            plans = [("as it is", before)] + [(n, p) for n, p, m in its]
        for ax in row[len(plans):]:
            ax.axis("off")
        for ax, (lab, plan) in zip(row, plans):
            draw(ax, shop, plan, "%s | %s: %d homes, %d pass, %.0f m² other use" % (
                shop["name"], lab, len(plan.get("units", [])), plan.get("compliant", 0), plan.get("unused_m2", 0)))
    out = ROOT / "7_floor_plans/output/generation" / ("layouts_%s.png" % tag)
    fig.tight_layout(); fig.savefig(out, dpi=90)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:2])
