"""Nomad - the website's engine: NOMAD's own pipeline for one shop and the user's requirements, run in the browser
(Pyodide) with the same files as Rhino: layout.py, better.py, flags.py, nomad_core.py, nomad_model.py, prisms.py.

  run(request_json) -> result_json
request: {"shop": {"outline", "facade", "height", "name", "source", "zoning"?},
          "mix": {"studio": n, "1bed": n, "2bed": n, "3bed": n},
          "sizes": {"1bed": m², ...}  (target useful area per flat type; empty = sizes learned from real flats),
          "programs": room_programs.json "programs", "own": [your plans, src/library/own_plans.py]}
or {"add_plans": [{"name", "text"}]} -> each plan read and checked (own_plans.read)
result: the shop as it is (verdict, rule cards) and three layouts, each with its rooms, verdict, homes, rule cards,
        changes made, and its walls model as prisms for the 3D view (prisms.py).
Also runs in normal Python: .venv/Scripts/python src/app/nomad_web.py  (a self-test on a dataset shop)
"""
import json, sys

for _p in ("src/rhino", "src/generate", "src/check", "src/model3d", "src/library"):
    if _p not in sys.path:
        sys.path.append(_p)
import layout  # noqa: E402
import flags  # noqa: E402
import nomad_core as core  # noqa: E402
import prisms  # noqa: E402

KEEP_CARD = ("title", "ok", "check", "value", "limit", "cite", "scope")


def _cards(res):
    return [dict((k, c.get(k)) for k in KEEP_CARD) for c in res["cards"]]


def _rooms(rooms):
    return [{"name": r["name"], "kind": r["kind"], "pts": r["pts"], "ok": bool(r.get("ok", True)), "area": r.get("area"),
             "why": r.get("why", "")} for r in rooms if len(r["pts"]) >= 3]


def _option(o):
    return {"lib": o["lib"], "ok": bool(o["ok"]), "fails": o.get("fails", []), "area": o.get("area_m2"), "rooms": _rooms(o["rooms"]),
            "swings": o.get("swings", []), "furniture": o.get("furniture", []), "room_scores": o.get("room_scores", []),
            "failing": [c["text"] for c in o.get("checks", []) if not c["ok"]]}


def _daylight(res):
    """The floor in bands from the windows (flags.daylight): lit (rooms can go), service, dark: [x0, y0, x1, y1, band]."""
    d = res.get("daylight") or {}
    return {"lit_depth": d.get("lit_depth"), "cells": [[round(c[0], 2), round(c[1], 2), round(c[2], 2), round(c[3], 2), c[5][0]]
                                                       for c in d.get("cells", [])]}


def _plan(plan):
    """What the page draws: flats, their rooms, door swings, furniture, the other real plans that fit each flat, patios, halls, and
    the building's existing portal / stair."""
    return {"units": [{"type": u["type"], "ok": bool(u.get("ok")), "area": u.get("area_m2"), "rooms": _rooms(u["rooms"]), "shared": bool(u.get("shared")),
                       "swings": u.get("swings", []), "furniture": u.get("furniture", []), "lib": u.get("lib"), "room_scores": u.get("room_scores", []),
                       "options": [_option(o) for o in u.get("options", [])]}
                      for u in plan.get("units", [])],
            "patios": [p["pts"] for p in plan.get("patios", [])], "corridors": [c["pts"] for c in plan.get("corridors", [])],
            "existing": plan.get("existing", []), "interventions": plan.get("interventions", []),
            "levels": plan.get("levels", 1), "storey_h": plan.get("storey_h"), "cores": [c["pts"] for c in plan.get("cores", [])]}


def add_plans(q):
    """Read your own plans (DXF or JSON text) -> for each: the entry to keep (or None), its checks and a message."""
    import own_plans
    out = []
    for p in q.get("add_plans", []):
        entry, cs, msg = own_plans.read(p["text"], p.get("name") or "your plan")
        draw = None
        if entry:                                            # a drawing of it, furnished, for the page
            import furnish, library_fit
            g = dict(entry, swings=library_fit.swings(library_fit.widen_doors(entry)))
            items, _ = furnish.furnish(g)
            draw = {"rooms": entry["rooms"], "furniture": [dict(x, pts=[[x["rect"][0], x["rect"][1]], [x["rect"][2], x["rect"][1]],
                                                                       [x["rect"][2], x["rect"][3]], [x["rect"][0], x["rect"][3]]]) for x in items]}
        out.append({"name": p.get("name"), "entry": entry, "message": msg, "draw": draw,
                    "failing": [c["text"] for c in cs if not c["ok"]]})
    return json.dumps({"plans": out})


def run(request_json):
    q = json.loads(request_json)
    if "add_plans" in q:
        return add_plans(q)
    import plan3
    plan3.set_own(q.get("own"))                              # your own plans join the real-plan library
    shop = dict(q["shop"])
    if shop["outline"][0] != shop["outline"][-1]:
        shop["outline"] = shop["outline"] + [shop["outline"][0]]
    shop.setdefault("name", "your shop")
    shop.setdefault("street", shop["facade"])
    shop.setdefault("source", "your shop")
    if q.get("weights"):
        shop["weights"] = q["weights"]                       # the user's weight sliders (plan3)
    mix = dict((k, int(v)) for k, v in q.get("mix", {}).items() if int(v or 0) > 0)
    sizes = dict((k, float(v)) for k, v in (q.get("sizes") or {}).items() if v)
    progs = q["programs"]
    if shop.get("kind") in ("warehouse", "commercial", "office"):   # a whole building (src/generate/building.py, Group B)
        story = core.run_building(shop, mix, float(shop.get("height") or 3.0), sizes=sizes or None, weights=q.get("weights"))
    else:
        story = core.run_story(shop, mix, programs=layout.with_targets(progs, sizes, "typical") if sizes else progs)
    b = story["before"]["res"]
    out = {"shop": {"area": b["shop_m2"], "facade_m": round(sum(((s[1][0] - s[0][0]) ** 2 + (s[1][1] - s[0][1]) ** 2) ** 0.5
                                                               for s in shop["facade"]), 1)},
           "building": bool(story.get("building")), "mix": core.mix_text(mix), "before": {"verdict": b["verdict"], "passing": b["flats_passing"], "asked": b["flats_asked"],
                                                   "cards": _cards(b), "plan": _plan(story["before"]["plan"]),
                                                   "daylight": _daylight(b)},
           "iterations": []}
    for it in story["iterations"]:
        r = it["res"]
        out["iterations"].append({"label": it["label"], "homes": it["homes"], "verdict": r["verdict"], "mix": r.get("mix_text", ""),
                                  "cards": _cards(r), "plan": _plan(it["plan"]), "prisms": prisms.prisms(shop, it["plan"]),
                                  "daylight": _daylight(r) if it["plan"].get("patios") else None})
    return json.dumps(out)


if __name__ == "__main__":                                   # self-test on a dataset shop, with sizes asked
    import time
    sh = core.shop_by_id(146519)
    progs = core.data()["programs"]
    t = time.time()
    res = json.loads(run(json.dumps({"shop": {k: sh[k] for k in ("outline", "facade", "height", "name", "source")},
                                     "mix": {"1bed": 2, "2bed": 1}, "sizes": {"1bed": 50, "2bed": 72}, "programs": progs})))
    print("as it is:", res["before"]["verdict"], "| layouts:", [(i["label"], i["homes"], i["verdict"], len(i["prisms"])) for i in res["iterations"]],
          "| %.1f s" % (time.time() - t))
    print("flat sizes, layout 1:", [u["area"] for u in res["iterations"][0]["plan"]["units"]])
