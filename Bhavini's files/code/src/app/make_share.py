"""NOMAD - a SAFE TO SHARE copy of the app, in its own folder. The app itself (site/) is only read, never changed.

Why: some data in the app may only be used privately (Catastro Sede legal notice: "download and private use"), and the
CAT file's numbers may only be published transformed (download licence clauses 5, 6, 8). This copy leaves those out.

  Private-use sources, removed or replaced:
    1. "The building" floor-by-floor plans (Sede Visor 3D, site/data/catastro/b_XX.json, source "units")
       -> rebuilt from the INSPIRE building parts (outline of each part, floors above / below), as for every other building
    2. the premises' own unit outline (Visor 3D, site/data/unit_shells.json, unit_skips.json) -> empty
    3. the building's existing portal / stair ("existing" in shells.json and cut_shells.json, Visor 3D) -> removed
    4. the facade read from the Catastro facade photo (site/data/facades.json) -> empty
  CAT file numbers, transformed:
    5. unit lists in facts/f_XX.json -> the number of units by use only (no areas, years or floor lists);
       cut shapes: outlines rounded to 0,5 m, areas to 10 m2, reasons without unit sizes
  INSPIRE numbers, rounded as the team site does: warehouses' built and ground areas to 10 m2.
Everything else is copied as it is (census CC BY 4.0, MUC zoning, ICGC LiDAR, INSPIRE-derived city and outlines, Swiss
Dwellings / ResPlan plans CC BY 4.0, idealista18 prices ODbL with credit, the daylight model, the laws).

Out: site_share/ (a full copy of site/ with the changes above), and site_share/SHARE_NOTES.txt
Run: .venv/Scripts/python src/app/make_share.py
"""
import gzip, json, shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "site"
OUT = ROOT / "site_share"
r5 = lambda v: round(v * 2) / 2
r10 = lambda v: int(round(v / 10.0) * 10)


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, d):
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def buildings_from_parts(D):
    """1. every building bundle from the INSPIRE building parts (as src/zoning/catastro_site.py does for buildings
    without a floor plan); the Visor 3D floor plans and its address text are dropped."""
    B = json.load(gzip.open(ROOT / "data/barcelona/catastro/buildings.json.gz", "rt", encoding="utf-8"))
    n = Counter()
    for f in (D / "catastro").glob("b_*.json"):
        d = load(f)
        for ref, v in list(d.items()):
            if v.get("source") != "units":
                n["kept (INSPIRE)"] += 1
                continue
            b = B.get(ref)
            parts = [{"up": p.get("up") or 0, "down": p.get("down") or 0, "rings": [r[0] for r in p["poly"]]} for p in (b or {}).get("parts", [])]
            allp = [q for p in parts for r in p["rings"] for q in r]
            if not allp:
                del d[ref]; n["Visor plan removed, no INSPIRE parts"] += 1
                continue
            x0, y0 = min(q[0] for q in allp), min(q[1] for q in allp)
            d[ref] = {"ref": ref, "use": v.get("use", ""), "dwellings": v.get("dwellings", 0), "units_n": v.get("units_n", 0),
                      "source": "building", "origin": [round(x0, 1), round(y0, 1)], "address": "",
                      "parts": [{"up": p["up"], "down": p["down"], "pts": [[round(x - x0, 1), round(y - y0, 1)] for x, y in r]}
                                for p in parts for r in p["rings"]]}
            n["Visor plan replaced by INSPIRE parts"] += 1
        save(f, d)
    return n


def main():
    if OUT.exists():
        shutil.rmtree(OUT)                                       # the copy only, rebuilt each time
    shutil.copytree(SRC, OUT)
    D = OUT / "data"
    notes = []

    notes.append("1. building plans: %s" % dict(buildings_from_parts(D)))

    save(D / "unit_shells.json", {}); save(D / "unit_skips.json", {})
    notes.append("2. unit_shells.json and unit_skips.json emptied (Visor 3D)")

    S = load(D / "shells.json")
    k = sum(1 for v in S.values() if v.pop("existing", None))
    save(D / "shells.json", S)
    C = load(D / "cut_shells.json")
    for v in C.values():
        v.pop("existing", None)
        v["outline"] = [[r5(x), r5(y)] for x, y in v["outline"]]
        v["facade"] = v["street"] = [[[r5(a[0]), r5(a[1])], [r5(b[0]), r5(b[1])]] for a, b in v["street"]]
        v["m2"] = r10(v["m2"])
        v["why"] = ("one shop unit on the ground floor in the Catastro: the part behind its door kept, as deep as the unit's area"
                    if v["rule"] == "A" else
                    "%d shop units share the ground floor: this premises takes a stretch of the street front at its door "
                    "and an area within the units' sizes" % v["units"])
    save(D / "cut_shells.json", C)
    notes.append("3. existing portal / stair removed from %d shop outlines and every cut shape (Visor 3D); cut shapes rounded" % k)

    save(D / "facades.json", {})
    notes.append("4. facades.json emptied (Catastro facade photo)")

    m = 0
    for f in (D / "facts").glob("f_*.json"):
        F = load(f)
        for v in F.values():
            u = v.pop("u", None)
            v.pop("y", None)
            if u:
                v["n"] = dict(Counter(use for _, use, _ in u)); m += 1
        save(f, F)
    notes.append("5. facts: unit lists of %d buildings reduced to counts by use (no areas, years, floor lists)" % m)

    W = load(D / "warehouses.json")
    c = W["cols"].index
    for r in W["rows"]:
        for col in ("built_m2", "ground_m2"):
            if r[c(col)] is not None:
                r[c(col)] = r10(r[c(col)])
    save(D / "warehouses.json", W)
    notes.append("6. warehouses: built and ground areas rounded to 10 m2")

    page(OUT / "index.html")
    notes.append("7. page: the facts panel shows unit counts by use; sources name the transformed data")
    (OUT / "SHARE_NOTES.txt").write_text("NOMAD safe-to-share copy, made by src/app/make_share.py from site/.\n" + "\n".join(notes) + "\n", encoding="utf-8")
    print("\n".join(notes))


def page(p):
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")

    # the facts panel: unit counts by use instead of the unit list
    a = s.index('      ${units.length ? `<dt>UNITS</dt>')
    b = s.index("</dl>", a)
    s = s[:a] + '''      ${f.n ? `<dt>UNITS</dt><dd>${Object.values(f.n).reduce((x, y) => x + y, 0)}: ${Object.entries(f.n).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${v} × ${esc(USE_EN[k] || k)}`).join(" · ")}</dd>` : `<dt>UNITS</dt><dd>no unit list in the land registry</dd>`}''' + s[b:]
    old = "NOMAD's reading of data from the Dirección General del Catastro: units from the alphanumeric CAT file (accessed 11 Nov 2026), building parts and addresses from INSPIRE. Built year = the year most of its units carry."
    assert s.count(old) == 1, "sources line not found"
    s = s.replace(old, "NOMAD's reading of data from the Dirección General del Catastro (accessed 11 Nov 2026): the number of units by use from the alphanumeric CAT file, building parts and addresses from INSPIRE, transformed by NOMAD; not Catastro information.")
    s = s.replace("Floor plans of each floor: The building, below.", "The outline of each floor: The building, below.")
    s = s.replace("<html", "<!-- NOMAD safe-to-share copy (src/app/make_share.py): private-use Catastro data left out -->\n<html", 1) if "<html" in s else \
        "<!-- NOMAD safe-to-share copy (src/app/make_share.py): private-use Catastro data left out -->\n" + s
    p.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


if __name__ == "__main__":
    main()
