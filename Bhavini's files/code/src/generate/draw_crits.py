"""Nomad - lab book figures for E32 (the 29 Oct crits): AMB, daylight zones and real lit depth, shared-space homes.
Run: .venv/Scripts/python src/generate/draw_crits.py   ->   book/figures/e32_*.png
"""
import csv, json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as P, Rectangle

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / p) for p in ("rhino", "generate", "check")]
import nomad_core as core  # noqa: E402

OUT = ROOT / "book" / "figures"
COL = {"living": "#F09F26", "bed_main": "#8078DE", "bed": "#B0A8ED", "kitchen": "#FAC775", "bath": "#85B8EB", "hall": "#CCCCCC", "storage": "#B5B0A5"}
BAND = {"lit": "#FFE7A3", "service": "#EEF0EC", "dark": "#AEBBCB"}


def amb():
    A = json.load(open(ROOT / "site" / "data" / "amb.json", encoding="utf-8"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1.1, 1]})
    for h, c in (("C", "#d9a400"), ("Y", "#3a9b5c")):
        pts = [p for p in A["pts"] if p[3] == h]
        a1.scatter([p[0] for p in pts], [p[1] for p in pts], s=1.5, c=c, label={"Y": "zone admits housing", "C": "the zone's plan decides"}[h])
    a1.set_aspect("equal"); a1.axis("off"); a1.legend(loc="lower right", fontsize=8, markerscale=6)
    a1.set_title("Warehouses, commercial and office buildings with no homes, AMB (36 towns)", fontsize=9)
    T = sorted(A["towns"], key=lambda t: t["zone_yes"] + t["zone_check"])[-18:]
    a2.barh([t["town"] for t in T], [t["zone_yes"] for t in T], color="#3a9b5c", label="zone admits housing")
    a2.barh([t["town"] for t in T], [t["zone_check"] for t in T], left=[t["zone_yes"] for t in T], color="#d9a400", label="plan decides")
    a2.tick_params(labelsize=7); a2.legend(fontsize=8); a2.set_title("The 18 towns with most of them", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT / "e32_amb.png", dpi=130); plt.close(fig)


def daylight_and_shared():
    sh = core.shop_by_id(152418)
    fig, axs = plt.subplots(1, 3, figsize=(15, 6))
    base = dict(sh, street=sh["facade"])
    st = core.run_story(dict(base, lit_depth=3.0), {"1bed": 2, "2bed": 1})
    d = st["before"]["res"]["daylight"]
    ax = axs[0]
    for c in d["cells"]:
        ax.add_patch(Rectangle((c[0], c[1]), c[2] - c[0], c[3] - c[1], fc=BAND[c[5]], ec="none"))
    ax.add_patch(P(sh["outline"], closed=True, fill=False, ec="#1d2733", lw=0.8))
    ax.set_title("Where light reaches (lit depth 3,0 m): yellow lit, grey service, blue dark", fontsize=8)
    for ax, (label, it) in zip(axs[1:], (("full flats, lit depth 3,0 m", max(st["iterations"], key=lambda i: i["homes"])),
                                          ("shared-space homes", max(core.run_story(dict(base, scheme="shared"), {"1bed": 2})["iterations"], key=lambda i: i["homes"])))):
        ax.add_patch(P(sh["outline"], closed=True, fc="#F4F1EA", ec="#1d2733", lw=0.8))
        for c in it["plan"].get("corridors", []):
            ax.add_patch(P(c["pts"], closed=True, fc="#E4E2DC", ec="#888", lw=0.4))
        for u in it["plan"]["units"]:
            for r in u["rooms"]:
                fc = "#E34A4A" if not (u.get("ok") and r.get("ok", True)) else ("#9ED3A6" if u.get("shared") else COL.get(r["kind"], "#ddd"))
                ax.add_patch(P(r["pts"], closed=True, fc=fc, ec="#1d2733", lw=0.4))
        ax.set_title("%s: %d homes · %s (red = a room too dark or another rule)" % (label, it["homes"], it["res"]["verdict"]), fontsize=8)
    for ax in axs:
        ax.autoscale(); ax.set_aspect("equal"); ax.axis("off")
    fig.suptitle("The large demo shop: daylight decides where homes can go; green = shared living rooms and kitchens", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT / "e32_daylight_shared.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    amb()
    daylight_and_shared()
    print("ok")
