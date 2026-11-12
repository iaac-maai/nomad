"""Nomad - NOMAD (zoning + Stage 5 check + Stage 6 layouts) on Barcelona's real empty shops.

Shops: the clean shops (2_building/code/clean_real_shops.py: data errors removed) that are the only premises in their Catastro
building, stand in a zone that
admits housing (1_find_the_shops/code/zoning.py) and have at least 40 m² of ground floor (the smallest Barcelona dwelling).
Shell: 2_building/output/real_shops/shells.json (2_building/code/real_shops.py). Same code as NOMAD.gh (rhino_grasshopper/code/nomad_core.py).
For each shop: the check as it is and after the smallest change, asked 2 x 1-bed + 1 x 2-bed, and the most homes that fit.
Limit: the shell is the building's whole ground floor (the stair and the entrance of the flats above are inside it), and
the clear height is assumed (3,0 m); the Catastro CAT file would give each premises' own area.
Out: 2_building/output/real_shops/nomad_results.csv (written as it goes), summary_nomad.json, three recipes for drawings.
Run: .venv/Scripts/python 2_building/code/run_real_shops.py [limit]
"""
import csv, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ("rhino_grasshopper/code", "7_floor_plans/code", "6_check_the_shop/code")]
import pandas as pd  # noqa: E402
import nomad_core as core  # noqa: E402
import better  # noqa: E402

OUT = ROOT / "2_building/output/real_shops"
MIX = {"1bed": 2, "2bed": 1}


def shop_of(r, S):
    s = S[r.ref14]
    shop = {"ok": True, "outline": s["outline"], "facade": s["facade"], "height": s["height"], "name": "BCN_" + r.ref14,
            "source": "%s %s, %s (Catastro %s)" % (r.Nom_Via, str(r.Num_Policia_Inicial).split(".")[0], r.Nom_Barri, r.ref14),
            "image": None}
    core.add_zoning(shop, r.ref14)
    return shop


def main(limit=None):
    S = json.load(open(OUT / "shells.json", encoding="utf-8"))
    m = pd.read_csv(OUT / "clean_shops.csv")                 # cleaned first: 2_building/code/clean_real_shops.py
    c = m[m.nomad_runs].drop_duplicates("ref14")
    c = c.head(limit) if limit else c
    cols = ["ref", "address", "barri", "district", "zone", "ground_m2", "street_facade_m", "open_facade_m", "floors",
            "as_is", "as_is_passing", "after", "after_passing", "changes", "most_homes", "seconds"]
    progs = core.data()["programs"]
    t_all = time.time()
    with open(OUT / "nomad_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for k, (_, r) in enumerate(c.iterrows()):
            t = time.time()
            shop = shop_of(r, S)
            try:
                case = core.run(shop, MIX)
                mh = better.most_homes(shop["outline"], shop["facade"], shop["height"], progs, "compact")[0]
                most = sum(1 for u in mh["units"] if u.get("ok"))
                b, a = case["before"]["res"], case["after"]["res"]
                w.writerow({"ref": r.ref14, "address": "%s %s" % (r.Nom_Via, str(r.Num_Policia_Inicial).split(".")[0]),
                            "barri": r.Nom_Barri, "district": r.Nom_Districte, "zone": r.zone, "ground_m2": r.ground_m2,
                            "street_facade_m": r.street_facade_m, "open_facade_m": r.open_facade_m, "floors": r.floors,
                            "as_is": b["verdict"], "as_is_passing": b["flats_passing"], "after": a["verdict"],
                            "after_passing": a["flats_passing"], "changes": "; ".join(a.get("interventions", [])),
                            "most_homes": most, "seconds": round(time.time() - t, 1)})
            except Exception as ex:                          # one broken outline must not stop the run
                w.writerow({"ref": r.ref14, "address": "%s %s" % (r.Nom_Via, r.Num_Policia_Inicial), "as_is": "ERROR",
                            "changes": str(ex)[:120]})
            f.flush()
            if k % 50 == 0:
                print("  %d / %d  (%.0f min)" % (k + 1, len(c), (time.time() - t_all) / 60), flush=True)
    d = pd.read_csv(OUT / "nomad_results.csv")
    ok = d[d.as_is != "ERROR"]
    summ = {"shops": int(len(d)), "errors": int((d.as_is == "ERROR").sum()),
            "as_is": ok.as_is.value_counts().to_dict(), "after_smallest_change": ok.after.value_counts().to_dict(),
            "homes_as_asked_after": int(ok.after_passing.sum()), "most_homes": int(ok.most_homes.sum()),
            "shops_with_a_home": int((ok.most_homes > 0).sum()), "by_district_most_homes": ok.groupby("district").most_homes.sum().to_dict(),
            "minutes": round((time.time() - t_all) / 60, 1)}
    json.dump(summ, open(OUT / "summary_nomad.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # three real shops drawn like the demo: a YES, a PARTLY and a NO (as it is)
    for v in ("YES", "PARTLY", "NO"):
        pick = ok[ok.as_is == v].sort_values("most_homes", ascending=False).head(1)
        if len(pick):
            r = c[c.ref14 == pick.iloc[0].ref].iloc[0]
            story = core.run_story(shop_of(r, S), MIX)
            core.save_case(story, "R_%s_%s" % (v, r.ref14))
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
