"""NOMAD - shop data: one file for the shop shapes, the doors and the facts that the app shows (E44, 11 Nov 2026).

In the team repo the paths below are relative to nomad/02_Code (ROOT), like the other scripts here: the raw data lives in
nomad/02_Code/data on the computer that builds it (not in git; the CAT file in data/barcelona/catastro/CAT_files/), and
the outputs that say site/data go to ROOT/site/data; the files in nomad/06_Results/shops_doors_facts are the step 4 team
copy of them.

Read it top to bottom. It runs in five steps:

  STEP 0  UNITS     every unit of every building (floor, door, use, m2, year) from the Catastro CAT file
                    -> data/barcelona/catastro/units_cat.jsonl
  STEP 1  DOORS     building entrances (land registry addresses) + every premises door (city census 2024)
                    -> data/barcelona/catastro/entrances.json, site/data/doors.json
  STEP 2  SHAPES    each empty premises' shape cut to its true size, rule A or rule B (an ASSUMPTION, labelled)
                    -> site/data/cut_shells.json, results/real_shops/cut_report.json
  STEP 3  FACTS     what the census and the land registry say about each premises' building
                    -> site/data/facts/f_XX.json
  STEP 4  TEAM COPY (only when asked) the same data changed for the Catastro licence, for the team repo
                    -> the folder you give

Run everything:     .venv/Scripts/python src/building/shop_data.py
Run one step:       .venv/Scripts/python src/building/shop_data.py units | doors | shapes | facts
Team copy:          .venv/Scripts/python src/building/shop_data.py team <folder>

What it reads (all on this computer, not in git):
  results/real_shops/shells.json                 our shop shapes = each building's whole ground floor (Catastro footprint)
  site/data/premises.json                        the empty premises NOMAD answers for
  data/barcelona/census/2024_CensComercial_BCN.csv           city census of ground-floor premises 2024 (CC BY 4.0)
  data/barcelona/catastro/CAT_files/08900U_14082026.CAT.gz   Catastro CAT file, Barcelona urban (download licence; never committed)
  data/barcelona/catastro/buildings.json.gz      land registry building parts (floors above / below ground)
  data/barcelona/catastro/addresses/A.ES.SDGC.AD.08900.gml   land registry addresses (INSPIRE), from
      https://www.catastro.hacienda.gob.es/INSPIRE/Addresses/08/08900-BARCELONA/A.ES.SDGC.AD.08900.zip
"""
import gzip, json, math, sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
CENSUS = ROOT / "data/barcelona/census/2024_CensComercial_BCN.csv"
UNITS = ROOT / "data/barcelona/catastro/units_cat.jsonl"        # made by step 0 from the CAT file
BUILDINGS = ROOT / "data/barcelona/catastro/buildings.json.gz"
ADDRESSES = ROOT / "data/barcelona/catastro/addresses/A.ES.SDGC.AD.08900.gml"
SHELLS = ROOT / "results/real_shops/shells.json"
PREMISES = ROOT / "site/data/premises.json"
SITE = ROOT / "site/data"


# ======================================================================================================================
# Shared helpers: reading the inputs
# ======================================================================================================================

def read_census(cols):
    """The 2024 census, with "ref" = the 14-character cadastral reference of the building."""
    C = pd.read_csv(CENSUS, low_memory=False, usecols=["Referencia_Cadastral"] + [c for c in cols if c != "Referencia_Cadastral"])
    C["ref"] = C.Referencia_Cadastral.fillna("").astype(str).str[:14]
    return C


def read_units():
    """{ref14: {"ref", "n", "units": [{"car" unit number, "pt" floor code, "pu" door, "use", "m2", "year"}]}}
    From the CAT file (step 0), never from the Sede's Consulta_DNPRC web service (private use only)."""
    U = {}
    for line in open(UNITS, encoding="utf-8"):
        d = json.loads(line)
        U[d["ref"]] = d
    return U


# ======================================================================================================================
# STEP 0  UNITS from the Catastro CAT file (alphanumeric bulk download, Barcelona urban, 08900U_14082026.CAT.gz, accessed
#   2026-11-11; download licence: transformed data may be published (clause 6), never the original file online (5, 8);
#   cite the Dirección General del Catastro and the access date (12)). The file stays in CAT_files and is never committed.
#   Fixed width, one record a line (format "Fichero informático de remisión de catastro"):
#     record 15 (each unit / bien inmueble): parcel (31,14) · unit number (45,4) · floor (252,3) · door (255,3) ·
#               use letter (428,1) · built area with its share of common parts (442,10)
#     record 14 (each construction): parcel (31,14) · unit number (51,4) · year built (79,4)
#   The unit's year = the oldest year among its own constructions.
# ======================================================================================================================

