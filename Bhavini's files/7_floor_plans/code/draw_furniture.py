"""Nomad - lab book figures for E28: real flats furnished and checked (furnish.py), your own plan read from a DXF
(own_plans.py), and a generated plan (library_fit.best_fits generate=True).
Run: .venv/Scripts/python 7_floor_plans/code/draw_furniture.py   ->   lab_book/figures/e28_*.png
"""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as P, Rectangle

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "7_floor_plans/code"), str(ROOT / "7_floor_plans/code")]
import furnish as U  # noqa: E402
import library_fit as F  # noqa: E402
import own_plans  # noqa: E402

COL = {"living": "#F09F26", "bed_main": "#8078DE", "bed": "#B0A8ED", "kitchen": "#FAC775", "bath": "#85B8EB", "hall": "#CCCCCC",
       "storage": "#B5B0A5"}
SHORT = {"bed_double": "bed", "bed_single": "bed", "wardrobe": "ward.", "worktop": "worktop", "fridge": "fr.", "wc": "WC",
         "basin": "bas.", "shower": "sh.", "washer": "wm", "sofa": "sofa", "table": "table"}
OUT = ROOT / "lab_book/figures"


def draw(ax, g, items, title):
    for r in g["rooms"]:
        ax.add_patch(P(r["pts"], closed=True, fc=COL.get(r["kind"], "#ddd"), ec="#1d2733", lw=0.7))
    for s in g.get("swings", []):
        x0, y0, x1, y1 = s["sweep"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#c0392b", lw=0.5, ls="--"))
    for it in items:
        x0, y0, x1, y1 = it["rect"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="white", ec="#1d2733", lw=0.9 if it["law"] else 0.5))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, SHORT.get(it["kind"], it["kind"]), fontsize=5.5, ha="center", va="center")
    ax.plot([0, g["W"]], [-0.15, -0.15], color="#2C5D8F", lw=2.5)
    ax.set_xlim(-0.4, g["W"] + 0.4); ax.set_ylim(-0.5, g["D"] + 0.4); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontsize=7.5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L = json.load(open(ROOT / "7_floor_plans/output/library/library_street.json"))
    picks = ([x for x in L if x["bedrooms"] == 1 and x["lit"] == ["front"]][:2] + [x for x in L if x["bedrooms"] == 2 and x["lit"] == ["front"]][:2] +
             [x for x in L if x["bedrooms"] == 3][:1] + [x for x in L if x["bedrooms"] == 2 and "back" in x["lit"]][:1])
    fig, axs = plt.subplots(2, 3, figsize=(13, 8.2))
    for ax, f in zip(axs.flat, picks):
        g = F.widen_doors(f)
        g["swings"] = F.swings(g)
        items, cs = U.furnish(g)
        draw(ax, g, items, "%s %s · %d bed · %s" % (f["source"], f["id"], f["bedrooms"], "passes" if U.passes(cs) else "fails"))
    fig.suptitle("Real flats furnished and checked: thick outline = asked by law (wardrobe 3.10.1, worktop 3.15.c, WC / basin / shower 3.15.b, "
                 "washing machine 3.15.d); thin = typical size (bed, sofa, table); red dashes = door swings. Street façade in blue.", fontsize=8)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    plt.savefig(OUT / "e28_furniture.png", dpi=130)
    plt.close(fig)
    # your own plan: the example DXF (rooms on layers named in Catalan, in mm, turned 23 degrees) read back
    text = (ROOT / "7_floor_plans/input/own_plans/own_plan_example.dxf").read_text(encoding="utf-8")
    raw = own_plans.from_dxf(text)
    entry, cs, msg = own_plans.read(text, "own plan example")
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.2))
    for r in raw["rooms"]:
        axs[0].add_patch(P(r["pts"], closed=True, fc=COL.get(r["kind"], "#ddd"), ec="#1d2733", lw=0.7))
    for a, b in raw["doors"] + raw["windows"] + ([raw["entrance"]] if raw["entrance"] else []):
        axs[0].plot([a[0], b[0]], [a[1], b[1]], color="#1d2733", lw=1.4)
    axs[0].autoscale(); axs[0].set_aspect("equal"); axs[0].axis("off")
    axs[0].set_title("as drawn (DXF: layers Estar-menjador, Dormitori, Cuina, Bany, Rebedor, Porta, Finestra, Entrada; mm)", fontsize=7.5)
    g = F.widen_doors(entry)
    g["swings"] = F.swings(g)
    items, _ = U.furnish(g)
    draw(axs[1], g, items, "read by NOMAD: squared, façade at the bottom, furnished\n" + msg)
    plt.tight_layout()
    plt.savefig(OUT / "e28_own_plan.png", dpi=130)
    plt.close(fig)
    print("figures:", [p.name for p in OUT.glob("e28_*.png")])


if __name__ == "__main__":
    main()
