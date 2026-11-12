"""Nomad Stage 6 demo numbers: the three 2D iterations on all 180 cleaned shops (same code as NOMAD.gh).
  1 as asked (typical rooms)   2 as asked, compact rooms   3 most homes (compact, patios allowed)
Asked mix: 2 x 1-bed + 1 x 2-bed. Outputs: 7_floor_plans/output/generation/iterations.csv, iterations_summary.json
Run: .venv/Scripts/python 7_floor_plans/code/run_iterations.py
"""
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "7_floor_plans/code"), str(ROOT / "6_check_the_shop/code")]
import better, flags  # noqa: E402

MIX = {"1bed": 2, "2bed": 1}


def main():
    shells = json.load(open(ROOT / "7_floor_plans/output/clean/nomad_shells.json", encoding="utf-8"))["shells"]
    progs = json.load(open(ROOT / "7_floor_plans/output/generation/room_programs.json", encoding="utf-8"))["programs"]
    rows, flags_v, homes, verdicts = [], Counter(), Counter(), {1: Counter(), 2: Counter(), 3: Counter()}
    for s in shells:
        o, f, h = s["outline"], s["facade"], s["height_m"]
        it1, before, _ = better.improve(o, f, h, MIX, progs, "typical")
        it2, _, _ = better.improve(o, f, h, MIX, progs, "compact")
        it3, _, _ = better.most_homes(o, f, h, progs, "compact")
        vb = flags.analyse(o, f, h, before)["verdict"]
        flags_v[vb] += 1
        row = {"shell_id": s["shell_id"], "shop_m2": round(flags.area(o), 1), "flags_as_it_is": vb}
        for k, p in ((1, it1), (2, it2), (3, it3)):
            v = flags.analyse(o, f, h, p)["verdict"]
            verdicts[k][v] += 1
            homes[k] += p["compliant"]
            row.update({"it%d_homes" % k: p["compliant"], "it%d_verdict" % k: v, "it%d_patios" % k: len(p.get("patios", []))})
        rows.append(row)
    out = ROOT / "7_floor_plans/output/generation"
    with open(out / "iterations.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summ = {"asked": "2 x 1-bed + 1 x 2-bed", "shops": len(shells), "stage5_flags_as_it_is": dict(flags_v),
            "iterations": {"1 as asked": {"homes": homes[1], "verdicts": dict(verdicts[1])},
                           "2 as asked, compact rooms": {"homes": homes[2], "verdicts": dict(verdicts[2])},
                           "3 most homes": {"homes": homes[3], "verdicts": dict(verdicts[3]),
                                            "shops_with_at_least_one_home": sum(1 for r in rows if r["it3_homes"] > 0)}}}
    json.dump(summ, open(out / "iterations_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(summ, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
