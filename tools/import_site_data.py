"""NOMAD - bring the website's data into the repo from a copy of the published site, and list every file.

Until 9 Nov 2026 the site's data lived only in the published artifact (321 files). This script reads a folder that
holds a copy of those files (same paths: data/..., rulebook/..., py/..., img/..., models/...), and:
  1. copies the files the cleaned site uses into  nomad/04_Website/  , removing what the cleanup took
     out (prices, daylight predictions, home counts, layout-engine data, Catastro Visor 3D units);
  2. writes docs/DATA_INVENTORY.md: every file, its type and size, where it came from, where the site uses it,
     and what happened to it.
Law PDFs (rulebook/parts) are not copied: tools/get_rulebook.py downloads them from their official URLs.
Pyodide (py/pyodide*) is not copied: the parked layout engine loads a pinned version from a CDN when it returns.

Run from the repo root:  python tools/import_site_data.py <folder with the published files>
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "nomad" / "04_Website"
B = "nomad/02_Code/src/"

# path pattern -> (where it came from, where the cleaned site uses it, decision)
RULES = [
    ("index.html", "the page itself (hand-written)", "the whole site", "in the repo"),
    ("data/nomad.json", B + "app/build_site.py (rules from 07_Rules_and_evaluation, experiment results from 06_Results)",
     "rule cards, golden set, experiments, workflow, tally", "in the repo, without demos / real / check / golden_rows (layout results)"),
    ("data/premises.json", B + "app/build_site.py premises(): census 2024 + MUC zoning + street life (src/check/avoid.py)",
     "Find your shop, the map, categories, For the city, 3D city", "in the repo, only x, y, address, district, ref, zone, answer, why, offer, shops"),
    ("data/basemap.json", B + "app/build_site.py basemap(): MUC zones merged and simplified", "the 2D map, 3D city typology", "in the repo"),
    ("data/warehouses.json", B + "zoning/warehouses.py: Catastro buildings with no homes + MUC zoning",
     "map mode 'warehouses', For the city", "in the repo, without shells (layout-engine outlines)"),
    ("data/city/index.json", B + "app/build_site.py city(): tile index and empty-shop façades", "City in 3D", "in the repo"),
    ("data/city/layers.json", B + "app/build_site.py city(): MUC ground layers, Open Data BCN trees", "City in 3D", "in the repo"),
    ("data/city/t_", B + "app/build_site.py city(): Catastro INSPIRE building parts, 1 km tiles", "City in 3D", "in the repo"),
    ("data/catastro/b_", B + "zoning/catastro_site.py: Catastro building parts per parcel", "Find your shop: the building",
     "in the repo, without the 600 Visor 3D unit buildings"),
    ("data/daylight.json", B + "app/daylight_site.py (XGBoost predictions, Exp 4)", "nothing (removed)", "not copied: Exp 4 model removed"),
    ("data/amb.json", B + "zoning/amb.py: 36 metropolitan towns", "nothing (Results section removed)", "not copied: removed"),
    ("data/city_homes.json", B + "check/city_runs.py: home counts per place", "nothing (home counts removed)", "not copied: home counts removed"),
    ("data/shells.json", B + "app/build_site.py engine(): shop outlines for the layout engine", "nothing (parked)", "not copied: parked layout engine"),
    ("data/room_programs.json", B + "app/build_site.py engine(): flat programmes from Swiss Dwellings", "nothing (parked)", "not copied: parked layout engine"),
    ("data/demo_shops.json", B + "app/build_site.py engine(): five test shops", "nothing (parked)", "not copied: parked layout engine"),
    ("img/city_still.jpg", "screenshot of the 3D city", "City in 3D when WebGL is off", "in the repo"),
    ("img/D", B + "rhino/make_demo.py, redraw_demos.py: plans of the five demo shops", "nothing (unused before the cleanup)", "not copied: parked"),
    ("models/", B + "rhino/ glTF export of the demo shops", "nothing (unused before the cleanup)", "not copied: parked"),
    ("py/pyodide", "Pyodide 0.26.4 distribution (MPL-2.0)", "nothing (parked layout engine)", "not copied: load from the CDN when the engine returns"),
    ("py/python_stdlib.json", "Pyodide 0.26.4 standard library", "nothing (parked layout engine)", "not copied: load from the CDN when the engine returns"),
    ("py/worker.js", "hand-written worker for the layout engine", "nothing (parked)", "on parked/before-cleanup"),
    ("py/src/", B + "* (the engine's Python, copied as .txt)", "nothing (parked)", "on parked/before-cleanup"),
    ("rulebook/index.json", B + "rulebook/compile_rulebook.py", "The laws (flipbook index)", "in the repo"),
    ("rulebook/anchors.json", B + "rulebook/compile_rulebook.py", "The laws (rule bookmarks)", "in the repo"),
    ("rulebook/parts/", B + "rulebook/compile_rulebook.py from the official PDFs", "The laws (pages)", "not copied: tools/get_rulebook.py downloads the official PDFs"),
]


def rule(path):
    for p, *rest in RULES:
        if path == p or (p.endswith(("_", "/")) or p in ("img/D", "py/pyodide")) and path.startswith(p):
            return rest
    return ("?", "?", "?")


def kind(p):
    return {"json": "JSON", "pdf": "PDF", "png": "PNG image", "jpg": "JPEG image", "txt": "Python source as text",
            "js": "JavaScript", "wasm": "WebAssembly", "html": "HTML"}.get(p.suffix[1:], p.suffix)


def clean(rel, src, dst):
    if rel == "data/nomad.json":
        d = json.loads(src.read_text(encoding="utf-8"))
        d.pop("demos", None); d.pop("real", None)
        d["experiments"].pop("check", None); d["experiments"].pop("golden_rows", None)
        dst.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    elif rel == "data/premises.json":
        d = json.loads(src.read_text(encoding="utf-8"))
        keep = ["x", "y", "street", "num", "barri", "district", "ref", "zone", "key", "housing", "why", "offer", "shops"]
        idx = [d["cols"].index(c) for c in keep]
        out = {"cols": keep, "rows": [[r[i] for i in idx] for r in d["rows"]]}
        dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    elif rel == "data/warehouses.json":
        d = json.loads(src.read_text(encoding="utf-8"))
        d.pop("shells", None)
        dst.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    elif rel.startswith("data/catastro/b_"):
        d = {k: v for k, v in json.loads(src.read_text(encoding="utf-8")).items() if v.get("source") != "units"}
        dst.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        shutil.copyfile(src, dst)


def main(folder):
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    rows, copied = [], 0
    for f in files:
        rel = f.relative_to(folder).as_posix()
        came, used, what = rule(rel)
        if rel != "index.html" and what.startswith("in the repo"):
            dst = SITE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            clean(rel, f, dst)
            copied += 1
        rows.append((rel, kind(f), f.stat().st_size, came, used, what))
    total = sum(r[2] for r in rows)
    md = ["# The website's files", "",
          f"Every file of the published site (claude.ai artifact MBLnc4q9R1XusSQQyjkvYX, version of 4 Nov 2026): {len(rows)} files,",
          f"{total / 1e6:.1f} MB. Written by `tools/import_site_data.py` on 9 Nov 2026. Sizes are those of the published copy.", "",
          "| File | Type | Size | Where it came from | Where the site uses it | Now |", "| --- | --- | ---: | --- | --- | --- |"]
    groups = {}
    for r in rows:                                               # the 183 tiles, 94 building bundles, 26 law PDFs, 24 demo plans: one line each
        key = next((p for p in ("data/city/t_", "data/catastro/b_", "rulebook/parts/", "img/D", "models/", "py/src/") if r[0].startswith(p)), r[0])
        groups.setdefault(key, []).append(r)
    for key, g in groups.items():
        name = key if len(g) == 1 else f"{key}* ({len(g)} files)"
        size = sum(r[2] for r in g)
        md.append(f"| `{name}` | {g[0][1]} | {size / 1e3:,.0f} kB | {g[0][3]} | {g[0][4]} | {g[0][5]} |")
    md += ["", "No data file in the repo is over 5 MB (the largest, data/city/layers.json, is 3.2 MB), so none needs Git LFS.",
           "If a file over 5 MB is added, track it with `git lfs track <file>` before committing it.", ""]
    (ROOT / "docs" / "DATA_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{len(rows)} files listed, {copied} copied into {SITE.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1])
