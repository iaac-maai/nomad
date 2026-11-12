"""Nomad Stage 6: v1 (the first generator), before (v2 with no building work: flats along the existing façades,
best placement order) vs after (smallest intervention: patios +
shared corridor + back flats, src/generate/better.py) on all 180 cleaned shops, for several unit mixes.
Outputs: results/generation/stage6_before_after.csv, results/generation/stage6_summary.json
Run: .venv/Scripts/python src/generate/run_better.py
"""
import csv, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "generate"), str(ROOT / "src" / "check")]
import better, layout  # noqa: E402

MIXES = {"1 x 1-bed": {"1bed": 1}, "2 x 1-bed + 1 x 2-bed": {"1bed": 2, "2bed": 1},
         "5 x 1-bed + 2 x 2-bed": {"1bed": 5, "2bed": 2}, "1 of each (studio, 1, 2, 3-bed)": {"studio": 1, "1bed": 1, "2bed": 1, "3bed": 1}}


def main():
    shells = json.load(open(ROOT / "data/clean/nomad_shells.json", encoding="utf-8"))["shells"]
    progs = json.load(open(ROOT / "results/generation/room_programs.json", encoding="utf-8"))["programs"]
    rows, summ, t0 = [], {}, time.time()
    for mname, mix in MIXES.items():
        v1_ok = v1_fl = b_ok = a_ok = b_fl = a_fl = with_patio = 0
        for s in shells:
            v1 = layout.generate(s["outline"], s["facade"], s["height_m"], mix, progs)      # the Stage 6 v1 generator as it was
            v1_ok += v1["proposal_ok"]
            v1_fl += v1["compliant"]
            after, before, tried = better.improve(s["outline"], s["facade"], s["height_m"], mix, progs)
            b_ok += before["proposal_ok"]
            a_ok += after["proposal_ok"]
            b_fl += before["compliant"]
            a_fl += after["compliant"]
            with_patio += bool(after.get("patios"))
            rows.append({"shell_id": s["shell_id"], "mix": mname, "area_m2": round(s.get("area_m2", 0), 1),
                         "v1_works": v1["proposal_ok"], "v1_passing_flats": v1["compliant"],
                         "before_works": before["proposal_ok"], "before_passing_flats": before["compliant"],
                         "after_works": after["proposal_ok"], "after_passing_flats": after["compliant"],
                         "patios": len(after.get("patios", [])), "patio_m2": sum(p["area"] for p in after.get("patios", [])),
                         "variants_tried": tried, "what_changed": after.get("stage6", "")})
        summ[mname] = {"shops": len(shells), "works_v1": v1_ok, "passing_flats_v1": v1_fl, "works_before": b_ok, "works_after": a_ok, "passing_flats_before": b_fl,
                       "passing_flats_after": a_fl, "shops_given_a_patio": with_patio}
        print(mname, summ[mname], "%.0fs" % (time.time() - t0), flush=True)
    out = ROOT / "results" / "generation"
    with open(out / "stage6_before_after.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summ["rules"] = {"patio": better.CITE["patio"], "corridor": better.CITE["corridor"]}
    json.dump(summ, open(out / "stage6_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
