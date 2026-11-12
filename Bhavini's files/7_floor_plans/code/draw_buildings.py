"""Nomad - lab book figures and numbers for whole buildings (7_floor_plans/code/building.py, E30).
  e30_candidates.png   warehouses, commercial and office buildings with no homes, by zoning answer and census hint
  e30_buildings.png    two empty warehouses: the whole floor vs patios cut through, with the stair + lift cores
  1_find_the_shops/output/warehouses/test_runs.csv   NOMAD on a sample of empty warehouses in zones that admit housing
Run: .venv/Scripts/python 7_floor_plans/code/draw_buildings.py [sample size]
"""
import json, random, sys, time
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as P
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ("rhino_grasshopper/code", "7_floor_plans/code", "6_check_the_shop/code")]
import nomad_core as core  # noqa: E402

COL = {"living": "#F09F26", "bed_main": "#8078DE", "bed": "#B0A8ED", "kitchen": "#FAC775", "bath": "#85B8EB", "hall": "#CCCCCC",
       "storage": "#B5B0A5"}
OUT = ROOT / "lab_book/figures"
MIX = {"1bed": 2, "2bed": 1}


def draw(ax, shell, it):
    o = shell["outline"]
    ax.add_patch(P(o, closed=True, fc="#F4F1EA", ec="#1d2733", lw=0.8))
    p = it["plan"]
    for q in p.get("patios", []):
        ax.add_patch(P(q["pts"], closed=True, fc="#C4E0F4", ec="#2C5D8F", lw=0.5))
    for c in p.get("corridors", []):
        ax.add_patch(P(c["pts"], closed=True, fc="#E4E2DC", ec="#888", lw=0.4))
    for c in p.get("cores", []):
        ax.add_patch(P(c["pts"], closed=True, fc="#7d838c", ec="#1d2733", lw=0.6))
    for u in p["units"]:
        for r in u["rooms"]:
            ax.add_patch(P(r["pts"], closed=True, fc=COL.get(r["kind"], "#ddd") if u.get("ok") else "#E34A4A", ec="#1d2733", lw=0.4))
        for x in u.get("furniture", []):
            ax.add_patch(P(x["pts"], closed=True, fc="white", ec="#1d2733", lw=0.2))
    for a, b in shell.get("street") or shell["facade"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#2C5D8F", lw=2.2)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("%s\n%d homes on %d level%s · %s" % (it["label"], it["homes"], p.get("levels", 1), "" if p.get("levels", 1) == 1 else "s",
                                                      it["res"]["verdict"]), fontsize=7.5)


def main(n=40):
    OUT.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(ROOT / "1_find_the_shops/output/warehouses/candidates.csv")
    S = json.load(open(ROOT / "1_find_the_shops/output/warehouses/shells.json"))
    # 1. candidates
    fig, axs = plt.subplots(1, 2, figsize=(12, 4))
    for ax, unused in zip(axs, (False, True)):
        d = c[c.status != "active business"] if unused else c
        t = d.groupby(["kind", "housing"]).size().unstack(fill_value=0).reindex(columns=["YES", "CHECK", "NO"], fill_value=0)
        t.plot.barh(stacked=True, ax=ax, color=["#3a9b5c", "#d9a400", "#c94c4c"], width=0.6)
        ax.set_title(("not in use (census hint)" if unused else "all") + ": buildings by what their zone allows", fontsize=9)
        ax.set_xlabel("buildings"); ax.set_ylabel("")
        for i, (k, row) in enumerate(t.iterrows()):
            ax.text(row.sum() + 10, i, "%d admitted" % row["YES"], va="center", fontsize=7)
    plt.tight_layout(); plt.savefig(OUT / "e30_candidates.png", dpi=130); plt.close(fig)
    # 2. two warehouses
    refs = ["9569407DF2896H", "9318916DF2891G"]
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    for row, ref in zip(axs, refs):
        st = core.run_building(S[ref], MIX, 6.0)
        for ax, it in zip(row, st["iterations"]):
            draw(ax, st["shop"], it)
    fig.suptitle("Empty warehouses, 6 m clear height: a mezzanine gives two levels; grey = stair + lift core; blue = patio cut through", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT / "e30_buildings.png", dpi=130); plt.close(fig)
    # 3. a sample of empty warehouses in zones that admit housing
    pool = [r for r in c[(c.kind == "warehouse") & (c.housing == "YES") & (c.status != "active business")].ref if r in S]
    random.seed(5)
    rows = []
    for ref in random.sample(pool, min(n, len(pool))):
        t = time.time()
        try:
            st = core.run_building(S[ref], MIX, 6.0)
            best = max(st["iterations"], key=lambda it: it["homes"]) if st["iterations"] else None
            rows.append({"ref": ref, "ground_m2": int(c[c.ref == ref].ground_m2.iloc[0]), "homes": best["homes"] if best else 0,
                         "layout": best["label"] if best else "", "verdict": best["res"]["verdict"] if best else "NO",
                         "patios": len(best["plan"].get("patios", [])) if best else 0, "s": round(time.time() - t, 1)})
        except Exception as e:
            rows.append({"ref": ref, "ground_m2": 0, "homes": 0, "layout": "error: %s" % e, "verdict": "", "patios": 0, "s": 0})
    d = pd.DataFrame(rows)
    d.to_csv(ROOT / "1_find_the_shops/output/warehouses/test_runs.csv", index=False)
    print(d.to_string())
    print("homes", d.homes.sum(), "buildings with homes", (d.homes > 0).sum(), "of", len(d), "patios used", (d.patios > 0).sum(),
          "errors", d.layout.str.startswith("error").sum(), "median s", d.s.median())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
