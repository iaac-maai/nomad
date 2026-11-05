"""Nomad - lab book figures for E33 (NOMAD's plan AI): training curve, AI plans furnished and checked, a shop with AI flats.
Run: .venv/Scripts/python src/ai/draw_ai.py   ->   book/figures/e33_*.png
"""
import csv, json, random, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / p) for p in ("generate", "rhino", "check")]
import furnish as U  # noqa: E402
import library_fit as F  # noqa: E402
import draw_furniture as DF  # noqa: E402
import draw_plan3  # noqa: E402

OUT = ROOT / "book" / "figures"


def curve():
    rows = list(csv.DictReader(open(ROOT / "results" / "ai" / "train_log.csv")))
    ep = [int(r["epoch"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(ep, [float(r["pixel_acc"]) for r in rows], color="#2C5D8F", label="pixels right (flats never seen)")
    ax.plot(ep, [float(r["mIoU"]) for r in rows], color="#C98A2B", label="room overlap, mIoU (flats never seen)")
    ax.set_xlabel("epoch (one pass over 28,434 training flats)"); ax.set_ylim(0, 1); ax.legend(fontsize=8); ax.grid(alpha=0.3)
    ax.set_title("NOMAD's plan AI learning to fill a flat with rooms", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT / "e33_training.png", dpi=130); plt.close(fig)


def samples():
    L = json.load(open(ROOT / "results" / "library" / "library_ai.json"))
    random.seed(4)
    picks = []
    for beds, lit in ((0, ["front"]), (1, ["front"]), (1, ["front", "back"]), (2, ["front"]), (2, ["front", "back"]), (3, ["front", "back"])):
        pool = [f for f in L if f["bedrooms"] == beds and f["lit"] == lit and f["useful"] >= 40]
        if pool:
            picks.append(random.choice(pool))
    fig, axs = plt.subplots(2, 3, figsize=(13, 8.2))
    for ax, f in zip(axs.flat, picks):
        g = F.widen_doors(f)
        g["swings"] = F.swings(g)
        items, _ = U.furnish(g)
        DF.draw(ax, g, items, "NOMAD AI · %d bed · %s · %.0f m²" % (f["bedrooms"], " + ".join(f["lit"]), f["useful"]))
    for ax in list(axs.flat)[len(picks):]:
        ax.axis("off")
    fig.suptitle("Plans drawn by NOMAD's plan AI for a given rectangle, façade and entrance; each passes every NOMAD check and is furnished", fontsize=9)
    plt.tight_layout(rect=(0, 0, 1, 0.96)); plt.savefig(OUT / "e33_ai_plans.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    curve()
    samples()
    print("ok")
