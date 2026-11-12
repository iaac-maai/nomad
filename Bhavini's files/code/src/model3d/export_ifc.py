"""Nomad - Stage 7 export: each layout's walls model as IFC (for BIM software) and glTF (.glb, for a web viewer).

The geometry is the same as the Rhino model (src/rhino/nomad_model.build_walls): that code is run here outside
Rhino, with its solid-making function swapped for one that records each prism (outline, base height, height,
colour). So IFC, glTF and Rhino show the same walls, glass, floors and slab.
  IFC (IfcOpenShell, LGPL-3.0): IfcProject > IfcSite > IfcBuilding > IfcBuildingStorey "Planta baixa";
      IfcWall per wall piece, IfcWindow per glass pane, IfcDoor per door / entry (a thin leaf in its opening),
      IfcSpace per room (name = flat + room, its floor area as a quantity), IfcSlab for the shop floor.
  glTF (trimesh, MIT): the same prisms with their E05 colours; doors in grey.

Run:  .venv/Scripts/python src/model3d/export_ifc.py [recipe names...]   (default: the demo shops D0-D4)
Out:  results/model3d/<case>_it<k>.ifc and .glb, + results/model3d/summary.json
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / "results" / "sheets" / "recipes"
OUT = ROOT / "results" / "model3d"

sys.path[:0] = [str(ROOT / "src" / "rhino"), str(ROOT / "src" / "check"), str(ROOT / "src" / "model3d")]
import prisms as PR  # noqa: E402  (the walls model as prisms; shared with the website)
M = PR.M

import numpy as np  # noqa: E402
import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402
import ifcopenshell.guid  # noqa: E402
import trimesh  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402


class Ifc:
    def __init__(self, name):
        f = self.f = ifcopenshell.api.run("project.create_file", version="IFC4")
        self.project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="NOMAD " + name)
        ifcopenshell.api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})
        ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
        self.body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                                         target_view="MODEL_VIEW", parent=ctx)
        site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="Barcelona")
        bldg = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name=name)
        self.storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Planta baixa")
        ifcopenshell.api.run("aggregate.assign_object", f, relating_object=self.project, products=[site])
        ifcopenshell.api.run("aggregate.assign_object", f, relating_object=site, products=[bldg])
        ifcopenshell.api.run("aggregate.assign_object", f, relating_object=bldg, products=[self.storey])
        self.count = {}

    def prism(self, ifc_class, name, pts, z0, h, spatial=False):
        f = self.f
        P = [f.createIfcCartesianPoint((float(x), float(y))) for x, y in pts] + [f.createIfcCartesianPoint((float(pts[0][0]), float(pts[0][1])))]
        prof = f.createIfcArbitraryClosedProfileDef("AREA", None, f.createIfcPolyline(P))
        place = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, float(z0))), None, None)
        solid = f.createIfcExtrudedAreaSolid(prof, place, f.createIfcDirection((0.0, 0.0, 1.0)), float(h))
        rep = f.createIfcShapeRepresentation(self.body, "Body", "SweptSolid", [solid])
        el = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class, name=name)
        el.Representation = f.createIfcProductDefinitionShape(None, None, [rep])
        el.ObjectPlacement = f.createIfcLocalPlacement(None, f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0)), None, None))
        if spatial:
            ifcopenshell.api.run("aggregate.assign_object", f, relating_object=self.storey, products=[el])
        else:
            ifcopenshell.api.run("spatial.assign_container", f, relating_structure=self.storey, products=[el])
        self.count[ifc_class] = self.count.get(ifc_class, 0) + 1
        return el

    def area_qto(self, el, area):
        q = ifcopenshell.api.run("pset.add_qto", self.f, product=el, name="Qto_SpaceBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", self.f, qto=q, properties={"NetFloorArea": round(float(area), 2)})


def export(case_name, k, shop, it):
    plan = it["plan"]
    pr = PR.prisms(shop, plan)
    ifc = Ifc("%s iteration %d" % (case_name, k))
    by_colour = {}                                              # glTF: one mesh + one material per colour
    for p in pr:
        kind, pts, z0, h, rgb = p["kind"], p["pts"], p["z0"], p["h"], tuple(p["rgb"])
        cls = {"wall": "IfcWall", "window": "IfcWindow", "slab": "IfcSlab", "door": "IfcDoor", "entry": "IfcDoor",
               "furniture": "IfcFurnishingElement"}.get(kind)
        if cls:
            ifc.prism(cls, {"entry": "street entry", "slab": "shop floor"}.get(kind, kind), pts, z0, h)
        g = Polygon(pts).buffer(0)
        for part in (g.geoms if g.geom_type == "MultiPolygon" else [g]):   # a self-touching outline splits in pieces
            if part.is_empty or part.area < 1e-6:
                continue
            poly = trimesh.creation.extrude_polygon(part, h)
            poly.apply_translation((0, 0, z0))
            by_colour.setdefault(rgb, []).append(poly)
    meshes = []
    for rgb, ms in by_colour.items():
        m_ = trimesh.util.concatenate(ms)
        alpha = 0.55 if rgb == tuple(M.GLASSC) else 1.0
        m_.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=[c / 255.0 for c in rgb] + [alpha], metallicFactor=0.0, roughnessFactor=0.9,
            alphaMode="BLEND" if alpha < 1 else "OPAQUE"))
        meshes.append(m_)
    for ui, u in enumerate(plan.get("units", [])):               # rooms as IfcSpace, full height
        for r in u["rooms"]:
            if len(r["pts"]) >= 3:
                el = ifc.prism("IfcSpace", "F%d %s" % (ui + 1, r.get("name", r["kind"])), r["pts"], 0.0, M.H_ROOM, spatial=True)
                el.LongName = r["kind"]
                ifc.area_qto(el, r.get("area", 0.0))
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "%s_it%d" % (case_name, k)
    ifc.f.write(str(OUT / (stem + ".ifc")))
    scene = trimesh.Scene()
    for m_ in meshes:
        # glTF is y-up: turn the z-up model
        m_.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0)))
        scene.add_geometry(m_)
    scene.export(str(OUT / (stem + ".glb")))
    return {"case": case_name, "iteration": k, "label": it["label"], "homes": it["homes"], "verdict": it["res"]["verdict"],
            "ifc": stem + ".ifc", "glb": stem + ".glb", "counts": ifc.count}


def main(names):
    names = names or sorted(p.stem for p in REC.glob("D*.json"))
    rows = []
    for n in names:
        case = json.load(open(REC / (n + ".json"), encoding="utf-8"))["case"]
        for k, it in enumerate(case.get("iterations", []), 1):
            if not it["plan"].get("units"):
                continue
            r = export(n, k, case["shop"], it)
            rows.append(r)
            print(r["ifc"], r["counts"])
    json.dump(rows, open(OUT / "summary.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
