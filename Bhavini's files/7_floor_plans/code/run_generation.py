"""Nomad - run the floor-plan generator on every clean shop shell and score the proposals.

For each of the clean shells (7_floor_plans/output/clean/nomad_shells.json) we ask for several unit mixes:
  fixed mixes  - the same request everywhere (e.g. 2 x 1-bed + 1 x 2-bed)
  best fit     - as many flats as the Barcelona density rule allows (built / 80 m²), trying the
                 mix of 1-bed and 2-bed that places the most flats that pass every rule
each at "typical" and "compact" room sizes. A proposal "works" when every flat asked for is
placed and passes every rule, and the total is within the density limit.
Outputs (7_floor_plans/output/generation/): proposals.csv (one row per shell x mix x size), summary.json,
sample_plans.json (plans for the Grasshopper viewer)
"""
import json, os, sys, collections
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import layout  # noqa: E402

OUT = "7_floor_plans/output/generation"
MIXES = {
    "1 x studio": {"studio": 1},
    "1 x 1-bed": {"1bed": 1},
    "2 x 1-bed + 1 x 2-bed": {"1bed": 2, "2bed": 1},
    "1 of each (studio, 1, 2, 3-bed)": {"studio": 1, "1bed": 1, "2bed": 1, "3bed": 1},
    "5 x 1-bed + 2 x 2-bed": {"1bed": 5, "2bed": 2},
}


def best_fit(shell, programs, size):
    """Most compliant flats up to the density cap, trying mixes of 1-bed and 2-bed."""
    cap = layout.generate(shell["outline"], shell["facade"], shell["height_m"], {}, programs, size)["density_cap"]

    def attempt(n):
        for n2 in sorted(set([n // 3, 0, n // 2])):          # a few 1-bed / 2-bed splits, not all
            mix = {"1bed": n - n2, "2bed": n2}
            plan = layout.generate(shell["outline"], shell["facade"], shell["height_m"], mix, programs, size)
            if plan["proposal_ok"]:
                return mix, plan
        return None

    # how many 1-beds fit at all gives an upper bound; then search down from there
    probe = layout.generate(shell["outline"], shell["facade"], shell["height_m"], {"1bed": cap}, programs, size)
    top = min(cap, max(probe["compliant"], 1))
    for n in range(top, 0, -1):
        got = attempt(n)
        if got:
            return got
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    shells = json.load(open("7_floor_plans/output/clean/nomad_shells.json", encoding="utf-8"))["shells"]
    programs = json.load(open(f"{OUT}/room_programs.json", encoding="utf-8"))["programs"]
    rows, samples = [], []
    for i, s in enumerate(shells):
        for size in ("typical", "compact"):
            for name, mix in MIXES.items():
                p = layout.generate(s["outline"], s["facade"], s["height_m"], mix, programs, size)
                fails = collections.Counter(f for u in p["units"] for f in u["fails"])
                rows.append({"shell_id": s["shell_id"], "area_m2": s["area_m2"], "facade_m": s["facade_m"], "size": size,
                             "mix": name, "requested": p["requested"], "placed": p["placed"], "compliant": p["compliant"],
                             "works": p["proposal_ok"], "density_cap": p["density_cap"], "unused_m2": p["unused_m2"],
                             "not_placed": len(p["unplaced"]), "fails": ";".join(sorted(fails))})
            bf = best_fit(s, programs, size)
            rows.append({"shell_id": s["shell_id"], "area_m2": s["area_m2"], "facade_m": s["facade_m"], "size": size,
                         "mix": "best fit (max flats)", "requested": bf[1]["requested"] if bf else 0,
                         "placed": bf[1]["placed"] if bf else 0, "compliant": bf[1]["compliant"] if bf else 0,
                         "works": bool(bf), "density_cap": bf[1]["density_cap"] if bf else None,
                         "unused_m2": bf[1]["unused_m2"] if bf else s["area_m2"], "not_placed": 0,
                         "fails": "" if bf else "nothing fits", "best_mix": json.dumps(bf[0]) if bf else ""})
            if size == "typical" and bf and len(samples) < 120:
                samples.append({"shell": s, "mix": bf[0], "plan": bf[1]})
        if i % 30 == 0:
            print(f"  shells {i + 1}/{len(shells)}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/proposals.csv", index=False)
    summ = {"shells": len(shells), "by_mix": {}}
    for (mix, size), g in df.groupby(["mix", "size"]):
        fails = collections.Counter(f for x in g.fails.dropna() for f in x.split(";") if f)
        summ["by_mix"].setdefault(mix, {})[size] = {
            "proposals_that_work": int(g.works.sum()), "share": round(float(g.works.mean()), 3),
            "flats_placed": int(g.placed.sum()), "flats_passing": int(g.compliant.sum()),
            "top_fail_reasons": dict(fails.most_common(4)),
            "shells_short_of_facade_or_depth": int((g.not_placed > 0).sum()),
        }
    bf = df[(df.mix == "best fit (max flats)") & (df["size"] == "typical")]
    summ["best_fit_typical"] = {"shells_with_a_proposal": int(bf.works.sum()), "flats_total": int(bf.compliant.sum()),
                                "median_flats_per_shell": float(bf[bf.works].compliant.median()) if bf.works.any() else 0}
    json.dump(summ, open(f"{OUT}/summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"programs": programs, "samples": samples}, open(f"{OUT}/sample_plans.json", "w", encoding="utf-8"))
    print(json.dumps(summ, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
