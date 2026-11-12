"""Nomad - Stage 7 outside Rhino: the walls model of a layout as plain prisms (outline, base height, height, colour).

src/rhino/nomad_model.build_walls (the Rhino code) runs here with its Rhino calls swapped for ones that record each
solid, so Rhino, IFC (export_ifc.py), glTF and the website's 3D all show the same walls, glass, doors and floors.
Plain Python only (no numpy), so it also runs in the browser (Pyodide).
  prisms(shop, plan) -> [{"kind", "pts", "z0", "h", "rgb"}]    kind: wall / window / door / entry / slab / patio /
                                                               corridor / furniture / floor:<room kind>
"""
import sys, types

# nomad_model.py is written for Rhino: stub the Rhino / .NET modules it imports
for _m in ("Rhino", "Rhino.Geometry", "System", "System.Drawing"):
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.modules["Rhino"].Geometry = sys.modules["Rhino.Geometry"]
sys.modules["System"].Drawing = sys.modules["System.Drawing"]
sys.modules["System"].Guid = types.SimpleNamespace(Empty=None)
import nomad_model as M  # noqa: E402


def _door_box(edges, c, w):
    """A thin leaf for a door centred at c, lined up with the nearest wall edge."""
    best = None
    for a, b in edges:
        d = M._d(c, (a, b))
        if best is None or d < best[0]:
            best = (d, a, b)
    _, a, b = best
    L = M._seg_len(a, b) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy * 0.025, ux * 0.025
    p, q = (c[0] - ux * w / 2, c[1] - uy * w / 2), (c[0] + ux * w / 2, c[1] + uy * w / 2)
    return [(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)]


def all_edges(shop, plan):
    pts = shop["outline"][:-1] if shop["outline"][0] == shop["outline"][-1] else shop["outline"]
    e = M._edges(pts)
    for u in plan.get("units", []):
        for r in u["rooms"]:
            if len(r["pts"]) >= 3:
                e += M._edges(r["pts"])
    return e


def prisms(shop, plan):
    rec = []
    M._block = lambda pts, z0, h, mv: ([(x + mv[0], y + mv[1]) for x, y in pts], z0 + M.ZOFF[0], h)
    M._attr = lambda doc, lay, rgb, clean=False: rgb

    class Objs:
        def AddBrep(self, g, rgb):
            rec.append((g, rgb))
            return 1
    M.build_walls(types.SimpleNamespace(Objects=Objs()), shop, plan, (0.0, 0.0), 0)
    room_rgb = dict((tuple(v), k) for k, v in M.COL.items())
    named = {tuple(M.WALLC): "wall", tuple(M.GLASSC): "window", tuple(M.SLABC): "slab", tuple(M.PATIO): "patio",
             tuple(M.CORR): "corridor", tuple(M.FURNC): "furniture", tuple(M.CORE): "core"}
    out = []
    for (pts, z0, h), rgb in rec:
        rgb = tuple(rgb)
        kind = named.get(rgb) or ("floor:" + room_rgb.get(rgb, "fails a rule"))
        out.append({"kind": kind, "pts": [list(p) for p in pts], "z0": z0, "h": h, "rgb": list(rgb)})
    edges = all_edges(shop, plan)
    for c, w, z0, z1, kind in M._openings(shop, plan):        # door leaves (the openings are already cut in the walls)
        if kind in ("door", "entry"):
            out.append({"kind": kind, "pts": [list(p) for p in _door_box(edges, c, w)], "z0": z0, "h": z1 - z0,
                        "rgb": [120, 124, 130]})
    return out
