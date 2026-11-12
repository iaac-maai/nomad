"""Nomad - the team's L-shaped parcel test, run through the real engine (plan3). 450 m2, street along y = 0.
Out: results/eval/test_slicing.json.  Run: .venv/Scripts/python src/check/test_slicing.py"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "generate"))
import plan3

L = [[0.0, 0.0], [20.0, 0.0], [20.0, 15.0], [10.0, 15.0], [10.0, 30.0], [0.0, 30.0]]
STREET = [[[0.0, 0.0], [20.0, 0.0]]]


def run():
    _, its, _ = plan3.iterations(L, STREET, 3.0, {"1bed": 2, "2bed": 1}, street=STREET)
    name, p = max(its, key=lambda it: len([u for u in it[1]["units"] if u.get("ok")]))[:2]
    units = [u for u in p["units"] if u.get("ok")]
    rooms = [{"room_id": "home%d_%s" % (i + 1, r["name"].replace(" ", "_")), "type": r["kind"], "area_sqm": r["area"]} for i, u in enumerate(units) for r in u["rooms"]]
    zones = [{"zone_id": "shared_%d" % (i + 1), "function": x["name"], "area_sqm": x["area"], "access": x["access"]} for i, x in enumerate(p.get("shared_spaces", []))]
    halls = [{"function": c.get("name", "corridor"), "area_sqm": round(plan3.area([tuple(q) for q in c["pts"]]), 1)} for c in p.get("corridors", [])]
    f = p.get("floor") or {}
    named = sum(r["area_sqm"] for r in rooms) + sum(z["area_sqm"] for z in zones) + sum(h["area_sqm"] for h in halls)
    return {"strategy": name, "total_plot_area_sqm": f.get("total"), "homes": len(units), "floor_in_homes_sqm": f.get("homes"), "shared_and_service_sqm": f.get("shared"),
            "named_floor_sqm": round(named, 1), "plot_coverage_percentage": "%.1f%%" % (100.0 * named / f["total"]), "dead_sqm": p.get("dead_m2"), "score": p.get("score"),
            "rooms": rooms, "corridors": halls, "shared_and_service": zones, "fire_walls": len(p.get("fire_walls", []))}


if __name__ == "__main__":
    r = run()
    (ROOT / "results" / "eval").mkdir(exist_ok=True)
    json.dump(r, open(ROOT / "results" / "eval" / "test_slicing.json", "w", encoding="utf-8"), indent=1)
    print({k: v for k, v in r.items() if k not in ("rooms", "shared_and_service", "corridors")})
    print(r["corridors"]); print(r["shared_and_service"])
