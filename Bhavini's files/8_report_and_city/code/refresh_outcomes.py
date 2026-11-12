"""Nomad - rebuild the results page's data files from our outcomes (results/, docs/, lab_book/).

Run after every experiment, then upload the changed CSVs to the NOMAD Results page:
  .venv/Scripts/python 8_report_and_city/code/refresh_outcomes.py
Writes 8_report_and_city/output/dashboard/dashboard_data/:
  headline.csv (adds plan-reader numbers), generation.csv, plan_reading.csv, github_repos.csv, experiments.csv
stages.csv, rule_results.csv, by_bedrooms.csv, rulebook_norms.csv and resources.csv are kept as they are
(they change only when a stage or a rule test is re-run, by the scripts that made them).
"""
import csv, glob, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASH = ROOT / "8_report_and_city/output/dashboard/dashboard_data"
WALLS = {"f3d": "floorplan-to-3d + dark lines (in NOMAD)", "f3d_only": "floorplan-to-3d model alone",
         "mitunet": "MitUNet walls + dark lines", "dark": "Dark lines alone (no AI)"}


def write(name, rows, cols):
    with open(DASH / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")


def headline():
    path = DASH / "headline.csv"
    old = {r["metric"]: r["value"] for r in csv.DictReader(open(path, encoding="utf-8"))}
    ev = json.load(open(ROOT / "2_building/output/plan_reading/eval_summary.json"))["scale given"]
    gen = json.load(open(ROOT / "7_floor_plans/output/generation/summary.json"))["by_mix"]["best fit (max flats)"]["typical"]
    old.update(reader_plans=ev["plans"], reader_iou=ev["median_iou"], reader_area_within_10pct=ev["area_within_10pct"],
               shops_with_proposal=gen["proposals_that_work"], flats_generated=gen["flats_placed"],
               experiments=len(json.load(open(ROOT / "lab_book/experiments.json", encoding="utf-8"))["experiments"]),
               repos_checked=sum(1 for _ in csv.DictReader(open(ROOT / "docs/github_repos.csv", encoding="utf-8"))))
    write("headline.csv", [{"metric": k, "value": v} for k, v in old.items()], ["metric", "value"])


def plan_reading():
    rows = []
    for f in sorted(glob.glob(str(ROOT / "2_building/output/plan_reading/compare/*.json"))):
        plans, walls = Path(f).stem.split("__")
        d = json.load(open(f))["scale given"]
        rows.append({"case": f"{walls} | {plans}", "reader": WALLS.get(walls, walls),
                     "plans": "messy (text, dimensions, scan noise)" if "messy" in plans else "clean",
                     "plans_tested": d["plans"], "median_outline_overlap": d["median_iou"],
                     "area_within_10pct": d["area_within_10pct"], "median_facade_error": d["median_facade_error"]})
    write("plan_reading.csv", rows, ["case", "reader", "plans", "plans_tested", "median_outline_overlap", "area_within_10pct", "median_facade_error"])


def repos():
    r = list(csv.DictReader(open(ROOT / "docs/github_repos.csv", encoding="utf-8")))
    write("github_repos.csv", r, list(r[0].keys()))


def experiments():
    sys_path = str(ROOT / "lab_book/code")
    import sys
    sys.path.insert(0, sys_path)
    import build_book
    m = build_book.metrics()
    ex = json.load(open(ROOT / "lab_book/experiments.json", encoding="utf-8"))["experiments"]
    fill = lambda t: re.sub(r"\{([a-z0-9_]+)\}", lambda g: m.get(g.group(1), g.group(0)), t)
    rows = [{"id": e["id"], "date": e["date"], "stage": e["stage"], "experiment": e["title"],
             "result": fill(e["result"]), "decision": fill(e["decision"]), "figures": len(e["figures"])} for e in ex]
    write("experiments.csv", rows, ["id", "date", "stage", "experiment", "result", "decision", "figures"])


def flags_summary():
    f = ROOT / "6_check_the_shop/output/summary.json"
    if not f.exists():
        return
    s5 = json.load(open(f, encoding="utf-8"))
    rows = []
    for mix, v in s5.items():
        if mix == "daylight":
            continue
        cf = v["cards_failed"]
        rows.append({"mix": mix, "shops": v["shops"], "yes": v["verdicts"].get("YES", 0), "partly": v["verdicts"].get("PARTLY", 0),
                     "no": v["verdicts"].get("NO", 0), "card_failed_most": ", ".join("%s (%d)" % (k, n) for k, n in list(cf.items())[:3])})
    write("flags.csv", rows, ["mix", "shops", "yes", "partly", "no", "card_failed_most"])


def stage6():
    f = ROOT / "7_floor_plans/output/generation/stage6_summary.json"
    if not f.exists():
        return
    s6 = json.load(open(f, encoding="utf-8"))
    rows = [{"mix": k, "shops": v["shops"], "works_first_generator": v["works_v1"], "works_stage6": v["works_after"],
             "passing_flats_first_generator": v["passing_flats_v1"], "passing_flats_stage6": v["passing_flats_after"],
             "shops_given_a_patio": v["shops_given_a_patio"]} for k, v in s6.items() if k != "rules"]
    write("stage6.csv", rows, list(rows[0]))


def iterations():
    """Old generator (patio iterations) vs plan2 circulation strategies, from 7_floor_plans/code/compare_v2.py (lab book E23)."""
    f = ROOT / "7_floor_plans/output/generation/compare_v2.json"
    if not f.exists():
        return
    c = json.load(open(f, encoding="utf-8"))
    rows = []
    for key, name in (("real", "Barcelona empty shops"), ("test", "test shops")):
        s = c[key]
        for gen, label in (("old", "old: patio iterations"), ("new", "new: circulation strategies")):
            rows.append({"iteration": "%s (%d) | %s" % (name, s["shops"], label), "homes": s["homes_most"][gen],
                         "homes_as_asked": s["homes_as_asked"][gen], "asked_all_fit": s["asked_all_fit"][gen],
                         "floor_in_homes": s["floor_in_homes_most"][gen],
                         "patio_only_flats": s["old_most_patio_only_flats"] if gen == "old" else 0})
    write("iterations.csv", rows, ["iteration", "homes", "homes_as_asked", "asked_all_fit", "floor_in_homes", "patio_only_flats"])


def generation():
    s = json.load(open(ROOT / "7_floor_plans/output/generation/summary.json"))["by_mix"]
    old = {r["case"]: r for r in csv.DictReader(open(DASH / "generation.csv", encoding="utf-8"))}
    rows = []
    for mix, by in s.items():
        for size, d in by.items():
            case = f"{mix} | {size}"
            fails = ", ".join(f"{k} ({v})" for k, v in d.get("top_fail_reasons", {}).items())
            rows.append({"case": case, "mix": mix, "room_sizes": size, "shops_where_it_works": d["proposals_that_work"],
                         "share_of_180_shops": d["share"], "flats_placed": d["flats_placed"], "flats_passing_all_rules": d["flats_passing"],
                         "shops_out_of_space": d["shells_short_of_facade_or_depth"], "rules_failed_most": fails or old.get(case, {}).get("rules_failed_most", "")})
    write("generation.csv", rows, ["case", "mix", "room_sizes", "shops_where_it_works", "share_of_180_shops", "flats_placed",
                                   "flats_passing_all_rules", "shops_out_of_space", "rules_failed_most"])


if __name__ == "__main__":
    for f in (headline, plan_reading, repos, experiments, generation, flags_summary, stage6, iterations):
        f()
