"""Nomad - the habitability rules learned from the 13,444 real flats (7_floor_plans/code/habitability.py), as numbers and charts.

For each question an architect asks of a plan, the answer the real flats give (median and the 10-90 % range):
  how much floor goes to living, sleeping, cooking, washing, moving, storing   (shares, by flat type)
  how much is circulation, and how wide is it                                   (corridor share, clear width)
  where the front door opens, and from where                                     (entrance room, outside side; ground floor apart)
  what each room is reached from; which rooms people walk through                (room graph)
  which rooms have windows, how much window per m², how deep from the window      (light)
  how wide and how rectangular each room is                                       (shape)
  open or closed kitchen; kitchen and bath on one wet wall                        (services)
Out: 7_floor_plans/output/habitability/summary.json + lab_book/figures/e24_*.png
Run: .venv/Scripts/python 7_floor_plans/code/habitability_summary.py
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "7_floor_plans/output/habitability"
FIG = ROOT / "lab_book/figures"
BLUE, OCHRE, GREEN, RED = "#2C5D8F", "#C98A2B", "#3F8F5A", "#C4473A"               # lab book E01
ROOM = {"living": "#F09F26", "bedroom": "#8078DE", "kitchen": "#FAC775", "bath": "#85B8EB", "circulation": "#CCCCCC",
        "storage": "#B5B0A5"}                                                       # lab book E05
NAMES = {0: "studio", 1: "1-bed", 2: "2-bed", 3: "3-bed"}


def q(s, p):
    s = s.dropna()
    return round(float(s.quantile(p)), 2) if len(s) else None


def rng(s):
    return {"p10": q(s, 0.1), "median": q(s, 0.5), "p90": q(s, 0.9)}


def main():
    u = pd.read_csv(D / "units.csv")
    r = pd.read_csv(D / "rooms.csv")
    u["type"] = u.bedrooms.map(NAMES)
    S = {"flats": int(len(u)), "rooms": int(len(r)), "ground_floor_flats": int(u.ground_floor.sum())}
    # 1 space
    sh = ["share_living", "share_bedroom", "share_kitchen", "share_bath", "share_circulation", "share_storage"]
    S["space_by_type"] = {t: {"flats": int(len(g)), "useful_m2": rng(g.useful_m2), **{c[6:]: q(g[c], 0.5) for c in sh}}
                          for t, g in u.groupby("type")}
    S["circulation"] = {"share": rng(u.share_circulation), "corridor_m2": rng(u.corridor_m2),
                        "clear_width_m": rng(u.corridor_width_m), "flats_without_corridor": round(float(u.corridor_m2.eq(0).mean()), 3),
                        "tiny_leftover_rooms_per_flat": round(float(u.tiny_rooms.mean()), 3)}
    # 2 entrance
    S["entrance"] = {"opens_into": u.entrance_into.value_counts(normalize=True).round(3).head(6).to_dict(),
                     "from_all": u.entrance_from.value_counts(normalize=True).round(3).head(6).to_dict(),
                     "from_ground_floor": u[u.ground_floor].entrance_from.value_counts(normalize=True).round(3).head(6).to_dict(),
                     "into_ground_floor": u[u.ground_floor].entrance_into.value_counts(normalize=True).round(3).head(6).to_dict()}
    # 3 room graph
    S["reached_from"] = {k: g.reached_from.value_counts(normalize=True).round(3).head(5).to_dict()
                         for k, g in r[r.kind.isin(["living", "bedroom", "kitchen", "bath"])].groupby("kind")}
    S["walk_through"] = {"flats_with_a_room_walked_through": round(float((u.rooms_walked_through > 0).mean()), 3),
                         "bedrooms_reached_through_living": round(float(u.bedrooms_via_living.sum() / max(u.bedrooms.sum(), 1)), 3),
                         "baths_reached_through_a_bedroom": round(float(u.baths_via_bedroom.sum() / max(len(r[r.kind == "bath"]), 1)), 3)}
    # 4 light
    r["win_per_m2"] = r.window_m / r.area_m2
    S["light"] = {k: {"with_window": round(float((g.window_m > 0).mean()), 3), "on_facade": round(float(g.on_facade.mean()), 3),
                      "window_m": rng(g[g.window_m > 0].window_m), "window_m_per_m2": rng(g[g.window_m > 0].win_per_m2)}
                  for k, g in r[r.kind.isin(["living", "bedroom", "kitchen", "bath", "circulation", "storage"])].groupby("kind")}
    S["depth_from_window_m"] = rng(u.depth_from_window_m)
    # 5 shape
    S["shape"] = {k: {"area_m2": rng(g.area_m2), "clear_width_m": rng(g.clear_width_m), "short_side_m": rng(g.width_m),
                      "long_over_short": rng(g.length_m / g.width_m), "rect_fill": rng(g.rect_fill)}
                  for k, g in r[r.kind.isin(["living", "bedroom", "kitchen", "bath", "circulation", "storage"])].groupby("kind")}
    # 6 services
    S["services"] = {"open_kitchen": round(float(u.open_kitchen.mean()), 3), "kitchen_as_room": round(float(u.kitchen_room.mean()), 3),
                     "kitchen_and_bath_share_a_wall": round(float(u.wet_core.mean()), 3), "doors_per_flat": rng(u.doors),
                     "door_width_m": rng(u.door_width_m)}
    json.dump(S, open(D / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    # ---- figures
    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    types = [t for t in ("studio", "1-bed", "2-bed", "3-bed") if t in S["space_by_type"]]
    left = [0] * len(types)
    for c in sh:
        k = c[6:]
        v = [S["space_by_type"][t][k] or 0 for t in types]
        ax.barh(types, v, left=left, color=ROOM[k], label=k)
        left = [a + b for a, b in zip(left, v)]
    ax.set_xlim(0, 1); ax.set_xlabel("share of the useful floor (median)"); ax.legend(ncol=6, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.25), frameon=False)
    for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "e24_space.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    ks = ["living", "bedroom", "kitchen", "bath", "storage", "circulation"]
    ks = [k for k in ks if k in S["shape"]]
    for x, k in enumerate(ks):
        g = r[r.kind == k].clear_width_m.dropna()
        ax.boxplot(g, positions=[x], widths=0.5, showfliers=False, patch_artist=True, boxprops=dict(facecolor=ROOM[k]), medianprops=dict(color="#1d2733"))
    ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks); ax.set_ylabel("clear width (m)")
    for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "e24_widths.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    rf = r[r.kind.isin(["living", "bedroom", "kitchen", "bath"])]
    tab = pd.crosstab(rf.kind, rf.reached_from, normalize="index")
    cols = [c for c in ("circulation", "living", "entrance", "bedroom", "kitchen", "bath") if c in tab.columns]
    left = [0] * len(tab)
    for c in cols:
        ax.barh(tab.index, tab[c], left=left, color=ROOM.get(c, "#888888"), label="from " + c)
        left = [a + b for a, b in zip(left, tab[c])]
    ax.set_xlim(0, 1); ax.set_xlabel("share of rooms"); ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.3), frameon=False)
    for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / "e24_reached.png", dpi=130); plt.close(fig)
    print(json.dumps(S, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
