"""Why a shop gets no flats with their own street door."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "7_floor_plans/code"))
import plan2, plan3, layout, eval_space
A = {a[0]: a for a in eval_space.shops()}
for ref in sys.argv[1:]:
    _, s, lit = A[ref]; plan3.LIT[0] = lit or 5.5; plan3._FIT.clear(); layout._DEPTH.clear(); plan3._EXISTING[:] = []
    st = s.get("street") or s["facade"]
    fr = [f for f in plan2._fronts(s["outline"], s["facade"], st)]
    print(ref, "lit", lit, "fronts", [(round(b - a, 1), f.public) for f in fr for a, b in f.spans])
    for D in plan3.DOOR_DEPTHS[:4]:
        p = plan3.build_doors(s["outline"], s["facade"], st, s["height"], {"1bed": 2, "2bed": 1}, D, True, False, None)
        print(" D", D, "units", [(u["type"], u["facade_w"], u.get("ok"), [str(x)[:40] for x in (u.get("fails") or [])][:2]) for u in p["units"]][:6], "left", p.get("left") or p.get("unplaced") and len(p.get("unplaced")))
    f = max(fr, key=lambda f: max(b - a for a, b in f.spans)); a, b = max(f.spans, key=lambda q: q[1] - q[0])
    for u in (a, a + (b - a) * .25, a + (b - a) * .5, a + (b - a) * .75):
        print("  at", round(u, 1), "depth", [round(layout.depth_at(f.local, u, u + w), 1) for w in (3, 6, 8)], "inside", [plan3.inside_shop(f, u, w, 5.75) for w in (6, 8)])
    print("  widths", {t: plan3.widths_for(t, 6.0, "door")[:6] for t in ("studio", "1bed")})
