"""Why flats do not fit: for each lit depth, how many sizes (width x depth) have a plan that passes."""
import json, sys, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import plan3, eval_space
A = eval_space.shops()
print("lit depths of the 40:", sorted(round(a[2], 1) for a in A if a[2]), "none:", sum(1 for a in A if not a[2]))
for lit in (2.5, 3.0, 3.5, 4.0, 5.5):
    plan3.LIT[0] = lit; plan3._FIT.clear()
    row = {}
    for t in ("studio", "1bed", "2bed"):
        ok = []
        for D in (5.0, 6.0, 7.0, 8.0, 9.0):
            for w10 in range(40, 125, 5):
                w = w10 / 10.0
                if plan3.fits(t, w, D, None, "hall", gen=False):
                    ok.append((w, D))
        row[t] = (len(ok), sorted(set(d for _, d in ok)), min([w for w, _ in ok] or [0]))
    print("lit", lit, row)
