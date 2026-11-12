"""Adds the rulebook pages of the checks that had none (Decret 141/2012 Annex 1, CTE DB-SI) to the anchors the website
uses, without recompiling the book. Pages are found in the compiled PDF parts by their own headings; a phrase that is
not found stops the script, so no page is ever guessed.
In/out: 4_laws_and_rules/output/rulebook/anchors.json, 4_laws_and_rules/output/rulebook/anchors.json."""
import io, json, os, sys
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from compile_rulebook import fold, rule_rects

NEW = [  # key, name, document, first and last page to search, phrase
    ("door_entry", "Entrance door width", "Decret 141/2012", 655, 668, "3.4.1.c)"),
    ("turning", "Turning circle in the practicable spaces", "Decret 141/2012", 655, 668, "3.4.1.e)"),
    ("door_inner", "Doors to the rooms", "Decret 141/2012", 655, 668, "3.4.2 Les portes"),
    ("kitchen", "Kitchen dimensions", "Decret 141/2012", 655, 668, "3.7.3 Dimensions de la cuina"),
    ("storage", "Storage: a wardrobe in each bedroom", "Decret 141/2012", 655, 668, "3.10 Espais per a"),
    ("equipment", "Equipment: bath, kitchen and laundry", "Decret 141/2012", 655, 668, "3.15 Dotaci"),
    ("escape", "Escape routes: length", "CTE DB-SI", 286, 377, "Tabla 3.1"),
]
idx = json.load(io.open(os.path.join(ROOT, "4_laws_and_rules", "output", "rulebook", "index.json"), encoding="utf-8"))
def page(n):
    for p in idx["parts"]:
        if p["first_page"] <= n <= p["last_page"]:
            return pymupdf.open(os.path.join(ROOT, "4_laws_and_rules", "output", "rulebook", p["file"]))[n - p["first_page"]]
    raise ValueError(n)
for f in ("4_laws_and_rules/output/rulebook/anchors.json",):
    a = json.load(io.open(os.path.join(ROOT, f), encoding="utf-8"))
    for key, name, doc, p0, p1, ph in NEW:
        for n in range(p0, p1 + 1):
            pg = page(n)
            if fold(ph) in fold(pg.get_text()):
                r = pg.rect
                a[key] = {"key": key, "name": name, "doc": doc, "page": n, "phrase": ph, "rects": rule_rects(pg, ph), "page_size": [round(r.width, 1), round(r.height, 1)]}
                print(key, n, len(a[key]["rects"]), "rects"); break
        else:
            raise SystemExit("not found: " + ph)
    json.dump(a, io.open(os.path.join(ROOT, f), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
