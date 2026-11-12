"""Nomad - the rulebook as ONE book: the original official PDFs, compiled, with an index, page numbers and bookmarks.

Every page is the official document itself (BOE, codigotecnico.org, Portal Jurídic, Agència de l'Habitatge, RPUC, AMB,
Ajuntament). NOMAD only adds: a cover, a plain-language "how to read this book" page, a clickable index (each title jumps
to its page), a divider before each level, a page number on every page, PDF bookmarks, and an invisible text layer on the
scanned PGM pages (from our OCR, 4_laws_and_rules/input/pgm/raw/*.ocr.json) so they can be searched. The 117 MB B1600 scan is re-encoded
(lower resolution JPEG) so the book can go online; its pages are otherwise unchanged.

It also finds, for every rule NOMAD checks, the page (and on text pages the exact lines) where that rule is written:
4_laws_and_rules/output/rulebook/anchors.json. The website's flipbook uses it to bookmark and highlight the laws of each project.
Out: 4_laws_and_rules/output/rulebook/NOMAD_rulebook.pdf, 4_laws_and_rules/output/rulebook/index.json, 4_laws_and_rules/output/rulebook/anchors.json,
     4_laws_and_rules/output/rulebook/parts/<level>.pdf (one file per level, for the website; same page numbers as the full book)
Run: .venv/Scripts/python 4_laws_and_rules/code/compile_rulebook.py
"""
import io
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_laws_and_rules/output/rulebook"
D = ROOT / "4_laws_and_rules" / "input"

LEVELS = [
    ("national", "1 · Spain", "Laws for the whole country: who may build, what every building must meet (safety, health, "
                             "accessibility, noise, energy), the right to housing, and how owners of one building share it."),
    ("catalonia", "2 · Catalonia", "Catalan laws: what makes a dwelling habitable (sizes, heights, light, air), the right to "
                                   "housing in Catalonia, and the urban planning law; plus two circulars that explain how "
                                   "the habitability rules are read."),
    ("pgm", "3 · Metropolitan plan (PGM)", "The metropolitan plan of the Barcelona area and its changes: where housing is "
                                           "allowed on a ground floor, how many dwellings fit in a plot, and the "
                                           "metropolitan building and renovation ordinances."),
    ("barcelona", "4 · Barcelona", "The city's own guide to turning a ground-floor shop into a home: what the Ajuntament checks."),
]

