"""Nomad - clean the real Barcelona shops before NOMAD uses them (as clean_dataset.py does for the Swiss shops).

Input: 2_building/output/real_shops/empty_shops_buildings.csv + shells.json (2_building/code/real_shops.py).
Data errors (removed, with the reason):
  door far from building   the census door point is more than 15 m from the Catastro building of its reference:
                           the reference or the location is wrong
  not one premises         the ground floor is over 3,000 m²: a whole block, market or complex, not a shop
  door far from façade     the building has street façades but the door is more than 20 m from all of them: the
                           premises sits in another part of a large building, so the outline is not this shop's
Kept but labelled (they are answers, not errors):
  under 40 m²              too small for one Barcelona dwelling (MPGM 2004 DA1 2.a): NO without a plan
  façade under 3 m         under the Barcelona minimum façade (MPGM 2004 DA1 2.b): NO without a plan
  shares the ground floor  other premises share the building's ground floor: the outline is the whole floor; the
                           Catastro CAT file is needed to cut out this premises
Outlines with more than 60 corners are simplified to 0,30 m (drawing noise). The kept shops that are alone in their
building, in a zone that admits housing, with 40 m² and 3 m of façade, are the ones NOMAD runs on.
Out: 2_building/output/real_shops/clean_shops.csv (every shop, kept / reason / group), cleaning_report.json; shells.json updated.
Run: .venv/Scripts/python 2_building/code/clean_real_shops.py
"""
import json
from pathlib import Path
import pandas as pd
from shapely.geometry import Polygon, Point, LineString

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "2_building/output/real_shops"


def main():
    S = json.load(open(D / "shells.json", encoding="utf-8"))
    m = pd.read_csv(D / "empty_shops_buildings.csv")
    door_b, door_f, simplified = [], [], 0
    for _, r in m.iterrows():
        s = S[r.ref14]
        ox, oy = s["origin_utm"]
        P = Polygon(s["outline"])
        if len(s["outline"]) > 60 and not s.get("simplified"):
            q = P.simplify(0.30, preserve_topology=True)
            s["outline"] = [[round(x, 2), round(y, 2)] for x, y in q.exterior.coords]
            s["simplified"] = True
            simplified += 1
            P = q
        door = Point(r.X_UTM_ETRS89 - ox, r.Y_UTM_ETRS89 - oy)
        door_b.append(0.0 if P.contains(door) else round(P.exterior.distance(door), 1))
        st = [LineString(e) for e in s["street"]]
        door_f.append(round(min(l.distance(door) for l in st), 1) if st else None)
    m["door_to_building_m"], m["door_to_street_facade_m"] = door_b, door_f
    reason = []
    for _, r in m.iterrows():
        if r.door_to_building_m > 15:
            reason.append("door far from building")
        elif r.ground_m2 > 3000:
            reason.append("not one premises")
        elif r.street_facade_m >= 0.5 and r.door_to_street_facade_m is not None and r.door_to_street_facade_m > 20:
            reason.append("door far from façade")
        else:
            reason.append("")
    m["removed"] = reason
    m["kept"] = m.removed == ""
    m["label"] = ""
    m.loc[m.kept & (m.ground_m2 < 40), "label"] = "under 40 m²"
    m.loc[m.kept & (m.label == "") & (m.street_facade_m + m.open_facade_m < 3), "label"] = "façade under 3 m"
    m.loc[m.kept & (m.label == "") & (m.premises_in_building > 1), "label"] = "shares the ground floor"
    m["nomad_runs"] = m.kept & (m.label == "") & (m.housing == "YES")
    m.to_csv(D / "clean_shops.csv", index=False, encoding="utf-8")
    json.dump(S, open(D / "shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    rep = {"shops_in": int(len(m)), "removed": m[~m.kept].removed.value_counts().to_dict(), "kept": int(m.kept.sum()),
           "labelled": m[m.kept].label.replace("", "ready").value_counts().to_dict(), "outlines_simplified": simplified,
           "nomad_runs_on": int(m.nomad_runs.sum()),
           "nomad_runs_on_by_district": m[m.nomad_runs].Nom_Districte.value_counts().to_dict()}
    json.dump(rep, open(D / "cleaning_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