CAT = ROOT / "data/barcelona/catastro/CAT_files/08900U_14082026.CAT.gz"
CAT_ACCESSED = "2026-11-11"
USE_LETTER = {"V": "Residencial", "C": "Comercial", "O": "Oficinas", "A": "Almacen-Estacionamiento", "I": "Industrial",
              "K": "Deportivo", "T": "Espectaculos", "G": "Ocio y Hosteleria", "Y": "Sanidad y Beneficencia",
              "E": "Cultural", "R": "Religioso", "M": "Obras de urbanizacion y jardineria, suelos sin edificar",
              "P": "Edificio singular", "B": "Almacen agrario", "J": "Industrial agrario", "Z": "Agrario"}


def cut(line, start, n):
    return line[start - 1:start - 1 + n].strip()


def step_units():
    keep = set(json.load(open(SHELLS, encoding="utf-8")))
    rows, c = read_premises()
    keep |= {(r[c("ref")] or "")[:14] for r in rows} - {""}
    units, years = defaultdict(list), defaultdict(list)
    import io
    for line in io.TextIOWrapper(gzip.open(CAT), encoding="latin-1"):
        kind, ref = line[:2], line[30:44]
        if ref not in keep:
            continue
        if kind == "15":
            try:
                m2 = float(cut(line, 442, 10) or 0)
            except ValueError:
                m2 = 0.0
            units[ref].append({"car": cut(line, 45, 4), "pt": cut(line, 252, 3), "pu": cut(line, 255, 3),
                               "use": USE_LETTER.get(cut(line, 428, 1), cut(line, 428, 1)), "m2": m2 or None})
        elif kind == "14" and cut(line, 51, 4):
            y = cut(line, 79, 4)
            if y.isdigit() and y != "0000":
                years[(ref, cut(line, 51, 4))].append(y)
    with open(UNITS, "w", encoding="utf-8") as f:
        for ref in sorted(units):
            us = units[ref]
            for u in us:
                y = years.get((ref, u["car"]))
                u["year"] = min(y) if y else None
            f.write(json.dumps({"ref": ref, "n": len(us), "units": us, "source": "CAT %s" % CAT_ACCESSED}, ensure_ascii=False) + "\n")
    print("buildings with units:", len(units), " units:", sum(len(v) for v in units.values()))


def read_premises():
    """The premises rows and a column finder: c("ref") gives that column's position."""
    P = json.load(open(PREMISES, encoding="utf-8"))
    return P["rows"], P["cols"].index


# ======================================================================================================================
# STEP 1  DOORS
#   entrances  land registry address points marked "Entrance" (the building's street door for that street number),
#              matched to the building by the cadastral reference at the end of the address id
#   doors      every premises of the building in the census (empty or in use): its door point
#   Both in the shape's local metres (same origin as the outline); "o" = that origin in UTM.
# ======================================================================================================================

AD = "urn:x-inspire:specification:gmlas:Addresses:3.0"
GMLNS = "http://www.opengis.net/gml/3.2"
BASE = "urn:x-inspire:specification:gmlas:BaseTypes:3.2"


def read_addresses():
    """{ref14: [[x_utm, y_utm, street number, "Entrance" | "Parcel"], ...]} from the land registry address file."""
    out = defaultdict(list)
    for _, el in ET.iterparse(ADDRESSES, events=("end",)):
        if el.tag != "{%s}Address" % AD:
            continue
        lid = el.findtext(".//{%s}localId" % BASE) or ""
        ref = lid.split(".")[-1][:14]
        pos = el.findtext(".//{%s}pos" % GMLNS)
        spec = el.findtext(".//{%s}specification" % AD) or ""
        num = next((d.text for d in el.iter("{%s}designator" % AD) if d.text and d.text.strip()), "")
        if pos and len(ref) == 14:
            x, y = map(float, pos.split()[:2])
            out[ref].append([round(x, 2), round(y, 2), num.strip(), spec])
        el.clear()
    return out