# file, short name, official title, plain words for a layman, source link (docs/sources.md), scanned?
DOCS = [
    ("national", "national/raw/BOE-A-1999-21567-consolidado.pdf", "LOE", "Ley 38/1999, de Ordenación de la Edificación",
     "The Building Act: who is responsible for a building (owner, architect, builder) and the basic quality every building "
     "must have.", "https://www.boe.es/buscar/act.php?id=BOE-A-1999-21567", False),
    ("national", "national/raw/BOE-A-2006-5515-consolidado.pdf", "CTE", "Real Decreto 314/2006, Código Técnico de la Edificación (Parte I)",
     "The Technical Building Code: the general part that says which technical rules (the DB documents below) apply, also "
     "to works on existing buildings.", "https://www.boe.es/buscar/act.php?id=BOE-A-2006-5515", False),
    ("national", "national/cte_db/DBSUA.pdf", "CTE DB-SUA", "CTE Documento Básico SUA: Seguridad de utilización y accesibilidad",
     "Safety in use and accessibility: corridors, doors, steps, falls, and access for people with reduced mobility.",
     "https://www.codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf", False),
    ("national", "national/cte_db/DBHS.pdf", "CTE DB-HS", "CTE Documento Básico HS: Salubridad",
     "Health: indoor air and ventilation (HS 3), damp, water supply and drainage, waste.",
     "https://www.codigotecnico.org/pdf/Documentos/HS/DBHS.pdf", False),
    ("national", "national/cte_db/DBSI.pdf", "CTE DB-SI", "CTE Documento Básico SI: Seguridad en caso de incendio",
     "Fire safety: escape routes, fire separation from the rest of the building, materials.",
     "https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf", False),
    ("national", "national/cte_db/DBHR.pdf", "CTE DB-HR", "CTE Documento Básico HR: Protección frente al ruido",
     "Noise: how well walls and floors must block sound between a home and its neighbours or a shop.",
     "https://www.codigotecnico.org/pdf/Documentos/HR/DBHR.pdf", False),
    ("national", "national/cte_db/DBHE.pdf", "CTE DB-HE", "CTE Documento Básico HE: Ahorro de energía",
     "Energy: insulation, heating and cooling demand, renewable energy.",
     "https://www.codigotecnico.org/pdf/Documentos/HE/DBHE.pdf", False),
    ("national", "national/raw/BOE-A-2015-11723-consolidado.pdf", "TRLSRU", "Real Decreto Legislativo 7/2015, Ley de Suelo y Rehabilitación Urbana",
     "Land and urban renovation: owners' duties to keep buildings in good state, and renovation of existing city areas.",
     "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11723", False),
    ("national", "national/raw/BOE-A-2023-12203-consolidado.pdf", "LDV", "Ley 12/2023, por el derecho a la vivienda",
     "The Right to Housing Act (2023): housing as a right, social and affordable housing, empty homes.",
     "https://www.boe.es/buscar/act.php?id=BOE-A-2023-12203", False),
    ("national", "national/raw/BOE-A-1960-10906-consolidado.pdf", "LPH", "Ley 49/1960, sobre propiedad horizontal",
     "Horizontal Property Act: how the owners of flats and shops in one building decide together (a change of use may need "
     "the community's agreement).", "https://www.boe.es/buscar/act.php?id=BOE-A-1960-10906", False),
    ("catalonia", "catalonia/raw/D141-2012.pdf", "Decret 141/2012", "Decret 141/2012, condicions mínimes d'habitabilitat dels habitatges i cèdula d'habitabilitat",
     "THE habitability decree: minimum sizes of a dwelling and its rooms, ceiling heights, façade, windows, light and "
     "ventilation. Annex 4 says which rules apply when a shop becomes a home.",
     "https://portaljuridic.gencat.cat/eli/es-ct/d/2012/10/30/141", False),
    ("catalonia", "catalonia/raw/Circular-10-2025.pdf", "Circular 10/2025", "Circular 10/2025, Agència de l'Habitatge de Catalunya",
     "How the habitability office reads the decree on direct light (an interpretation, not a law).",
     "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/CIRCULAR-NUM.-10-2025.pdf", False),
    ("catalonia", "catalonia/raw/Circular-08.pdf", "Circular 8", "Circular informativa 8, Agència de l'Habitatge de Catalunya",
     "Another interpretation note of the habitability office (not a law).",
     "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/Circular_informativa_8.pdf", False),
    ("catalonia", "catalonia/raw/L18-2007.pdf", "Llei 18/2007", "Llei 18/2007, del dret a l'habitatge",
     "The Catalan Right to Housing Act: quality of dwellings, empty homes, social housing.",
     "https://portaljuridic.gencat.cat/eli/es-ct/l/2007/12/28/18", False),
    ("catalonia", "catalonia/raw/DLL50-2020.pdf", "DL 50/2020", "Decret llei 50/2020, de mesures urgents per estimular la promoció d'habitatge amb protecció oficial",
     "Urgent measures for protected housing; among others it repealed part of the habitability decree.",
     "https://portaljuridic.gencat.cat/eli/es-ct/dl/2020/12/09/50", False),
    ("catalonia", "catalonia/raw/DL1-2010-TRLU.pdf", "TRLU", "Decret legislatiu 1/2010, Text refós de la Llei d'urbanisme",
     "The Catalan planning law: zoning, licences, changes of use.",
     "https://portaljuridic.gencat.cat/eli/es-ct/dlg/2010/08/03/1", False),
    ("pgm", "pgm/raw/MPGM-1999-art225.pdf", "MPGM 1999 art. 225", "Modificació del PGM: art. 225 de les normes urbanístiques, ús d'habitatge en planta baixa",
     "Where a ground floor may be a home: art. 225.7 allows ground-floor housing in street-line zones, with open space in front.",
     "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/96749", True),
    ("pgm", "pgm/raw/MPGM-2004-habitatges-parcela.pdf", "MPGM 2004", "Modificació del PGM: nombre màxim d'habitatges per parcel·la a Barcelona",
     "How many dwellings fit in a plot in Barcelona (one per 80 m² built), and the minimum size and façade of a dwelling.",
     "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/215050", True),
    ("pgm", "pgm/raw/MPGM-B1600.pdf", "MPGM B1600", "Modificació del PGM per a l'obtenció d'habitatge assequible (B1600, 2018)",
     "Affordable housing in the consolidated city (30 % rule). Its final provision two was annulled by the court (next document).",
     "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/283290", True),
    ("pgm", "pgm/raw/MPGM-B1600-acord-sentencia-2022.pdf", "B1600 ruling", "Acord de 31/5/2022 sobre la sentència del TSJC (MPGM B1600)",
     "The court ruling on the B1600 change, as recorded by the planning commission.",
     "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/283290", False),
    ("pgm", "pgm/raw/OME.pdf", "OME", "Ordenances metropolitanes d'edificació",
     "Metropolitan building ordinances: heights, patios, projections and other building details.",
     "https://www.amb.cat/web/territori/gestio-i-organitzacio/numamb", False),
    ("pgm", "pgm/raw/OM-rehabilitacio.pdf", "OM rehabilitació", "Ordenances metropolitanes de rehabilitació",
     "Metropolitan renovation ordinances: what existing buildings must meet when they are renovated.",
     "https://www.amb.cat/web/territori/gestio-i-organitzacio/numamb", False),
    ("barcelona", "barcelona_guide/InforUrb_Canvi-us-habitatge.pdf", "Guia canvi d'ús", "Informació bàsica per a consultes sobre canvi d'ús de locals a habitatge (Ajuntament de Barcelona, 2025)",
     "The city's guide: every rule it checks before a shop can become a home (guidance, not a law).",
     "https://ajuntament.barcelona.cat/urbanisme-accio-climatica-mobilitat-pla-barris-serveis-urbans/sites/default/files/2025-03/InforUrb_Canvi-us-habitatge.pdf", False),
]

