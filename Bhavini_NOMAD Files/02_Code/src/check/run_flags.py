"""Nomad Stage 5: run the flags (src/check/flags.py, the same code NOMAD.gh uses) on all 180 cleaned shops.

For each unit mix: the verdict (YES / PARTLY / NO), how often each rule card fails, and the daylight bands.
Outputs: results/flags/verdicts.csv (one row per shop and mix), results/flags/summary.json
Run: .venv/Scripts/python src/check/run_flags.py
"""
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "generate"), str(ROOT / "src" / "check")]
import layout, flags  # noqa: E402

MIXES = {"1 x 1-bed": {"1bed": 1}, "2 x 1-bed + 1 x 2-bed": {"1bed": 2, "2bed": 1}, "5 x 1-bed + 2 x 2-bed": {"1bed": 5, "2bed": 2}}


def main():
    shells = json.load(open(ROOT / "data/clean/nomad_shells.json", encoding="utf-8"))["shells"]
    progs = json.load(open(ROOT / "results/generation/room_programs.json", encoding="utf-8"))["programs"]
    out = ROOT / "results" / "flags"
    out.mkdir(parents=True, exist_ok=True)
    rows, summ = [], {}
    for mname, mix in MIXES.items():
        verdicts, fails = Counter(), Counter()
        for s in shells:
            plan = layout.generate(s["outline"], s["facade"], s["height_m"], mix, progs)
            r = flags.analyse(s["outline"], s["facade"], s["height_m"], plan)
            verdicts[r["verdict"]] += 1
            for c in r["cards"]:
                if not c["ok"]:
                    fails[c["title"]] += 1
            d = r["daylight"]
            rows.append({"shell_id": s["shell_id"], "mix": mname, "verdict": r["verdict"], "flats_asked": r["flats_asked"],
                         "flats_passing": r["flats_passing"], "shop_m2": r["shop_m2"], "lit_share": d["share"]["lit"],
                         "service_share": d["share"]["service"], "dark_share": d["share"]["dark"], "max_depth_m": d["max_depth"],
                         "failed_cards": "; ".join(c["title"] for c in r["cards"] if not c["ok"])})
        summ[mname] = {"shops": len(shells), "verdicts": dict(verdicts), "cards_failed": dict(fails.most_common())}
    dark = sorted(r["dark_share"] for r in rows if r["mix"] == "1 x 1-bed")
    summ["daylight"] = {"shops_with_over_20pct_dark": sum(1 for x in dark if x > 0.2), "median_dark_share": dark[len(dark) // 2],
                        "note": "lit = within 5,5 m of a façade with windows (design assumption, not a law)"}
    with open(out / "verdicts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump(summ, open(out / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(summ, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
