"""Nomad - draw the v3 layouts (real flats, stretched) for a few shops: rooms in the E05 colours, the lobby / hall /
passage in grey, the street façade in blue, doors as white gaps, each flat's entrance as a dark tick, and what is left
for the building hatched.
Run: .venv/Scripts/python src/generate/draw_plan3.py [tag] [shop ids...]   ->   results/generation/plan3_<tag>.png
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as P

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / p) for p in ("rhino", "generate", "check")]
import nomad_core as core  # noqa: E402
import plan3  # noqa: E402

COL = {"living": "#F09F26", "bed_main": "#8078DE", "bed": "#B0A8ED", "kitchen": "#FAC775", "bath": "#85B8EB", "hall": "#CCCCCC",
       "storage": "#B5B0A5"}
SHOPS = [(146519, {"1bed": 2, "2bed": 1}), (152418, {"1bed": 5, "2bed": 2}), (154822, {"1bed": 2, "2bed": 1}), (145057, {"1bed": 2})]


def draw(ax, sh, plan, title):
    ax.add_patch(P(sh["outline"], closed=True, fc="none", ec="#999", hatch="..", lw=0.8))
    for q in plan.get("existing", []):                   # the building's own portal / stair (Catastro common parts)
        ax.add_patch(P(q, closed=True, fc="#5b5f66", ec="#1d2733", lw=0.6, hatch="////"))
    for c in plan.get("corridors", []):
        ax.add_patch(P(c["pts"], closed=True, fc="#E4E2DC", ec="#888", lw=0.6))
    for u in plan["units"]:
        ax.add_patch(P(u["outline"], closed=True, fc="white", ec="none"))
        for r in u["rooms"]:
            if len(r["pts"]) >= 3:
                ax.add_patch(P(r["pts"], closed=True, fc=COL.get(r["kind"], "#ddd") if r.get("ok", True) else "#E34A4A", ec="#1d2733", lw=0.7))
        for sw in u.get("swings", []):                       # doors: leaf + quarter arc
            ax.plot([q[0] for q in sw], [q[1] for q in sw], color="#1d2733", lw=0.45)
        for x in u.get("furniture", []):                     # furniture (src/generate/furnish.py): white, thin line
            ax.add_patch(P(x["pts"], closed=True, fc="white", ec="#1d2733", lw=0.3, alpha=0.95))
        if u.get("entrance"):
            ax.plot([u["entrance"][0]], [u["entrance"][1]], marker="D", ms=4, color="#1d2733")
        cx = sum(p[0] for p in u["outline"]) / len(u["outline"])
        cy = sum(p[1] for p in u["outline"]) / len(u["outline"])
        ax.text(cx, cy, u["type"], fontsize=6, ha="center", va="center", color="#1d2733", weight="bold")
    for a, b in sh["facade"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#2C5D8F", lw=2.2)
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title, fontsize=7)


def shop(sid):
    """A Swiss test shop by its id, or a real Barcelona shop by its cadastral reference (results/real_shops/shells.json)."""
    if str(sid).isdigit():
        return core.shop_by_id(int(sid))
    import json
    s = json.load(open(ROOT / "results" / "real_shops" / "shells.json", encoding="utf-8"))[sid]
    return {"outline": s["outline"], "facade": s["facade"], "street": s["street"], "height": s["height"], "name": "BCN_" + sid,
            "existing": s.get("existing")}


def main(tag="v3", ids=None):
    shops = [(i, {"1bed": 2, "2bed": 1}) for i in ids] if ids else SHOPS
    fig, axes = plt.subplots(len(shops), 3, figsize=(15, 4.6 * len(shops)))
    for row, (sid, mix) in zip(axes if len(shops) > 1 else [axes], shops):
        sh = shop(sid)
        before, its, _ = plan3.iterations(sh["outline"], sh["facade"], sh["height"], mix, street=sh.get("street"), existing=sh.get("existing"))
        panels = [("as it is", before)] + [(n, p) for n, p, _ in its]
        for ax, (n, p) in zip(row, panels[:3]):
            draw(ax, sh, p, "%s | %s: %d homes, %d pass, %.0f m² for the building" % (sh["name"], n, p["placed"], p["compliant"], p["unused_m2"]))
        for ax in row[len(panels):]:
            ax.axis("off")
    out = ROOT / "results" / "generation" / ("plan3_%s.png" % tag)
    fig.tight_layout(); fig.savefig(out, dpi=110); print(out)


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["v3"]), ids=sys.argv[2:] or None)