# every rule NOMAD checks -> where it is written: (key, plain name, document short name, phrases to find, in order of preference)
# Phrases are copied from the documents (headings or rule-card quotes, 4_laws_and_rules/output/rules/rules.json); nothing is invented.
ANCHORS = [
    ("zoning", "Can a ground floor be housing here (PGM art. 225.7)", "MPGM 1999 art. 225", ["planta baixa", "225"]),
    ("height", "Clear height for a change of use: 2,40 m", "Decret 141/2012", ["Grup C", "Annex 4"]),
    ("height_rule", "Minimum habitable height", "Decret 141/2012", ["3.5 Alçada mínima habitable."]),
    ("useful", "Minimum useful area of a dwelling", "Decret 141/2012", ["3.1 Habitabilitat i ocupació."]),
    ("useful_bcn", "Barcelona: minimum dwelling size and façade", "MPGM 2004", ["40 m", "superfície útil"]),
    ("density", "Barcelona: one dwelling per 80 m² built", "MPGM 2004", ["80 m", "318"]),
    ("facade", "Minimum façade of a dwelling", "Decret 141/2012", ["3.6 Façana mínima."]),
    ("hall", "Width of the circulation inside the dwelling", "Decret 141/2012", ["3.4.1.d)"]),
    ("living", "Size of the living room (common spaces)", "Decret 141/2012", ["3.7.2 Dimensions dels espais d’ús comú."]),
    ("bedroom", "Size of the bedrooms", "Decret 141/2012", ["3.8 Habitacions."]),
    ("windows", "Natural light and ventilation (windows)", "Decret 141/2012", ["3.9 Ventilació i il·luminació natural."]),
    ("bath", "Bathrooms", "Decret 141/2012", ["3.11 Cambres higièniques."]),
    ("patio", "Ventilation patios", "Decret 141/2012", ["2.5.1 Patis de ventilació."]),
    ("ldk_repealed", "Annex 1 3.7.1 (20 m² living-kitchen) repealed", "Decret 141/2012", ["3.7.1 derogat", "Apartat 3.7.1 derogat"]),
    ("corridor", "Shared corridor width (accessible route)", "CTE DB-SUA", ["Itinerario accesible"]),
    ("ventilation", "Indoor air quality and ventilation (HS 3)", "CTE DB-HS", ["Calidad del aire interior"]),
    ("guide", "What Barcelona checks for a shop-to-home change", "Guia canvi d'ús", ["canvi d'ús", "habitatge"]),
]


