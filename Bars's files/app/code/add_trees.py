"""NOMAD - put Barcelona's trees into the 3D city tiles (the "trees" layer).

The tiles in Bars's files/app/data/city/ were built without trees (build_site.py adds them only when the tree files are
on the machine), so the layer drew nothing. This adds them in the same encoding build_site.py city() uses:
  "tr": base64 of int16 pairs ((x - x0) * 10, (y - y0) * 10), metres from the tile's south-west corner, 0,1 m
  "tk": one character per tree, its size class: 0 unknown, 1 TERCERA, 2 SEGONA, 3 PRIMERA, 4 EXEMPLAR, 5 palm
A tree in a 1 km cell with no buildings gets a tile of its own (no buildings, only trees), added to the tile index.
Everything else in the tiles stays byte for byte. index.json gets the tree count, its date and the source.

Source: Open Data BCN (Ajuntament de Barcelona), CC BY 4.0: "Arbrat viari" (street trees), "Arbrat zona" (zone trees),
"Arbrat parcs" (park trees); coordinates x_etrs89 / y_etrs89 (EPSG:25831), size from categoria_arbrat, palm when
tipus_element starts with PALMERA.
Run from the repo root:  python "Bars's files/app/code/add_trees.py" [viari.csv zona.csv parcs.csv]   (downloads them when none is given)
"""
import base64
import csv
import io
import json
import struct
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CITY = ROOT / "Bars's files" / "app" / "data" / "city"
SETS = [("street trees (arbrat viari)",
         "https://opendata-ajuntament.barcelona.cat/data/dataset/27b3f8a7-e536-4eea-b025-ce094817b2bd/resource/23124fd5-521f-40f8-85b8-efb1e71c2ec8/download"),
        ("zone trees (arbrat zona)",
         "https://opendata-ajuntament.barcelona.cat/data/dataset/9b525e1d-13b8-48f1-abf6-f5cd03baa1dd/resource/29cd5c1f-11b1-404b-b3a5-ae29940b8c55/download"),
        ("park trees (arbrat parcs)",
         "https://opendata-ajuntament.barcelona.cat/data/dataset/99ce00b1-36ab-4e06-b1bc-c60c5f7a811d/resource/23076aaa-4f0e-4045-b4e5-61d5e651b5a6/download")]
SIZE = {"EXEMPLAR": 4, "PRIMERA": 3, "SEGONA": 2, "TERCERA": 1}          # as build_site.py


def dump(d):
    return json.dumps(d, separators=(",", ":"))


def main():
    texts = ([Path(p).read_text(encoding="utf-8-sig") for p in sys.argv[1:4]] if len(sys.argv) > 3
             else [urllib.request.urlopen(u, timeout=300).read().decode("utf-8-sig") for _, u in SETS])
    ix = json.loads((CITY / "index.json").read_text(encoding="utf-8"))
    T = ix["tile"]
    cells, counts, kinds, bad = {}, [], Counter(), 0
    for (name, _), text in zip(SETS, texts):
        n = 0
        for r in csv.DictReader(io.StringIO(text)):
            try:
                x, y = float(r["x_etrs89"]), float(r["y_etrs89"])
            except ValueError:
                bad += 1
                continue
            k = 5 if r["tipus_element"].upper().startswith("PALMERA") else SIZE.get(r["categoria_arbrat"], 0)
            cells.setdefault((int(x // T), int(y // T)), []).append((x, y, k))
            kinds[k] += 1
            n += 1
        counts.append((name, n))
    have = {(i, j) for i, j, _ in ix["tiles"]}
    added, written = [], 0
    for (i, j), trees in sorted(cells.items()):
        f = CITY / f"t_{i}_{j}.json"
        x0, y0 = i * T, j * T
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"x0": x0, "y0": y0, "n": [], "up": [], "bid": [], "b": [], "xy": ""}
        xy = [max(-32768, min(32767, int(round(v)))) for x, y, k in trees for v in ((x - d["x0"]) * 10, (y - d["y0"]) * 10)]
        d["tr"] = base64.b64encode(struct.pack("<%dh" % len(xy), *xy)).decode()
        d["tk"] = "".join(str(k) for _, _, k in trees)
        f.write_text(dump(d), encoding="utf-8")
        written += 1
        if (i, j) not in have:
            ix["tiles"].append([i, j, 0])
            added.append(f.name)
    total = sum(n for _, n in counts)
    ix["trees"] = {"count": total, "by_dataset": dict(counts), "date": date.today().isoformat(),
                   "source": "Ajuntament de Barcelona, Open Data BCN: arbrat viari, arbrat zona, arbrat parcs (CC BY 4.0)"}
    (CITY / "index.json").write_text(json.dumps(ix, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"trees: {total:,} ({', '.join(f'{n:,} {k}' for k, n in counts)}); {bad} rows without coordinates skipped")
    print("size classes:", {["unknown", "TERCERA", "SEGONA", "PRIMERA", "EXEMPLAR", "palm"][k]: v for k, v in sorted(kinds.items())})
    print(f"tiles written: {written}; new tiles with trees only: {len(added)} {added[:6]}")


if __name__ == "__main__":
    main()
