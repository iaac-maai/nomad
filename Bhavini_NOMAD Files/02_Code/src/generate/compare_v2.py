"""Nomad - old generator (layout.py + better.py) vs plan generator v2 (plan2.py), on every test shop and a sample of real
Barcelona shops, asking for 2 x 1-bed + 1 x 2-bed. Counts homes that pass every rule in each iteration, whether the flats
asked for all fit, and how much of the floor becomes homes.
Run: .venv/Scripts/python src/generate/compare_v2.py [n_real]   -> results/generation/compare_v2.csv + compare_v2.json
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/rhino", "src/generate", "src/check"):
    sys.path.insert(0, str(ROOT / p))
import nomad_core as core  # noqa: E402
import better  # noqa: E402
import plan2  # noqa: E402

MIX = {"1bed": 2, "2bed": 1}


def passing(plan):
    return sum(1 for u in plan["units"] if u["ok"])


def in_homes(plan):
    return sum(u["area_m2"] for u in plan["units"] if u["ok"]) / max(plan["shell_area_m2"], 1)


def old(shop, progs):
    o, f, h = shop["outline"], shop["facade"], shop["height"]
    it1, before, _ = better.improve(o, f, h, MIX, progs, "typical")
    it3, _, _ = better.most_homes(o, f, h, progs, "compact")
    return before, it1, it3


def main(n_real=300):
    progs = core.data()["programs"]
    shops = [("test", core.shop_from_dataset(i)) for i in range(len(core.data()["shells"]))]
    S = json.load(open(ROOT / "results/real_shops/shells.json", encoding="utf-8"))
    c = pd.read_csv(ROOT / "results/real_shops/clean_shops.csv")
    c = c[c.nomad_runs].drop_duplicates("ref14").sample(n=min(n_real, len(c)), random_state=7)
    for ref in c.ref14:
        s = S[ref]
        shops.append(("real", {"outline": s["outline"], "facade": s["facade"], "street": s["street"], "height": 2.7, "name": ref}))
    rows, t0 = [], time.time()
    for kind, sh in shops:
        o, f, h = sh["outline"], sh["facade"], sh["height"]
        ob, o1, o3 = old(sh, progs)
        nb, its, tried = plan2.iterations(o, f, h, MIX, progs, street=sh.get("street"))
        plans = dict((n, p) for n, p, _ in its)
        n3 = max([p for _, p, _ in its], key=passing)
        asked = [p for n, p in plans.items() if not p["params"].get("fill")] or [nb]
        n1 = max(asked, key=lambda p: (p["proposal_ok"], passing(p)))
        rows.append({"kind": kind, "name": sh["name"], "area": round(o1["shell_area_m2"], 1),
                     "old_asis": passing(ob), "old_asked": passing(o1), "old_asked_all": int(o1["proposal_ok"]), "old_most": passing(o3),
                     "old_homes_share": round(in_homes(o3), 3),
                     "old_patio_only": sum(1 for u in o3["units"] if u["ok"] and u.get("on_patio")),
                     "new_asis": passing(nb), "new_asked": passing(n1), "new_asked_all": int(n1["proposal_ok"]),
                     "new_most": passing(n3), "new_homes_share": round(in_homes(n3), 3),
                     "new_iterations": len(its), "new_strategies": "; ".join(plans),
                     "new_back_flats": sum(1 for u in n3["units"] if u["ok"] and u["kind"] == "back"),
                     "new_failing_flats": sum(p["placed"] - p["compliant"] for p in plans.values()),
                     "tried": tried})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results/generation/compare_v2.csv", index=False)
    summ = {}
    for kind, g in df.groupby("kind"):
        summ[kind] = {"shops": len(g),
                      "asked_all_fit": {"old": int(g.old_asked_all.sum()), "new": int(g.new_asked_all.sum())},
                      "homes_as_asked": {"old": int(g.old_asked.sum()), "new": int(g.new_asked.sum())},
                      "homes_most": {"old": int(g.old_most.sum()), "new": int(g.new_most.sum())},
                      "floor_in_homes_most": {"old": round(float(g.old_homes_share.mean()), 3), "new": round(float(g.new_homes_share.mean()), 3)},
                      "shops_with_a_home_most": {"old": int((g.old_most > 0).sum()), "new": int((g.new_most > 0).sum())},
                      "old_most_patio_only_flats": int(g.old_patio_only.sum()),
                      "new_back_flats_most": int(g.new_back_flats.sum()),
                      "new_failing_flats_shown": int(g.new_failing_flats.sum()),
                      "new_iterations_per_shop": round(float(g.new_iterations.mean()), 2),
                      "new_strategy_shown": {n: int(g.new_strategies.str.contains(n, regex=False).sum()) for n in
                                             [x[0] for x in plan2.STRATEGIES] + ["street flats only"]}}
    summ["minutes"] = round((time.time() - t0) / 60, 1)
    json.dump(summ, open(ROOT / "results/generation/compare_v2.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*[int(a) for a in sys.argv[1:2]])