def fold(s):
    """Lower case, no accents, one kind of apostrophe, single spaces: for finding text across PDFs and OCR."""
    s = unicodedata.normalize("NFKD", s.replace("’", "'").replace("·", ".")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


SECTION = re.compile(r"^\s*(\d+(\.\d+)+\.?\s|\d+\.\d+(\.\d+)*\.[a-z]\)|annex\s+\d|article\s+\d|art[ií]culo\s+\d)", re.I)


def rule_rects(page, phrase, limit=8):
    """Boxes to highlight on a text page: the line where the phrase is, and the paragraphs under it, down to the next
    numbered heading (or the end of the page). A heading like '3.8 Habitacions.' then lights up the whole rule."""
    hits = page.search_for(phrase)
    if not hits:
        return []
    top = hits[0]
    out = [top]
    lines = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(sp["text"] for sp in ln["spans"]).strip()
            if t:
                lines.append((pymupdf.Rect(ln["bbox"]), t))
    lines.sort(key=lambda x: (round(x[0].y0), x[0].x0))
    for r, t in lines:
        if r.y0 <= top.y1 - 1 or abs(r.x0 - top.x0) > 260:
            continue
        if r.y0 > page.rect.height * 0.93:                         # the page's own footer and page number
            break
        if SECTION.match(t) and not t.startswith(phrase.split(" ")[0]):
            break
        if r.y0 > top.y1 + 420 or len(out) > 60:
            break
        out.append(r)
    # merge the lines into a few paragraph boxes
    merged = []
    for r in out:
        if merged and r.y0 - merged[-1].y1 < 6 and abs(r.x0 - merged[-1].x0) < 40:
            merged[-1] |= r
        else:
            merged.append(pymupdf.Rect(r))
    return [[round(v, 1) for v in m] for m in merged[:limit]]


def ocr_pages(pdf):
    p = pdf.with_suffix(".ocr.json")
    if not p.exists():
        return {}
    return json.load(io.open(p, encoding="utf-8"))


def shrink_scans(doc, width=1300, quality=50):
    """Scanned pages of text: a new document where each page is ONE greyscale JPEG of the page, about 80 dpi on these
    A3 sheets (still easy to read on screen). Returns the new document; the page sizes stay the same."""
    from PIL import Image
    out = pymupdf.open()
    for page in doc:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(width / page.rect.width, width / page.rect.width), colorspace=pymupdf.csGRAY)
        pic = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        b = io.BytesIO(); pic.save(b, "JPEG", quality=quality, optimize=True)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=b.getvalue())
    return out


FONT = "helv"
INK, MUTED, ACC = (0.12, 0.12, 0.12), (0.42, 0.41, 0.38), (0.75, 0.44, 0.31)


