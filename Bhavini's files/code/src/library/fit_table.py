"""Nomad - which real plans can pass at each flat size, worked out once so the browser does not have to.
For every bedroom count, door mode, width and depth (25 cm steps): the first plans that pass every legal check and furniture check.
Out: src/generate/fit_table.json. Rebuild it whenever the library, the checks or the furniture rules change.
Run: .venv/Scripts/python src/library/fit_table.py [workers]
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / p) for p in ("rhino", "generate", "check")]
KEEP = 8
WS = range(12, 81)      # 3 to 20 m wide
DS = range(16, 61)      # 4 to 15 m deep


def _cell(job):
    import plan3
    import furnish as U
    import library_fit as F
    b, lit, ent, gen, w4 = job
    keep = {}
    for d4 in DS:
        W, D = w4 / 4.0, d4 / 4.0
        got = []
        for g in F.iter_fits(plan3.library(), b, W, D, lit=lit, entry_sides=ent, generate=gen):
            if str(g["id"]) in got:
                continue
            try:
                if not U.passes(U.furnish(g)[1]):
                    continue
            except Exception:
                continue
            got.append(str(g["id"]))
            if len(got) >= KEEP:
                break
        if got:
            keep["%d,%d" % (w4, d4)] = got
    return b, lit, ent, gen, keep


def main(workers):
    import plan3
    modes = sorted(set((tuple(l), tuple(e)) for l, e in plan3.MODES.values()))
    jobs = [(b, l, e, g, w) for b in sorted(set(plan3.BEDS.values())) for l, e in modes for g in (False, True) for w in WS]
    print(len(jobs), "jobs", flush=True)
    ids, index, fits, t = [], {}, {}, time.time()
    with Pool(workers) as pool:
        for n, (b, l, e, g, keep) in enumerate(pool.imap_unordered(_cell, jobs)):
            k = "%d|%s|%s|%d" % (b, ",".join(l), ",".join(e), g)
            for cell, got in keep.items():
                fits.setdefault(k, {})[cell] = [index.setdefault(i, len(index)) for i in got]
            if n % 200 == 0:
                print(n, round(time.time() - t), flush=True)
    ids = sorted(index, key=index.get)
    json.dump({"ids": ids, "fits": fits}, open(ROOT / "src" / "generate" / "fit_table.json", "w"), separators=(",", ":"))
    print("done", len(ids), "plans,", sum(len(v) for v in fits.values()), "sizes", round(time.time() - t), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
