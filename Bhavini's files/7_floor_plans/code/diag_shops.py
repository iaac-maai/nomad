"""For the shops with the biggest unused reachable floor: how long their street fronts are and how deep."""
import csv, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import plan2, plan3, layout, eval_space
tag = sys.argv[1] if len(sys.argv) > 1 else "placed"
R = {r["ref"]: r for r in csv.DictReader(open(ROOT / "7_floor_plans/output/space" / (tag + ".csv"), encoding="utf-8"))}
A = {a[0]: a for a in eval_space.shops()}
rows = sorted(R.values(), key=lambda r: -(int(r["reach"]) - int(r["used"])))
for r in rows[:22]:
    ref, s, lit = A[r["ref"]]
    st = s.get("street") or s["facade"]
    fr = []
    for f in plan2._fronts(s["outline"], s["facade"], st):
        for x0, x1 in f.spans:
            ds = [layout.depth_at(f.local, x0 + (x1 - x0) * k, x0 + (x1 - x0) * k + 1.0) for k in (0.1, 0.5, 0.85)]
            fr.append("%.1fm d%s" % (x1 - x0, "/".join("%.0f" % d for d in ds)))
    print(ref, "floor", r["floor"], "reach", r["reach"], "homes", r["homes"], "used", r["used"], "lit", round(lit or 0, 1), "existing", len(s.get("existing") or []), fr[:4])
