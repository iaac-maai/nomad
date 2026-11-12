"""Do rooms or flats overlap in NOMAD's layouts? Every option of the 40 test shops: rooms inside a flat, and flats against flats."""
import sys
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import eval_space
TOL = 0.05   # m2: slivers from rounding


def run(a):
    from shapely.geometry import Polygon
    import plan3
    ref, s, lit = a
    _, its, _ = plan3.iterations(s["outline"], s["facade"], s["height"], eval_space.MIX, street=s.get("street"), existing=s.get("existing"), lit_depth=lit or 5.5, lit_source="bars" if lit else None)
    rooms = flats = rm = fl = 0; by = {}
    for it in its:
        us = [u for u in it[1]["units"] if u.get("ok")]
        P = [Polygon(u["outline"]).buffer(0) for u in us]
        for i in range(len(P)):
            for j in range(i + 1, len(P)):
                fl += 1
                o = P[i].intersection(P[j]).area
                flats += o > TOL
                if o > TOL:
                    by[it[0]] = by.get(it[0], 0) + 1
        for u in us:
            R = [Polygon(r["pts"]).buffer(0) for r in u["rooms"]]
            for i in range(len(R)):
                for j in range(i + 1, len(R)):
                    rm += 1
                    rooms += R[i].intersection(R[j]).area > TOL
    return rm, rooms, fl, flats, by


if __name__ == "__main__":
    with Pool(4) as p:
        R = p.map(run, eval_space.shops(), 1)
    print("room pairs %d, overlapping %d; flat pairs %d, overlapping %d" % tuple(sum(r[k] for r in R) for k in range(4)))
    t = {}
    for r in R:
        for k, v in r[4].items():
            t[k] = t.get(k, 0) + v
    print(t)
