"""Nomad - the Catastro CAT file: each premises' own area and use on the ground floor, to split shared ground floors.

The INSPIRE buildings (catastro_buildings.py) give each building's outline and floors, but not which part of the ground
floor is which shop: 389 of the clean real shops share their ground floor with other premises (clean_real_shops.py label).
The Catastro's alphanumeric CAT file lists every building space (record type 14) with its floor, door, use code and m².
The CAT file is free but needs a request on the Sede Electrónica del Catastro ("Descarga de información alfanumérica",
formato CAT, municipality 08900 Barcelona), so it is NOT downloaded by a script: save it by hand into
data/barcelona/catastro/CAT_files/ (the .CAT, or the .zip / .gz it comes in - read in place, never unpacked).

Record layout (fixed width, 1-based start, length) = the official CAT format, as used by hypercadaster_ES
(BeeGroup-cimne, EUPL-1.2, downloaders.catstruct[14]); only the fields NOMAD needs are read.
Out: results/real_shops/cat_ground_floor.json {ref14: [{"floor", "door", "use", "m2"}]} and a line in the summary.
Run: .venv/Scripts/python src/building/cat_file.py
"""
import gzip
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT_DIR = ROOT / "data" / "barcelona" / "catastro" / "CAT_files"
OUT = ROOT / "results" / "real_shops" / "cat_ground_floor.json"

F14 = {"ref14": (31, 14), "floor": (65, 3), "door": (68, 3), "use": (71, 3), "m2": (84, 7)}   # record type 14 fields
GROUND = {"00", "0", "BJ", "PB", "B"}                         # floor names used for the ground floor ("baixos")


def lines():
    """Every line of the CAT file(s) in CAT_DIR, read in place (plain, .gz or .zip). Catastro files are ISO-8859-1."""
    files = sorted(p for p in CAT_DIR.glob("*") if p.suffix.lower() in (".cat", ".gz", ".zip"))
    if not files:
        raise SystemExit("No CAT file in %s. Download Barcelona's CAT file (Sede Electronica del Catastro, alphanumeric "
                         "data, CAT format) and save it there." % CAT_DIR)
    for p in files:
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.upper().endswith(".CAT"):
                        yield from io.TextIOWrapper(z.open(n), encoding="latin-1")
        elif p.suffix.lower() == ".gz":
            yield from io.TextIOWrapper(gzip.open(p), encoding="latin-1")
        else:
            yield from open(p, encoding="latin-1")


def field(line, k):
    a, n = F14[k]
    return line[a - 1:a - 1 + n].strip()


def main():
    keep = None
    shells = ROOT / "results" / "real_shops" / "shells.json"
    if shells.exists():                                        # only the buildings NOMAD has a shop in
        keep = set(json.load(open(shells, encoding="utf-8")))
    ground, n14 = defaultdict(list), 0
    for line in lines():
        if line[:2] != "14":
            continue
        n14 += 1
        ref = field(line, "ref14")
        if keep is not None and ref not in keep:
            continue
        fl = field(line, "floor").lstrip("0") or "0"
        if fl not in GROUND and field(line, "floor") not in GROUND:
            continue
        try:
            m2 = float(field(line, "m2") or 0)
        except ValueError:
            continue
        if m2 <= 0:
            continue
        ground[ref].append({"floor": field(line, "floor"), "door": field(line, "door"), "use": field(line, "use"), "m2": m2})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(ground, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    shared = sum(1 for v in ground.values() if len(v) > 1)
    print("type-14 spaces read:", n14, "| buildings with ground-floor spaces:", len(ground), "| shared ground floors:", shared)


if __name__ == "__main__":
    main()
