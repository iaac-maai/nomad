"""Nomad - homes for the whole city, for the policy-maker view: every candidate shop and whole building run through NOMAD.

Shops: every clean shell (results/real_shops/clean_shops.csv nomad_runs) of an empty premises in a zone that admits housing or whose plan
decides, with Bars's predicted lit depth when there is one (site/data/premises.json "lit"). Buildings: the warehouses,
commercial and office buildings with no homes and no active business on the census hint (src/zoning/warehouses.py), in a
zone that admits housing or whose plan decides; warehouses at 6 m clear height (mezzanine), others at their Catastro storeys.
Homes = the most legal homes over NOMAD's layouts (the asked mix 2 x 1-bed + 1 x 2-bed and "most homes").
Out: results/city/homes.csv (written as it goes), site/data/city_homes.json
Run: .venv/Scripts/python src/check/city_runs.py [workers]
"""
import csv, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / p) for p in ("rhino", "generate", "check")]
OUT = ROOT / "results" / "city"
MIX = {"1bed": 2, "2bed": 1}
WH_CLEAR = 6.0


def _shop(job):
    import plan3
    ref, s, lit = job
    t = time.time()
    try:
        _, its, _ = plan3.iterations(s["outline"], s["facade"], s["height"], MIX, street=s["street"], existing=s.get("existing"),
                                     lit_depth=lit or 5.5, lit_source="bars" if lit else None)
        best = max(its, key=lambda x: x[1]["compliant"]) if its else None
        return {"ref": ref, "kind": "shop", "homes": best[1]["compliant"] if best else 0, "layout": best[0] if best else "",
                "levels": 1, "lit": lit or "", "s": round(time.time() - t, 1)}
    except Exception as e:
        return {"ref": ref, "kind": "shop", "homes": 0, "layout": "error: %s" % str(e)[:80], "levels": 1, "lit": lit or "", "s": 0}


def _building(job):
    import nomad_core as core
    ref, s = job
    t = time.time()
    try:
        st = core.run_building(s, MIX, WH_CLEAR if s["kind"] == "warehouse" else 3.0)
        best = max(st["iterations"], key=lambda it: it["homes"]) if st["iterations"] else None
        return {"ref": ref, "kind": s["kind"], "homes": best["homes"] if best else 0, "layout": best["label"] if best else "",
                "levels": best["plan"].get("levels", 1) if best else 1, "lit": "", "s": round(time.time() - t, 1)}
    except Exception as e:
        return {"ref": ref, "kind": s["kind"], "homes": 0, "layout": "error: %s" % str(e)[:80], "levels": 1, "lit": "", "s": 0}


def main(workers=4):
    OUT.mkdir(parents=True, exist_ok=True)
    P = json.load(open(ROOT / "site" / "data" / "premises.json", encoding="utf-8"))
    ci = P["cols"].index
    lit, ok, seen = {}, set(), set()
    for r in P["rows"]:
        ref = (r[ci("ref")] or "")[:14]
        if r[ci("lit")] is not None:
            lit[ref] = r[ci("lit")]
        if r[ci("housing")] in ("YES", "CHECK"):
            ok.add(ref)
    for k, v in json.load(open(ROOT / "site" / "data" / "daylight.json", encoding="utf-8"))["shops"].items():
        lit[k[:14]] = max(lit.get(k[:14]) if k[:14] in seen else 0, max(q[2] for q in v)); seen.add(k[:14])   # Bars's new model (Exp 4) replaces the old lit depth
    S = json.load(open(ROOT / "results" / "real_shops" / "shells.json", encoding="utf-8"))
    clean = set(r["ref14"] for r in csv.DictReader(open(ROOT / "results" / "real_shops" / "clean_shops.csv", encoding="utf-8"))
                if r.get("nomad_runs") == "True")             # the clean shells NOMAD runs on (src/building/clean_real_shops.py)
    shops = [(r, S[r], lit.get(r)) for r in sorted(ok) if r in S and r in clean]
    W = json.load(open(ROOT / "results" / "warehouses" / "shells.json", encoding="utf-8"))
    blds = [(r, s) for r, s in sorted(W.items()) if s["status"] != "active business"]
    done = set()
    path = OUT / "homes.csv"
    if path.exists():
        done = set(r["ref"] + r["kind"] for r in csv.DictReader(open(path, encoding="utf-8")))
    shops = [j for j in shops if j[0] + "shop" not in done]
    blds = [j for j in blds if j[0] + j[1]["kind"] not in done]
    print("to run: %d shops, %d buildings" % (len(shops), len(blds)), flush=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f, Pool(workers) as pool:
        w = csv.DictWriter(f, fieldnames=["ref", "kind", "homes", "layout", "levels", "lit", "s"])
        if new:
            w.writeheader()
        n = 0
        for res in pool.imap_unordered(_shop, shops, chunksize=4):
            w.writerow(res); f.flush(); n += 1
            if n % 100 == 0:
                print("shops", n, flush=True)
        for res in pool.imap_unordered(_building, blds, chunksize=2):
            w.writerow(res); f.flush(); n += 1
            if n % 100 == 0:
                print("all", n, flush=True)
    export()


def export():
    """site/data/city_homes.json: {ref|kind: [homes, levels]} for the policy-maker view."""
    clean = set(r["ref14"] for r in csv.DictReader(open(ROOT / "results" / "real_shops" / "clean_shops.csv", encoding="utf-8"))
                if r.get("nomad_runs") == "True")
    rows = [r for r in csv.DictReader(open(OUT / "homes.csv", encoding="utf-8")) if r["kind"] != "shop" or r["ref"] in clean]
    out = {}
    for r in rows:
        out[r["ref"] + "|" + r["kind"]] = [int(r["homes"]), int(r["levels"] or 1)]
    json.dump(out, open(ROOT / "site" / "data" / "city_homes.json", "w"), separators=(",", ":"))
    tot = {}
    for r in rows:
        k = r["kind"]
        tot.setdefault(k, [0, 0, 0])
        tot[k][0] += 1; tot[k][1] += int(r["homes"]) > 0; tot[k][2] += int(r["homes"])
    print("by kind [run, with homes, homes]:", tot, "errors:", sum(r["layout"].startswith("error") for r in rows))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        export()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
