"""Nomad - Step 1c: Catalan rules, from the consolidated PDFs of the Portal Jurídic de Catalunya
(downloaded into 4_laws_and_rules/input/catalonia/raw/ - see docs/download_checklist.md) and the Agència de l'Habitatge circulars.

Laws are cut at bold headings ("Article 108", "Disposició transitòria segona", "Annex 1"); inside an
annex also at numbered sub-headings ("3.8 Habitacions."). Chapter/title headings are kept as context.
Note: the Portal says its consolidated texts "no tenen caràcter oficial"; the official one is the DOGC.
"""
import json, re, sys
import pymupdf

sys.path.insert(0, "4_laws_and_rules/code")
from fetch_cte_db import merge_lines, table_rows, inside   # same PDF helpers as Step 1b

RAW = "4_laws_and_rules/input/catalonia/raw"
OUT = "4_laws_and_rules/input/catalonia/catalonia_chunks.jsonl"

LAWS = [
    {"file": "D141-2012", "norm": "Decret 141/2012", "why": "Habitability: minimum areas, heights, light, ventilation (Annex 1 = new dwellings)",
     "eli": "https://portaljuridic.gencat.cat/eli/es-ct/d/2012/10/30/141"},
    {"file": "DL1-2010-TRLU", "norm": "TRLU (DL 1/2010)", "why": "Catalan urbanism law (art. 108.4 volume disconforme)",
     "eli": "https://portaljuridic.gencat.cat/eli/es-ct/dlg/2010/08/03/1"},
    {"file": "L18-2007", "norm": "Llei 18/2007", "why": "Right to housing (cèdula, sobreocupació, habitability)",
     "eli": "https://portaljuridic.gencat.cat/eli/es-ct/l/2007/12/28/18"},
    {"file": "DLL50-2020", "norm": "DL 50/2020", "why": "Shared housing / allotjaments; amends Llei 18/2007 and TRLU",
     "eli": "https://portaljuridic.gencat.cat/eli/es-ct/dl/2020/12/09/50"},
]
CIRCULARS = [
    {"file": "Circular-10-2025", "norm": "Circular 10/2025 AHC", "title": "Llums directes, ventilació i il·luminació natural en façanes amb elements de protecció solar",
     "url": "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/CIRCULAR-NUM.-10-2025.pdf"},
    {"file": "Circular-08", "norm": "Circular 8 AHC", "title": "Allotjaments Decret llei 50/2020",
     "url": "https://habitatge.gencat.cat/web/.content/home/ambits_dactuacio/Cedules-habitabilitat/Circulars-informatives/Circular_informativa_8.pdf"},
]

HEADER_Y, FOOTER_Y = 40, 790
START = re.compile(r"^(Preàmbul|Article \d+(?:\s?(?:bis|ter|quater|quinquies|sexies))?(?:\.\d+)?|"
                   r"Disposició (?:addicional|transitòria|derogatòria|final)(?: \w+)?|Annex \d+)$", re.I)
CONTEXT = re.compile(r"^(Títol|Capítol|Secció|Subsecció)\b.*|^Disposicions (?:addicionals|transitòries|finals)$", re.I)
ANNEX_SUB = re.compile(r"^(Apartat \d+$|\d+(?:\.\d+)+)\.?\s*([A-ZÀ-Úa-zà-ú].{0,80})?$")


def is_annex_heading(t):
    """'3.8 Habitacions.' or 'Apartat 3' - not the first line of a numbered paragraph ('3.11.1 Tots els habitatges ...')."""
    if not ANNEX_SUB.match(t) or len(t) >= 95:
        return False
    return t.startswith("Apartat") or (t.endswith(".") and len(t.split()) <= 12)


def slug(s):
    s = s.lower().replace("disposició ", "d").replace("article ", "a").replace("annex ", "annex")
    return re.sub(r"[^a-z0-9.]+", "-", s.replace("à", "a").replace("ò", "o").replace("è", "e")).strip("-")