def step_doors():
    E = read_addresses()
    json.dump(E, open(ROOT / "data/barcelona/catastro/entrances.json", "w", encoding="utf-8"), separators=(",", ":"))
    print("buildings with an address point:", len(E), " entrance points:", sum(1 for v in E.values() for p in v if p[3] == "Entrance"))
    S = json.load(open(SHELLS, encoding="utf-8"))
    C = read_census(["X_UTM_ETRS89", "Y_UTM_ETRS89", "Codi_Principal_Activitat"])
    C = C[C.ref.isin(S.keys())]
    out, n_e = {}, 0
    for ref, s in S.items():
        x0, y0 = s["origin_utm"]
        entr = [[round(x - x0, 2), round(y - y0, 2), num] for x, y, num, spec in E.get(ref, []) if spec == "Entrance"]
        n_e += bool(entr)
        doors = []
        for _, r in C[C.ref == ref].iterrows():
            if math.isnan(r.X_UTM_ETRS89):
                continue
            p = [round(r.X_UTM_ETRS89 - x0, 2), round(r.Y_UTM_ETRS89 - y0, 2), "active" if r.Codi_Principal_Activitat == 1 else "empty"]
            if not any(math.hypot(p[0] - q[0], p[1] - q[1]) < 0.5 and p[2] == q[2] for q in doors):
                doors.append(p)
        out[ref] = {"o": [x0, y0], "entr": entr, "doors": doors}
    json.dump(out, open(SITE / "doors.json", "w", encoding="utf-8"), separators=(",", ":"))
    print("modelled buildings:", len(S), " with a building entrance:", n_e, " shop doors:", sum(len(v["doors"]) for v in out.values()))


# ======================================================================================================================
# STEP 2  SHAPES (checklist item 2). Every cut is an ASSUMPTION and is labelled in the app.
#   Our shop shape = the building's whole ground floor. The land registry gives the true built area of each ground-floor
#   unit. Shop units = ground-floor units ('0', '00', 'BJ') of 15 m2 or more that are not homes or parking/storage.
#
#   Rule A  one shop unit: when the shape is more than 15 % bigger than the unit, keep the part behind its door on its
#           street facade (narrower, centred on the door, when the front is long) until the area equals the unit's m2.
#   Rule B  2 or more shop units: the street front is shared out between the premises doors (census, every premises of
#           the building, empty or in use): each door gets the stretch of facade halfway to its neighbours (to the
#           building corner at the ends); its depth from the street gives it its share of the shop units' total m2
#           (share = its stretch / the whole front), kept between the smallest and largest unit's m2 (one premises = one
#           unit); when that is shallower than 4 m the stretch is narrowed round the door.
#   No shop unit / no unit list / no street facade: the shape stays the footprint.
#   In the app a premises' own land registry unit plan (site/data/unit_shells.json) still comes first.
# ======================================================================================================================

GROUND = ("0", "00", "BJ")                        # ground-floor codes in the land registry
NOT_SHOP = ("Residencial", "Almacen-Estacionamiento")
MIN_UNIT = 15.0       # m2: smaller units are not shops
OVER = 1.15           # rule A only when the shape is more than 15 % bigger than the unit
DOOR_TO_FRONT = 8.0   # m: a census door belongs to a street facade within 8 m
MIN_W = 2.5           # m: no cut narrower than this (a room needs it)
MIN_DEPTH = 4.0       # m: a cut shallower than this over its stretch is made narrower instead ...
GOOD_DEPTH = 8.0      # m: ... with a depth of about 8 m


def shop_units(rec):
    return [u for u in (rec.get("units") or []) if u["pt"] in GROUND and (u["m2"] or 0) >= MIN_UNIT and u["use"] not in NOT_SHOP]


def depth_cut(shape, band, target):
    """Grow band(d) ∩ shape until its area reaches the target (binary search on the depth d)."""
    lo, hi = 0.5, 80.0
    full = shape.intersection(band(hi))
    if full.area <= target:
        return full
    for _ in range(30):
        mid = (lo + hi) / 2
        if shape.intersection(band(mid)).area < target:
            lo = mid
        else:
            hi = mid
    return shape.intersection(band(hi))


def biggest(g):
    """The largest polygon of a geometry (a cut can fall into pieces)."""
    if g.geom_type == "Polygon":
        return g
    polys = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    return max(polys, key=lambda p: p.area) if polys else None


def ring(g):
    return [[round(x, 2), round(y, 2)] for x, y in list(g.exterior.coords)[:-1]]


def edges_on(g, segs, tol=0.25):
    """Outline edges of g lying on the given street segments (they stay the street facade)."""
    lines = unary_union([LineString(s) for s in segs]).buffer(tol)
    pts = list(g.exterior.coords)
    return [[[round(a[0], 2), round(a[1], 2)], [round(b[0], 2), round(b[1], 2)]] for a, b in zip(pts, pts[1:])
            if LineString([a, b]).length > 0.3 and lines.contains(LineString([a, b]))]


