# -*- coding: utf-8 -*-
"""Nomad - your own plans in the library: read a flat plan you drew, check it like every real plan, and let NOMAD use it.

Input, in metres (mm and cm are detected), any rotation:
  DXF   (Rhino 7: File > Export Selected > .dxf; AutoCAD) - each room a closed polyline on a layer named by its use
        (living / bedroom / kitchen / bath / hall / storage, also in Catalan and Spanish: estar, dormitori, cuina, bany,
        rebedor ...) or with a text label inside it; doors and windows as lines across the opening on layers "door" and
        "window"; the flat's entrance door on "entrance"; rooms open to each other (no wall) with a line on "open".
  JSON  {"name", "rooms": [{"kind", "pts"}], "doors": [[[x, y], [x, y]]], "windows": [...], "entrance": [[x, y], [x, y]],
         "open": [...]}  (a door may also be {"at": [x, y], "w": 0.8})
It is then squared (the side with most window becomes the front), turned into the plan graph (rooms = nodes, doors and
open connections = edges), and checked exactly like the real flats: plan graph, door widths, turning circles, room
widths (src/generate/library_fit.py) and furniture (src/generate/furnish.py). Walls stay where you drew them: when it is
stretched into a shop, its walls between rooms are locked like any library plan.
A floor plan image or PDF (src/building/read_plan.py) gives the shop's outline only, not labelled rooms: draw the rooms.
Plain Python (no shapely), so it also runs in the browser.
  read(text, name)  -> (entry or None, checks, message)
Run: .venv/Scripts/python src/library/own_plans.py plan.dxf [--name "Casa 1"]   (adds it to results/library/library_own.json)
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "generate"), HERE):
    if _p not in sys.path:
        sys.path.append(_p)
import furnish as U  # noqa: E402
import library_fit as F  # noqa: E402

WORDS = [  # layer or label word -> NOMAD kind (English, Catalan, Spanish)
    ("living", ("living", "lounge", "estar", "sala", "salon", "salón", "menjador", "comedor", "dining")),
    ("bed", ("bed", "dormitori", "dormitorio", "habitaci", "chambre")),
    ("kitchen", ("kitchen", "cuina", "cocina")),
    ("bath", ("bath", "bany", "baño", "bano", "wc", "aseo", "lavabo", "toilet")),
    ("hall", ("hall", "corridor", "passad", "pasillo", "rebedor", "recibidor", "distribu", "entrance hall", "pas")),
    ("storage", ("storage", "store", "rober", "trastero", "armari", "despensa")),
    ("entrance", ("entrance", "entrada", "acces", "acceso")),
    ("door", ("door", "porta", "puerta")),
    ("window", ("window", "finestra", "ventana")),
    ("open", ("open", "obert", "abierto")),
]
SNAP = 0.12


def kind_of(word):
    w = (word or "").strip().lower()
    for k, keys in WORDS:
        if any(w == x or w.startswith(x) or (len(x) > 3 and x in w) for x in keys):
            return k
    return None


# ---------- DXF (ASCII) ----------
def _pairs(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i in range(0, len(lines) - 1, 2):
        yield lines[i].strip(), lines[i + 1].strip()


def parse_dxf(text):
    """-> {"units": INSUNITS or None, "polys": [(layer, pts)], "lines": [(layer, a, b)], "texts": [(text, pt)]}"""
    out = {"units": None, "polys": [], "lines": [], "texts": []}
    pairs = list(_pairs(text))
    i, n = 0, len(pairs)
    while i < n:
        c, v = pairs[i]
        if c == "9" and v == "$INSUNITS" and i + 1 < n:
            try:
                out["units"] = int(pairs[i + 1][1])
            except ValueError:
                pass
        if c == "0" and v in ("LWPOLYLINE", "POLYLINE", "LINE", "TEXT", "MTEXT"):
            ent, j = v, i + 1
            rec = []
            while j < n and pairs[j][0] != "0":
                rec.append(pairs[j])
                j += 1
            layer = "".join(x[1] for x in rec if x[0] == "8")
            if ent == "LWPOLYLINE":
                xs = [float(x[1]) for x in rec if x[0] == "10"]
                ys = [float(x[1]) for x in rec if x[0] == "20"]
                flag = int(([x[1] for x in rec if x[0] == "70"] or ["0"])[0])
                pts = list(zip(xs, ys))
                if len(pts) >= 3 and (flag & 1 or pts[0] == pts[-1]):
                    out["polys"].append((layer, pts))
                elif len(pts) == 2:
                    out["lines"].append((layer, pts[0], pts[1]))
            elif ent == "POLYLINE":
                flag = int(([x[1] for x in rec if x[0] == "70"] or ["0"])[0])
                pts = []
                while j < n and not (pairs[j][0] == "0" and pairs[j][1] == "SEQEND"):
                    if pairs[j] == ("0", "VERTEX"):
                        k, x, y = j + 1, None, None
                        while k < n and pairs[k][0] != "0":
                            if pairs[k][0] == "10":
                                x = float(pairs[k][1])
                            if pairs[k][0] == "20":
                                y = float(pairs[k][1])
                            k += 1
                        if x is not None and y is not None:
                            pts.append((x, y))
                        j = k
                    else:
                        j += 1
                if len(pts) >= 3 and (flag & 1 or pts[0] == pts[-1]):
                    out["polys"].append((layer, pts))
                elif len(pts) == 2:
                    out["lines"].append((layer, pts[0], pts[1]))
            elif ent == "LINE":
                g = dict(rec)
                try:
                    out["lines"].append((layer, (float(g["10"]), float(g["20"])), (float(g["11"]), float(g["21"]))))
                except (KeyError, ValueError):
                    pass
            else:
                g = dict(rec)
                try:
                    out["texts"].append((g.get("1", ""), (float(g["10"]), float(g["20"]))))
                except (KeyError, ValueError):
                    pass
            i = j
            continue
        i += 1
    return out


def from_dxf(text):
    d = parse_dxf(text)
    allp = [p for _, q in d["polys"] for p in q]
    if not allp:
        raise ValueError("no closed polylines (rooms) in the DXF")
    ext = max(max(p[0] for p in allp) - min(p[0] for p in allp), max(p[1] for p in allp) - min(p[1] for p in allp))
    k = {4: 0.001, 5: 0.01, 6: 1.0}.get(d["units"])
    if k is None:                                    # no units in the file: a flat is 4-30 m across
        k = 0.001 if ext >= 3000 else 0.01 if ext >= 300 else 1.0
    S = lambda p: (round(p[0] * k, 3), round(p[1] * k, 3))
    plan = {"rooms": [], "doors": [], "windows": [], "entrance": None, "open": []}
    for layer, pts in d["polys"]:
        kind = kind_of(layer)
        if kind not in ("living", "bed", "kitchen", "bath", "hall", "storage"):
            lab = [t for t, p in d["texts"] if F.inside(p[0], p[1], pts)]
            kind = next((kind_of(t) for t in lab if kind_of(t) in ("living", "bed", "kitchen", "bath", "hall", "storage")), None)
        if kind:
            q = [S(p) for p in pts]
            if q[0] == q[-1]:
                q = q[:-1]
            plan["rooms"].append({"kind": kind, "pts": q})
    for layer, a, b in d["lines"]:
        kind = kind_of(layer)
        if kind == "door":
            plan["doors"].append([S(a), S(b)])
        elif kind == "window":
            plan["windows"].append([S(a), S(b)])
        elif kind == "entrance":
            plan["entrance"] = [S(a), S(b)]
        elif kind == "open":
            plan["open"].append([S(a), S(b)])
    return plan


# ---------- geometry ----------
def _seg(o):
    """A door / window as (centre, width) from [a, b] or {"at", "w"}."""
    if isinstance(o, dict):
        return tuple(o["at"]), float(o["w"])
    a, b = o
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), math.hypot(b[0] - a[0], b[1] - a[1])


def _dist(p, pts):
    return min(F._seg_dist(p, a, b) for a, b in zip(pts, pts[1:] + pts[:1]))


def _snap(vals):
    vs = sorted(set(round(v, 3) for v in vals))
    groups, cur = [], [vs[0]]
    for v in vs[1:]:
        if v - cur[-1] <= SNAP:
            cur.append(v)
        else:
            groups.append(cur)
            cur = [v]
    groups.append(cur)
    m = {}
    for g in groups:
        c = round(sum(g) / len(g), 2)
        for v in g:
            m[v] = c
    return m


def _side(p, W, D, tol=0.7):
    d = {"front": p[1], "back": D - p[1], "left": p[0], "right": W - p[0]}
    k = min(d, key=d.get)
    return k if d[k] <= tol else "inside"


def square(plan):
    """Turn the plan so its walls run along x and y and the side with most window is the front (y = 0)."""
    rooms = plan["rooms"]
    if not rooms:
        raise ValueError("no rooms")
    best = (0.0, 0.0)                                # wall direction: the longest room edge
    for r in rooms:
        for a, b in zip(r["pts"], r["pts"][1:] + r["pts"][:1]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L > best[0]:
                best = (L, math.atan2(b[1] - a[1], b[0] - a[0]))
    ang0 = best[1]
    wins = [_seg(w) for w in plan.get("windows", [])]

    def turn(a):
        c, s = math.cos(a), math.sin(a)
        return lambda p: (p[0] * c - p[1] * s, p[0] * s + p[1] * c)

    pick = None
    for q in range(4):
        t = turn(-ang0 + q * math.pi / 2)
        P = [t(p) for r in rooms for p in r["pts"]]
        x0, y0 = min(p[0] for p in P), min(p[1] for p in P)
        W, D = max(p[0] for p in P) - x0, max(p[1] for p in P) - y0
        front = sum(w for c, w in wins if _side((t(c)[0] - x0, t(c)[1] - y0), W, D) == "front")
        if pick is None or front > pick[0] + 1e-6:
            pick = (front, t, x0, y0)
    _, t, x0, y0 = pick
    T = lambda p: (t(p)[0] - x0, t(p)[1] - y0)
    for r in rooms:                                  # rectilinear after the turn?
        q = [T(p) for p in r["pts"]]
        for a, b in zip(q, q[1:] + q[:1]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 0.05 and min(abs(b[0] - a[0]), abs(b[1] - a[1])) > 0.08:
                raise ValueError("the %s has a slanted wall: NOMAD's library holds rectilinear plans" % r["kind"])
    xs = _snap([T(p)[0] for r in rooms for p in r["pts"]])
    ys = _snap([T(p)[1] for r in rooms for p in r["pts"]])
    S = lambda p: [xs[round(T(p)[0], 3)], ys[round(T(p)[1], 3)]]
    out = []
    for r in rooms:
        pts = []
        for p in r["pts"]:
            q = S(p)
            if not pts or q != pts[-1]:
                pts.append(q)
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        out.append({"kind": r["kind"], "pts": pts})
    W, D = max(xs.values()), max(ys.values())
    move = lambda o: (lambda c, w: {"at": [round(T(c)[0], 2), round(T(c)[1], 2)], "w": round(w, 2)})(*_seg(o))
    return out, W, D, move


def build(plan, name="your plan"):
    """The plan as a library entry (the same fields as src/library/build_library.py), or ValueError."""
    rooms, W, D, move = square(plan)
    for r in rooms:
        r["area"] = round(F.poly_area(r["pts"]), 2)
        r["clear"] = round(F.clear_width(r["pts"]), 2)
        if r["area"] < 0.5:
            raise ValueError("a %s smaller than 0,5 m²" % r["kind"])
    beds = sorted([i for i, r in enumerate(rooms) if r["kind"] == "bed"], key=lambda i: -rooms[i]["area"])
    if beds:
        rooms[beds[0]]["kind"] = "bed_main"
    doors = [move(d) for d in plan.get("doors", [])]
    windows = []
    for w in plan.get("windows", []):
        m = move(w)
        m["side"] = _side(m["at"], W, D)
        windows.append(m)
    edges = []
    for d in doors:                                  # a door joins the two rooms nearest to it (walls up to 0,5 m)
        t = sorted((_dist(d["at"], r["pts"]), i) for i, r in enumerate(rooms) if _dist(d["at"], r["pts"]) < 0.5)
        if len(t) >= 2:
            edges.append([t[0][1], t[1][1], d["w"]])
    for o in plan.get("open", []):                   # rooms open to each other
        c = move(o)["at"]
        t = sorted((_dist(c, r["pts"]), i) for i, r in enumerate(rooms) if _dist(c, r["pts"]) < 0.5)
        if len(t) >= 2:
            edges.append([t[0][1], t[1][1], 0.0])
    ent = None
    if plan.get("entrance"):
        ent = move(plan["entrance"])
        ent["side"] = _side(ent["at"], W, D)
        t = sorted((_dist(ent["at"], r["pts"]), i) for i, r in enumerate(rooms) if _dist(ent["at"], r["pts"]) < 0.8)   # outer walls are thicker
        ent["room"] = t[0][1] if t else None
    lit = sorted(set(w["side"] for w in windows if w["side"] in ("front", "back")))
    return {"id": "own:" + name, "bedrooms": len(beds), "W": round(W, 2), "D": round(D, 2), "rooms": rooms, "doors": doors,
            "windows": windows, "entrance": ent, "edges": edges, "lit": lit,
            "useful": round(sum(r["area"] for r in rooms), 1), "source": "your plan: " + name, "W0": round(W, 2), "D0": round(D, 2)}


def read(text, name="your plan"):
    """DXF or JSON text -> (entry or None, checks, message). The entry passes every check NOMAD's library asks for."""
    try:
        s = text.lstrip()
        plan = json.loads(s) if s.startswith("{") else from_dxf(text)
        name = plan.get("name") or name
        f = build(plan, name)
    except (ValueError, KeyError, TypeError, IndexError) as e:
        return None, [], "could not read the plan: %s" % e
    if not f["entrance"]:
        return None, [], "no entrance door: draw it as a line on the layer 'entrance'"
    side = f["entrance"]["side"]
    one = f["lit"] == ["front"] and side in ("back", "left", "right")
    through = f["lit"] == ["back", "front"] and side in ("left", "right")
    if f["bedrooms"] > 3:
        return None, [], "NOMAD's library holds studios to 3 bedrooms"
    g = F.widen_doors(f)
    cs = F.checks(g)
    sw = F.swings(g)
    g["swings"] = sw
    items, fc = U.furnish(g)
    cs = cs + fc
    bad = [c["text"] for c in cs if not c["ok"] and (c["rule"] != "furniture" or not c["text"].startswith("living"))]
    if not (one or through):
        bad.append("windows on the %s and the entrance on the %s: NOMAD places flats lit from the street and entered from the back or a side, "
                   "or through flats lit front and back entered from a side" % (" and ".join(f["lit"]) or "no side", side))
    g["furniture"] = items
    if bad:
        return None, cs, "it does not pass yet: " + "; ".join(bad)
    keep = dict((k, g[k]) for k in ("id", "bedrooms", "W", "D", "rooms", "doors", "windows", "entrance", "edges", "lit", "useful",
                                    "source", "W0", "D0"))
    return keep, cs, "added: %d bedroom%s, %.1f m², %.2f x %.2f m, %s" % (f["bedrooms"], "" if f["bedrooms"] == 1 else "s", f["useful"],
                                                                         f["W"], f["D"], "through flat" if through else "lit from the street")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--name")
    a = ap.parse_args()
    with open(a.path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    entry, cs, msg = read(text, a.name or os.path.splitext(os.path.basename(a.path))[0])
    print(msg)
    for c in cs:
        print("  %s %s" % ("ok  " if c["ok"] else "FAIL", c["text"]))
    if entry:
        p = os.path.join(HERE, "..", "..", "results", "library", "library_own.json")
        own = json.load(open(p)) if os.path.exists(p) else []
        own = [o for o in own if o["id"] != entry["id"]] + [entry]
        json.dump(own, open(p, "w"), separators=(",", ":"))
        print("saved to results/library/library_own.json (%d own plans); run src/library/street_library.py to use it" % len(own))


if __name__ == "__main__":
    main()