def law_chunks(law):
    doc = pymupdf.open(f"{RAW}/{law['file']}.pdf")
    first = doc[0].get_text()
    m = re.search(r"Vigència (\d\d)/(\d\d)/(\d{4})", first)
    in_force = f"{m.group(3)}{m.group(2)}{m.group(1)}" if m else None
    chunks, cur, context, annex = [], None, "", None

    def start(block_id, title, page_no, first_lines):
        nonlocal cur
        cur = {"id": block_id, "title": title, "page": page_no, "lines": list(first_lines)}
        chunks.append(cur)

    expect_title = False
    for i, page in enumerate(doc):
        lines = [l for l in merge_lines(page) if HEADER_Y <= l["y"] < FOOTER_Y]
        tables = [t.bbox for t in page.find_tables().tables]
        words = page.get_text("words") if tables else []
        items = [(l["y"], "line", l) for l in lines if not any(inside(l, b) for b in tables)]
        items += [(b[1], "table", b) for b in tables]
        items.sort(key=lambda it: it[0])
        for _, kind, obj in items:
            if kind == "table":
                if cur:
                    cur["lines"] += ["[Tabla]"] + table_rows(words, obj) + ["[/Tabla]"]
                continue
            t = obj["text"]
            if i == 0 and cur is None and not START.match(t):
                continue   # cover lines: title, DOGC number, "TEXT CONSOLIDAT", Vigència
            if obj["bold"] and START.match(t):
                annex = t if t.lower().startswith("annex") else None
                start(slug(t), t, i + 1, [t])
                expect_title = t.lower().startswith(("article", "annex"))
                continue
            if obj["bold"] and CONTEXT.match(t):
                context = t
                expect_title = False
                continue
            if expect_title and cur and len(t) < 160:
                cur["title"] = f"{cur['title']}. {t}"
                expect_title = False
                cur["lines"].append(t)
                continue
            expect_title = False
            if annex and is_annex_heading(t):
                num = ANNEX_SUB.match(t).group(1)
                start(f"{slug(annex)}-{slug(num)}", f"{annex} · {t}", i + 1, [annex, t])
                continue
            if cur is None:
                start("preambul", "Preàmbul", i + 1, [])
            cur["lines"].append(t)
        if context and cur and not cur.get("context"):
            cur["context"] = context

    out, seen = [], {}
    for c in chunks:
        text = re.sub(r"(\w)-\n([a-zà-ú])", r"\1\2", "\n".join(c["lines"])).strip()
        if len(text) < 30:
            continue
        n = seen.get(c["id"], 0)
        seen[c["id"]] = n + 1
        out.append({
            "norm_id": law["eli"], "norm": law["norm"], "level": "catalonia",
            "block_id": c["id"] + (f"-{n + 1}" if n else ""), "block_type": "precepte", "title": c["title"],
            "in_force_from": in_force,
            "source_url": law["eli"],
            "text": text,
        })
    return out, doc.page_count, in_force


def circular_chunks(c):
    doc = pymupdf.open(f"{RAW}/{c['file']}.pdf")
    text = "\n".join(l["text"] for p in doc for l in merge_lines(p) if HEADER_Y <= l["y"] < FOOTER_Y)
    m = re.search(r"(\d{1,2}) d['’e ]+\s?(\w+) de (\d{4})", text)
    return [{
        "norm_id": c["url"], "norm": c["norm"], "level": "catalonia",
        "block_id": slug(c["file"]), "block_type": "circular", "title": c["title"],
        "in_force_from": None, "source_url": c["url"], "text": text,
        "note": "interpretive circular of the Agència de l'Habitatge de Catalunya (how the Agència applies Decret 141/2012), not a norm",
    }], doc.page_count


def main():
    all_chunks = []
    for law in LAWS:
        chunks, pages, in_force = law_chunks(law)
        all_chunks += chunks
        print(f"{law['norm']:18} {pages:4} pages  {len(chunks):4} pieces  in force from {in_force}")
    for c in CIRCULARS:
        chunks, pages = circular_chunks(c)
        all_chunks += chunks
        print(f"{c['norm']:18} {pages:4} pages  {len(chunks):4} pieces")
    with open(OUT, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print("Total Catalonia pieces:", len(all_chunks))


if __name__ == "__main__":
    main()