def keep_inside(polys, g):
    """Light wells / portal polygons that still touch the cut."""
    return [q for q in polys or [] if len(q) >= 3 and Polygon(q).buffer(0).intersects(g)]


def step_shapes():
    S = json.load(open(SHELLS, encoding="utf-8"))
    U = read_units()
    rows, c = read_premises()
    C = read_census(["X_UTM_ETRS89", "Y_UTM_ETRS89"])
    doors = defaultdict(list)                           # every census door of each building, 1 m apart at least
    for ref, x, y in zip(C.ref, C.X_UTM_ETRS89, C.Y_UTM_ETRS89):
        if ref and not (math.isnan(x) or math.isnan(y)) and not any(math.hypot(x - a, y - b) < 1.0 for a, b in doors[ref]):
            doors[ref].append((x, y))

    out, n = {}, Counter()
    for r in rows:
        ref = (r[c("ref")] or "")[:14]
        s = S.get(ref)
        if not s:
            continue
        key = "%s|%s|%s" % (ref, r[c("x")], r[c("y")])
        rec = U.get(ref)
        if not rec or not rec.get("units"):
            n["no unit list: footprint kept"] += 1
            continue
        units = shop_units(rec)
        if not units:
            n["no shop unit on the ground floor: footprint kept"] += 1
            continue
        g = biggest(Polygon(s["outline"]).buffer(0))
        if g is None or not s.get("street"):
            n["no street facade: footprint kept"] += 1
            continue
        total = sum(u["m2"] for u in units)
        x0, y0 = s["origin_utm"]
        segs = s["street"]
        door = Point(r[c("x")] - x0, r[c("y")] - y0)
        if g.exterior.distance(door) > DOOR_TO_FRONT and not g.contains(door):
            n["census door more than 8 m from the building: footprint kept"] += 1
            continue

        # the street facade nearest the door, and a frame along it: u along the street, v into the building
        seg = min(segs, key=lambda q: LineString(q).distance(door))
        (ax, ay), (bx, by) = seg
        L = math.hypot(bx - ax, by - ay)
        if L < 1.0:
            n["street facade too short: footprint kept"] += 1
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        if not g.contains(Point(ax + (bx - ax) / 2 + 0.5 * nx, ay + (by - ay) / 2 + 0.5 * ny)):
            nx, ny = -nx, -ny
        t = min(max((door.x - ax) * ux + (door.y - ay) * uy, 0.0), L)      # the door's place along the facade

        def band(d, u0, u1, m=(ux, nx, uy, ny, ax, ay)):      # the strip u0..u1 along the street, d deep -> local metres
            return affinity.affine_transform(box(u0, -0.5, u1, d), m)

        def around(w):                                          # a stretch of width w centred on the door, inside the front
            w = min(w, L)
            u0 = min(max(0.0, t - w / 2), L - w)
            return u0, u0 + w

        if len(units) == 1:                                     # ---- rule A ----
            want = units[0]["m2"]
            if g.area <= OVER * want:
                n["A: shape already fits its unit"] += 1
                continue
            u0, u1 = 0.0, L
            if want / L < MIN_DEPTH:                            # a long front and a small unit: narrower, centred on the door
                u0, u1 = around(max(MIN_W, want / GOOD_DEPTH))
            rule, why = "A", ("one shop unit in the Catastro (%d m2): the part behind its door kept, %.1f m of street front, "
                              "as deep as its area" % (round(want), u1 - u0))
        else:                                                   # ---- rule B ----
            line = LineString(seg)
            here = sorted({round((p[0] - x0 - ax) * ux + (p[1] - y0 - ay) * uy, 2)
                           for p in doors.get(ref, []) if line.distance(Point(p[0] - x0, p[1] - y0)) <= DOOR_TO_FRONT})
            if not here or min(abs(t - h) for h in here) > 1.0:
                here = sorted(here + [round(t, 2)])
            i = min(range(len(here)), key=lambda k: abs(here[k] - t))
            front = sum(LineString(q).length for q in segs)    # every street front of the building counts for the shares
            if len(here) == 1:                                  # the only door on this front: it shares the front by the unit count
                u0, u1 = around(max(MIN_W, front / len(units)))
            else:                                               # halfway to the neighbouring doors
                u0 = 0.0 if i == 0 else max(0.0, (here[i - 1] + here[i]) / 2)
                u1 = L if i == len(here) - 1 else min(L, (here[i] + here[i + 1]) / 2)
                if u1 - u0 < MIN_W:
                    u0, u1 = around(MIN_W)
            want = total * (u1 - u0) / front
            lo_m2, hi_m2 = min(u["m2"] for u in units), max(u["m2"] for u in units)
            want = min(max(want, lo_m2), hi_m2)                # one premises = one unit: its area stays within the units' range
            if want / (u1 - u0) < MIN_DEPTH:                    # too shallow over its stretch: narrower, centred on the door
                u0, u1 = around(max(MIN_W, want / GOOD_DEPTH))
            rule = "B"
            why = ("%d shop units share this ground floor (%d m2 in all); this premises takes "
                   "%.1f m of the street front at its door and an area within the units' sizes (%d-%d m2)"
                   % (len(units), round(total), u1 - u0, round(lo_m2), round(hi_m2)))

        cut = biggest(depth_cut(g, lambda d: band(d, u0, u1), want))
        if cut is not None and cut.buffer(-MIN_W / 2).is_empty:
            n[rule + ": cut narrower than %.1f m: footprint kept" % MIN_W] += 1
            continue
        if cut is None or cut.area < 15:
            n[rule + ": cut too small: footprint kept"] += 1
            continue
        cut = cut.simplify(0.05, preserve_topology=True)
        street = edges_on(cut, segs)
        if not street:
            n[rule + ": cut lost its street facade: footprint kept"] += 1
            continue
        out[key] = {"outline": ring(cut), "facade": street, "street": street, "m2": round(cut.area),
                    "rule": rule, "why": why, "units": len(units),
                    "patios": keep_inside(s.get("patios"), cut), "existing": keep_inside(s.get("existing"), cut)}
        n[rule + ": cut"] += 1
    json.dump(out, open(SITE / "cut_shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    json.dump(dict(n), open(ROOT / "results/real_shops/cut_report.json", "w", encoding="utf-8"), indent=1)
    for k, v in sorted(n.items()):
        print("%6d  %s" % (v, k))
    print("cut shapes:", len(out))


# ======================================================================================================================
# STEP 3  FACTS for the app panel (Find your shop > Show the details)
#   census, every premises in the building: [x, y, address, "empty" | "active", sector / offer, activity, flags]
#       flags: street / market:<name> / gallery:<name> / centre:<name> / axis:<shopping street> / night / 24h /
#              coworking / tasting
#   land registry: year built (the year most of its units carry), every unit [floor, use, m2]
#   building parts: floors above and below ground (highest part)
#   Split into small files by the first two characters of the reference, so the app loads only one.
# ======================================================================================================================

FACT_COLS = ["X_UTM_ETRS89", "Y_UTM_ETRS89", "Codi_Principal_Activitat", "Nom_Sector_Activitat", "Nom_Grup_Activitat",
             "Nom_Activitat", "Num_Policia_Inicial", "Lletra_Inicial", "Num_Policia_Final", "Nom_Via",
             "SN_Carrer", "SN_Mercat", "Nom_Mercat", "SN_Galeria", "Nom_Galeria", "SN_CComercial", "Nom_CComercial",
             "SN_Eix", "Nom_Eix", "SN_Oci_Nocturn", "SN_Obert24h", "SN_Coworking", "SN_Servei_Degustacio"]


def text(v):
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v).strip()


def flags(r):
    f = []
    if r.SN_Carrer == "Si": f.append("street")
    if r.SN_Mercat == "Si": f.append("market:" + text(r.Nom_Mercat))
    if r.SN_Galeria == "Si": f.append("gallery:" + text(r.Nom_Galeria))
    if r.SN_CComercial == "Si": f.append("centre:" + text(r.Nom_CComercial))
    if r.SN_Eix == "Si": f.append("axis:" + text(r.Nom_Eix))
    if r.SN_Oci_Nocturn == "Si": f.append("night")
    if r.SN_Obert24h == "Si": f.append("24h")
    if r.SN_Coworking == "Si": f.append("coworking")
    if r.SN_Servei_Degustacio == "Si": f.append("tasting")
    return f


def step_facts():
    rows, c = read_premises()
    refs = {(r[c("ref")] or "")[:14] for r in rows} - {""}
    C = read_census(FACT_COLS)
    C = C[C.ref.isin(refs)]
    out = {r: {"c": []} for r in refs}
    for r in C.itertuples():
        num = text(r.Num_Policia_Inicial).split(".")[0] + text(r.Lletra_Inicial)
        if text(r.Num_Policia_Final):
            num += "-" + text(r.Num_Policia_Final).split(".")[0]
        empty = r.Codi_Principal_Activitat == 0
        out[r.ref]["c"].append([round(r.X_UTM_ETRS89), round(r.Y_UTM_ETRS89), text(r.Nom_Via) + " " + num, "empty" if empty else "active",
                                text(r.Nom_Sector_Activitat), "" if empty else text(r.Nom_Activitat) or text(r.Nom_Grup_Activitat), flags(r)])
    for ref, d in read_units().items():
        if ref not in out or not d.get("units"):
            continue
        us = d["units"]
        years = Counter(u.get("year") for u in us if u.get("year"))
        out[ref]["y"] = years.most_common(1)[0][0] if years else None
        out[ref]["u"] = [[u["pt"], u["use"], u["m2"]] for u in us]
    B = json.load(gzip.open(BUILDINGS, "rt", encoding="utf-8"))
    for ref, v in out.items():
        b = B.get(ref)
        if b and b.get("parts"):
            v["up"] = max((p["up"] or 0) for p in b["parts"])
            v["down"] = max((p["down"] or 0) for p in b["parts"])
    D = SITE / "facts"
    D.mkdir(exist_ok=True)
    by = {}
    for ref, v in out.items():
        by.setdefault(ref[:2], {})[ref] = v
    for k, v in by.items():
        json.dump(v, open(D / ("f_%s.json" % k), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("buildings:", len(out), " with census rows:", sum(bool(v["c"]) for v in out.values()),
          " with units:", sum("u" in v for v in out.values()), " files:", len(by),
          " largest KB:", max(f.stat().st_size for f in D.glob("f_*.json")) // 1000)


# ======================================================================================================================
# STEP 4  TEAM COPY (only when asked). The Catastro licence allows only transformed data online, and the team shows no
#   unit areas: outlines and points rounded to 0,5 m, cut areas to 10 m2, reasons without unit sizes, unit lists
#   reduced to the number of units by use (no areas, no year, no floor list). The census stays as it is (CC BY 4.0).
# ======================================================================================================================

def step_team(folder):
    D = Path(folder)
    (D / "facts").mkdir(parents=True, exist_ok=True)
    r5 = lambda v: round(v * 2) / 2
    r10 = lambda v: int(round(v / 10.0) * 10)
    C = json.load(open(SITE / "cut_shells.json", encoding="utf-8"))
    for v in C.values():
        v["outline"] = [[r5(x), r5(y)] for x, y in v["outline"]]
        v["facade"] = v["street"] = [[[r5(a[0]), r5(a[1])], [r5(b[0]), r5(b[1])]] for a, b in v["street"]]
        v["m2"] = r10(v["m2"])
        v["why"] = ("one shop unit on the ground floor in the Catastro: the part behind its door kept, as deep as the unit's area"
                    if v["rule"] == "A" else
                    "%d shop units share the ground floor: this premises takes a stretch of the street front at its census door "
                    "and an area within the units' sizes" % v["units"])
        v.pop("existing", None)
    json.dump(C, open(D / "cut_shells.json", "w", encoding="utf-8"), separators=(",", ":"))
    Dd = json.load(open(SITE / "doors.json", encoding="utf-8"))
    for v in Dd.values():
        v["entr"] = [[r5(x), r5(y), n] for x, y, n in v["entr"]]
        v["doors"] = [[r5(x), r5(y), k] for x, y, k in v["doors"]]
    json.dump(Dd, open(D / "doors.json", "w", encoding="utf-8"), separators=(",", ":"))
    for f in (SITE / "facts").glob("f_*.json"):
        F = json.load(open(f, encoding="utf-8"))
        for v in F.values():
            u = v.pop("u", None)
            v.pop("y", None)                                    # the year and the floor list stay out: too close to the file
            if u:
                v["n"] = dict(Counter(use for _, use, _ in u))     # only the number of units by use
        json.dump(F, open(D / "facts" / f.name, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("team copy written to", D)


# ======================================================================================================================

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "units"):
        print("== STEP 0 UNITS (CAT file)"); step_units()
    if what in ("all", "doors"):
        print("== STEP 1 DOORS"); step_doors()
    if what in ("all", "shapes"):
        print("== STEP 2 SHAPES"); step_shapes()
    if what in ("all", "facts"):
        print("== STEP 3 FACTS"); step_facts()
    if what == "team":
        print("== STEP 4 TEAM COPY"); step_team(sys.argv[2])
