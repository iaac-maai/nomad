"""Nomad - the website's engine: NOMAD's own pipeline for one shop and the user's requirements, run in the browser
(Pyodide) with the same files as Rhino: layout.py, better.py, flags.py, nomad_core.py, nomad_model.py, prisms.py.

  run(request_json) -> result_json
request: {"shop": {"outline", "facade", "height", "name", "source", "zoning"?},
          "mix": {"studio": n, "1bed": n, "2bed": n, "3bed": n},
          "sizes": {"1bed": m², ...}  (target useful area per flat type; empty = sizes learned from real flats),
          "programs": room_programs.json "programs", "own": [your plans, 7_floor_plans/code/own_plans.py]}
or {"add_plans": [{"name", "text"}]} -> each plan read and checked (own_plans.read)
result: the shop as it is (verdict, rule cards) and three layouts, each with its rooms, verdict, homes, rule cards,
        changes made, and its walls model as prisms for the 3D view (prisms.py).
Also runs in normal Python: .venv/Scripts/python app/code/nomad_web.py  (a self-test on a dataset shop)
"""
import json, sys

for _p in ("rhino_grasshopper/code", "7_floor_plans/code", "6_check_the_shop/code", "7_floor_plans/code", "7_floor_plans/code"):
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
            "existing": plan.get("existing", []), "light_wells": plan.get("light_wells", []), "interventions": plan.get("interventions", []),
            "levels": plan.get("levels", 1), "storey_h": plan.get("storey_h"), "cores": [c["pts"] for c in plan.get("cores", [])],
            "shared_spaces": plan.get("shared_spaces", []), "floor": plan.get("floor"), "comfort": plan.get("comfort"), "score": plan.get("score"), "fire_walls": plan.get("fire_walls", []), "risers": plan.get("risers", []), "dead_m2": plan.get("dead_m2", 0), "lobby_uses": plan.get("lobby_uses", []), "cascade": plan.get("cascade"), "solar": plan.get("solar"), "way": plan.get("way"), "ducts": [d for u in plan.get("units", []) for d in u.get("ducts", [])]}


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


ANNEX4 = "Decret 141/2012 Annex 4 apartat 2"
COMMUNITY = "Decret 141/2012 Annex 1 2.6 (community room from 8 homes: 1,20 x 0,80 m, +0,05 m2 per home over 12)"


def _annex4(grup, homes, plan):
    """The conversion group of this shop (Bars's tools/annex4_grup.py from the Catastro CAT data) and what it adds.
    grup = [group, % of the building, how the unit was found, largest %, why unknown]. Grups B, C and D: 2,40 m.
    Grup C: Annex 1 apartat 2 exempt except 2.2.1, patios not required. Grup D: apartat 2 applies: 2.1 route (all homes on the entry level: met),
    2.2.2 landing (no lift on one level), 2.5.1 patios -10 % (NOMAD's shop plans light no room from a patio), and 2.6 the
    community room from 8 homes, checked here against the plan's shared rooms."""
    g = grup[0] if grup else "unknown"
    pct = "" if not grup or grup[1] is None else "%s %% of the building's built area%s" % (grup[1], " (up to %s %%)" % grup[3] if len(grup) > 3 and grup[3] not in (None, grup[1]) else "")
    text = {"C": "Grup C (<= 50 %): Annex 1 apartat 2 exempt except 2.2.1 (each home reached from a public or common space); patios not required; 2,40 m clear height",
            "D": "Grup D (> 50 %): Annex 1 apartat 2 applies (2.1 accessible route, 2.2.2 1,50 m landing, 2.6 community room from 8 homes); patios -10 %; 2,40 m clear height",
            "B": "Grup B: total change of use of the building; use the whole-building mode; patios -10 %; 2,40 m clear height",
            }.get(g, "group not known (no Catastro unit found for this premises): NOMAD applies Grup C")
    cards = [{"title": "Conversion group", "ok": True, "check": text, "value": pct or g, "limit": None, "cite": ANNEX4,
              "scope": "Catastro CAT data (team tool annex4_grup.py): a NOMAD estimate"}]
    if g == "D" and homes >= 8:
        need = 1.20 * 0.80 + 0.05 * max(0, homes - 12)
        have = sum(x.get("area", 0) for x in plan.get("shared_spaces", []) if x.get("name") != "service corridor")
        cards.append({"title": "Community room (Grup D)", "ok": have >= need - 1e-6, "check": "%d homes: a community room of %.2f m2 is needed; %.1f m2 of shared rooms in the plan" % (homes, need, have),
                      "value": round(have, 1), "limit": round(need, 2), "cite": COMMUNITY, "scope": "Grup D conversions"})
    return cards


def run(request_json):
    q = json.loads(request_json)
    if "add_plans" in q:
        return add_plans(q)
    import plan3
    plan3.use_table("/nomad/fit_table.json")
    plan3.BUDGET = 12                                        # the browser waits at most about this long on the real-plan search
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
    if shop.get("kind") in ("warehouse", "commercial", "office"):   # a whole building (7_floor_plans/code/building.py, Group B)
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
        extra = _annex4(shop.get("annex4"), it["homes"], it["plan"]) if not story.get("building") else []
        verdict = r["verdict"]
        if verdict == "YES" and any(not c["ok"] for c in extra):
            verdict = "PARTLY"
        out["iterations"].append({"label": it["label"], "homes": it["homes"], "verdict": verdict, "mix": r.get("mix_text", ""),
                                  "cards": extra + _cards(r), "plan": _plan(it["plan"]), "prisms": prisms.prisms(shop, it["plan"]),
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
