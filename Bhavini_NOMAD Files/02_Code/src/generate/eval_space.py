"""How well NOMAD uses the floor it can legally use, on the same 40 real shops as the plan-AI test (results/ai).
Reachable floor = inside the shop and within 9 m of a street facade: Decret 141/2012 Annex 1 3.6.2 (facade >= S/9) caps the
depth of a flat lit from one facade at 9 m. Efficiency = useful floor of the flats that pass every rule / reachable floor.
Each shop keeps the option with the most homes (ties: most floor used). Out: results/space/<tag>.csv + summary line."""
import csv, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "generate")); sys.path.insert(0, str(ROOT / "src" / "check"))
REACH = 9.0
MIX = {"1bed": 2, "2bed": 1}


def shops():
    S = json.load(open(ROOT / "results" / "real_shops" / "shells.json", encoding="utf-8"))
    refs = [r["ref"] for r in csv.DictReader(open(ROOT / "results" / "ai" / "shops40_base2.csv", encoding="utf-8"))]
    D = {}                                                               # Bars's lit depth per shop (site/data/daylight.json)
    for k, v in json.load(open(ROOT / "site" / "data" / "daylight.json", encoding="utf-8"))["shops"].items():
        D.setdefault(k[:14], max(q[2] for q in v))
    return [(r, S[r], D.get(r)) for r in refs if r in S]


def reach(s):
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    o = Polygon(s["outline"]).buffer(0)
    st = s.get("street") or s.get("facade") or []
    if not st:
        return o.area, 0.0
    return o.area, o.intersection(unary_union([LineString(q).buffer(REACH, cap_style=2) for q in st])).area


def run(a):
    ref, s, lit = a
    import plan3
    floor, rch = reach(s)
    try:
        _, its, _ = plan3.iterations(s["outline"], s["facade"], s["height"], MIX, street=s.get("street"), existing=s.get("existing"),
                                     lit_depth=lit or 5.5, lit_source="bars" if lit else None)
    except Exception as e:
        return dict(ref=ref, floor=round(floor), reach=round(rch), homes=0, used=0, eff=0, err=str(e)[:60])
    best = (0, 0.0, "")
    for it in its:
        name, p = it[0], it[1]
        ok = [u for u in p["units"] if u.get("ok")]
        used = sum(sum(r["area"] for r in u.get("rooms", [])) for u in ok)
        if (len(ok), used) > best[:2]:
            best = (len(ok), used, name)
    return dict(ref=ref, floor=round(floor), reach=round(rch), homes=best[0], used=round(best[1]), eff=round(best[1] / rch, 3) if rch else 0, err=best[2][:30])


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    A = shops(); t0 = time.time()
    with Pool(max(2, (os.cpu_count() or 4) - 2)) as p:
        R = p.map(run, A, 1)
    (ROOT / "results" / "space").mkdir(exist_ok=True)
    with open(ROOT / "results" / "space" / (tag + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(R[0])); w.writeheader(); w.writerows(R)
    F, C, U, H = (sum(r[k] for r in R) for k in ("floor", "reach", "used", "homes"))
    print("%s: %d shops, %d with homes, %d homes, floor %d, reachable %d, used %d = %.0f %% of reachable, %.0f %% of floor (%.0f s)" % (tag, len(R), sum(1 for r in R if r["homes"]), H, F, C, U, 100.0 * U / max(C, 1), 100.0 * U / max(F, 1), time.time() - t0))