def wrap(text, size, width, font=FONT):
    """Split text into lines that fit width (points) in the given font: measured, so nothing is silently dropped."""
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            t = (line + " " + word).strip()
            if pymupdf.get_text_length(t, fontname=font, fontsize=size) <= width or not line:
                line = t
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def put(pg, x, y, text, size, width, font=FONT, color=INK, lead=1.3, **kw):
    """Write wrapped text from baseline y; return the baseline after the last line."""
    for ln in wrap(text, size, width, font):
        pg.insert_text((x, y), ln, fontsize=size, fontname=font, color=color, **kw)
        y += size * lead
    return y


def text_page(book, title, lines, w=595, h=842):
    """A plain A4 page NOMAD adds (cover, how to read, dividers). lines: [(text, size, colour, gap_before)]."""
    pg = book.new_page(width=w, height=h)
    pg.insert_text((60, 90), title, fontsize=24, fontname="hebo", color=INK)
    y = 130
    for t, size, col, gap in lines:
        y = put(pg, 60, y + gap, t, size, w - 120, color=col)
    return pg


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "parts").mkdir(exist_ok=True)
    srcs = []
    for lvl, rel, short, title, plain, url, scan in DOCS:
        f = D / rel
        doc = pymupdf.open(f)
        srcs.append(dict(level=lvl, file=rel, short=short, title=title, plain=plain, url=url, scan=scan, pages=doc.page_count))
        doc.close()
    total_src = sum(s["pages"] for s in srcs)

    book = pymupdf.open()
    # ---- front matter: cover, how to read, index (index pages are filled after we know every page number) ----
    text_page(book, "NOMAD rulebook", [
        ("Every regulation that decides whether a ground-floor shop in Barcelona can become a home, in one book.", 14, INK, 0),
        ("%d official documents · %d original pages · 4 levels: Spain, Catalonia, the metropolitan plan, Barcelona."
         % (len(srcs), total_src), 11, MUTED, 18),
        ("The pages are the official texts themselves, unchanged. NOMAD only adds this cover, a page on how to read the book, "
         "the index, one divider per level, page numbers and bookmarks.", 11, MUTED, 10),
        ("IAAC Master in AI for Architecture 2026-27 · NOMAD (Bhavini, Alvaro, Bars) · compiled %s" % "29 October 2026", 9, MUTED, 40),
    ])
    text_page(book, "How to read this book", [
        ("Laws are written in Spanish and Catalan, and in legal language. You do not need to read all of it.", 12, INK, 0),
        ("1. Start at the index. Each document has one line in plain words saying what it is about. Click a title to jump to it.", 11, INK, 14),
        ("2. The four levels go from the widest to the closest: Spain applies everywhere, then Catalonia, then the metropolitan "
         "plan of the Barcelona area, then the city of Barcelona. When two levels say different things, the stricter one "
         "usually applies to your project, and a professional confirms it.", 11, INK, 8),
        ("3. For a shop becoming a home, most of the numbers are in the Catalan habitability decree (Decret 141/2012, "
         "Annex 1 and Annex 4) and in the Barcelona plan changes (MPGM 1999 art. 225, MPGM 2004).", 11, INK, 8),
        ("4. On the NOMAD website, after you check a shop, the book opens with bookmarks on the exact pages that decided your "
         "answer, and highlights the lines where it can.", 11, INK, 8),
        ("5. The page numbers at the bottom right are this book's. Each document keeps its own original numbering too.", 11, INK, 8),
        ("Not legal advice. Consolidated texts from the Portal Jurídic de Catalunya are working copies (the official text is "
         "the DOGC); the circulars and the Ajuntament guide are interpretations, not laws. Always confirm with the Ajuntament "
         "or an architect before starting works.", 9, MUTED, 22),
    ])
    n_index = 2                                                  # index pages (reserved; 23 entries over 2 pages)
    for _ in range(n_index):
        book.new_page(width=595, height=842)
    front = book.page_count

    # ---- the documents, level by level, each level after a divider ----
    toc, starts = [], {}
    for lvl, lname, lplain in LEVELS:
        docs = [s for s in srcs if s["level"] == lvl]
        text_page(book, "Level " + lname, [(lplain, 12, INK, 0)] +
                  [("%s  —  %s" % (s["short"], s["title"]), 10, MUTED, 10) for s in docs])
        toc.append([1, "Level " + lname, book.page_count])
        s_level = book.page_count
        for s in docs:
            src = pymupdf.open(D / s["file"])
            if s["short"] == "MPGM B1600":                       # 117 MB of 200-dpi colour scans: re-encode so the book can go online
                small = shrink_scans(src); src.close(); src = small
            start = book.page_count
            book.insert_pdf(src)
            src.close()
            s["start"] = start + 1                               # 1-based page in the book
            starts[s["short"]] = s["start"]
            toc.append([2, "%s — %s" % (s["short"], s["title"][:90]), s["start"]])
            if s["scan"]:                                        # invisible OCR text, so the scan pages can be searched
                oc = ocr_pages(D / s["file"])
                for i in range(s["pages"]):
                    t = oc.get(str(i + 1))
                    if t:
                        pg = book[start + i]                      # render_mode 3 = invisible, but found by search and copy
                        put(pg, 20, 24, t, 4, pg.rect.width - 40, lead=1.15, render_mode=3)
        s_level_end = book.page_count
        for s in docs:
            s["level_name"] = lname
        globals().setdefault("PARTS", []).append((lvl, s_level, s_level_end))

    total = book.page_count
    # ---- index pages: one line per document, clickable ----
    y, pi = 0, 0
    pg = book[2]
    pg.insert_text((60, 70), "Index", fontsize=24, fontname="hebo", color=INK)
    y = 110
    for lvl, lname, lplain in LEVELS:
        if y > 720:
            pi += 1; pg = book[2 + pi]; y = 70
        pg.insert_text((60, y), "Level " + lname, fontsize=13, fontname="hebo", color=ACC)
        pg.insert_text((480, y), "page", fontsize=8, fontname=FONT, color=MUTED)
        y += 8
        for s in [s for s in srcs if s["level"] == lvl]:
            if y > 760:
                pi += 1; pg = book[2 + pi]; y = 70
            y += 16
            y0 = y
            pg.insert_text((480, y), str(s["start"]), fontsize=10, fontname="hebo", color=ACC)
            y = put(pg, 60, y, s["short"] + "  ·  " + s["title"], 9.5, 405, font="hebo", color=INK)
            y = put(pg, 60, y + 1, s["plain"], 8, 460, color=MUTED)
            pg.insert_link({"kind": pymupdf.LINK_GOTO, "page": s["start"] - 1, "from": pymupdf.Rect(56, y0 - 11, 540, y - 6),
                            "to": pymupdf.Point(0, 0)})
        y += 16
    toc = [[1, "Cover", 1], [1, "How to read this book", 2], [1, "Index", 3]] + toc

    # ---- page numbers on every page ----
    for i, page in enumerate(book):
        r = page.rect
        label = "NOMAD rulebook  %d / %d" % (i + 1, total)
        box = pymupdf.Rect(r.x1 - 150, r.y1 - 15, r.x1 - 6, r.y1 - 3)
        page.draw_rect(box, color=None, fill=(1, 1, 1), fill_opacity=0.85, overlay=True)
        page.insert_text((box.x1 - 4 - pymupdf.get_text_length(label, fontname=FONT, fontsize=7), box.y1 - 3.5), label,
                         fontsize=7, fontname=FONT, color=MUTED)
    book.set_toc(toc)
    book.set_metadata({"title": "NOMAD rulebook: the regulations for turning a Barcelona shop into a home",
                       "author": "NOMAD (IAAC MaAI 2026-27)", "subject": "Compiled official texts", "keywords": "Barcelona, habitatge, canvi d'ús"})

    # ---- where each rule is written (page + highlight boxes on text pages) ----
    anchors = {}
    by_short = {s["short"]: s for s in srcs}
    for key, name, short, phrases in ANCHORS:
        s = by_short[short]
        found = None
        oc = ocr_pages(D / s["file"]) if s["scan"] else {}
        for ph in phrases:
            for i in range(s["pages"]):
                bp = s["start"] - 1 + i
                txt = oc.get(str(i + 1), "") if s["scan"] else book[bp].get_text()
                if fold(ph) in fold(txt):
                    rects = [] if s["scan"] else rule_rects(book[bp], ph)
                    pr = book[bp].rect
                    found = {"key": key, "name": name, "doc": short, "page": bp + 1, "phrase": ph,
                             "rects": rects, "page_size": [round(pr.width, 1), round(pr.height, 1)]}
                    break
            if found:
                break
        anchors[key] = found or {"key": key, "name": name, "doc": short, "page": s["start"], "phrase": None, "rects": [],
                                 "note": "phrase not found: opens the document's first page"}
        print("%-13s %-18s p.%-5s %s" % (key, short, anchors[key]["page"], "" if found else "(not found)"))

    book.save(OUT / "NOMAD_rulebook.pdf", garbage=3, deflate=True)
    # one file per document for the website (each under the host's 15 MB limit; the flipbook loads only what is opened).
    # A level's divider page travels with its first document. Page numbers stay those of the full book.
    for old in (OUT / "parts").glob("*.pdf"):
        old.unlink()
    parts, k = [], 0
    for lvl, a, b in globals()["PARTS"]:
        docs = [s for s in srcs if s["level"] == lvl]
        for j, s in enumerate(docs):
            first = a if j == 0 else s["start"]                   # page a = the level divider, kept with its first document
            last = s["start"] + s["pages"] - 1
            chunks = [(first, last)]
            while True:                                           # a document over 12 MB is cut into equal chunks
                trial = []
                for c0, c1 in chunks:
                    part = pymupdf.open(); part.insert_pdf(book, from_page=c0 - 1, to_page=c1 - 1)
                    trial.append((c0, c1, part.tobytes(garbage=3, deflate=True)))
                if max(len(t[2]) for t in trial) < 12e6 or len(chunks) >= 8:
                    break
                n = len(chunks) + 1
                step = -(-(last - first + 1) // n)
                chunks = [(p, min(last, p + step - 1)) for p in range(first, last + 1, step)]
            for c0, c1, data in trial:
                k += 1
                fp = OUT / "parts" / ("%02d.pdf" % k)
                fp.write_bytes(data)
                parts.append({"level": lvl, "doc": s["short"], "file": "parts/%02d.pdf" % k, "first_page": c0, "last_page": c1,
                              "mb": round(len(data) / 1e6, 2)})
    front_part = pymupdf.open(); front_part.insert_pdf(book, from_page=0, to_page=front - 1)
    front_part.save(OUT / "parts" / "00.pdf", garbage=3, deflate=True)
    parts.insert(0, {"level": "front", "doc": "front", "file": "parts/00.pdf", "first_page": 1, "last_page": front,
                     "mb": round((OUT / "parts" / "00.pdf").stat().st_size / 1e6, 2)})
    idx = {"title": "NOMAD rulebook", "pages": total, "levels": [{"id": l, "name": n, "plain": p} for l, n, p in LEVELS],
           "docs": [{k: s[k] for k in ("level", "short", "title", "plain", "url", "scan", "pages", "start")} for s in srcs],
           "parts": parts}
    json.dump(idx, io.open(OUT / "index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(anchors, io.open(OUT / "anchors.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("book: %d pages, %.1f MB | parts: %s" % (total, (OUT / "NOMAD_rulebook.pdf").stat().st_size / 1e6,
                                                   "largest %s MB (%s)" % max((p["mb"], p["doc"]) for p in parts)))


if __name__ == "__main__":
    main()
