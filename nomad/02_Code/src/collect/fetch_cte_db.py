"""Nomad - Step 1b: download the CTE technical documents (DB-HS, SUA, SI, HR, HE)
from codigotecnico.org and split them into section chunks (e.g. "HS3-3.1.1") for RAG.

How it works, page by page:
1. The 2nd line of the page header names the section (e.g. "HS 3 Calidad del aire interior").
2. Tables are found with pymupdf, then rebuilt row by row from word positions
   (pymupdf's own cell text drops spaces and can break numbers like "0,7").
3. All other lines are read top to bottom; a bold line starting with a number
   ("3.1.1 Viviendas") starts a new chunk.
"""
import json, os, re, time
from datetime import date
import requests
import pandas as pd
import pymupdf

BASE = "https://www.codigotecnico.org/pdf/Documentos"
OUT = "data/national"
PDF_DIR = f"{OUT}/cte_db"

# in_force: entry into force of the last decree that changed this DB (codigotecnico.org names the decree;
# dates from BOE: RD 450/2022 and RD 732/2019 version dates in BOE-A-2006-5515, RD 164/2025 = BOE-A-2025-7190)
DBS = [
    {"code": "HS",  "in_force": "20220616", "why": "Health: HS3 indoor air quality / ventilation"},
    {"code": "SUA", "in_force": "20220616", "why": "Safety of use and accessibility"},
    {"code": "SI",  "in_force": "20250510", "why": "Fire safety"},
    {"code": "HR",  "in_force": "20191228", "why": "Protection against noise"},
    {"code": "HE",  "in_force": "20220616", "why": "Energy saving"},
]

HEADER_Y = 62     # lines above this are the running page header
FOOTER_Y = 785    # lines below this are the page number
HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
ANNEX = re.compile(r"^(Anejo|Apéndice)\s+([A-Z])\b\.?\s*(.*)$")

# The PDFs write symbols (≥ ≤ × Δ α ...) in the old "Symbol" font, which pymupdf returns as
# private codes U+F020-U+F0FF. The last two hex digits are the Symbol-font code; map them back.
_SYM = dict(zip(range(0x41, 0x5B), "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ"))
_SYM.update(zip(range(0x61, 0x7B), "αβχδεφγηιϕκλμνοπθρστυϖωξψζ"))
_SYM.update({0x22: "∀", 0x24: "∃", 0x2A: "∗", 0x2D: "−", 0x40: "≅", 0x5C: "∴", 0x5E: "⊥", 0x7E: "∼",
             0xA2: "′", 0xA3: "≤", 0xA4: "⁄", 0xA5: "∞", 0xAB: "↔", 0xAC: "←", 0xAD: "↑", 0xAE: "→",
             0xAF: "↓", 0xB0: "°", 0xB1: "±", 0xB2: "″", 0xB3: "≥", 0xB4: "×", 0xB5: "∝", 0xB6: "∂",
             0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBA: "≡", 0xBB: "≈", 0xBC: "…", 0xD6: "√", 0xD7: "·",
             0xD8: "¬", 0xD9: "∧", 0xDA: "∨", 0xE5: "Σ", 0xF2: "∫",
             0xE6: "(", 0xE9: "[", 0xEC: "{", 0xF6: ")", 0xF9: "]", 0xFC: "}"})
SYMBOL_FONT = {0xF000 + k: v for k, v in _SYM.items()}
SYMBOL_FONT.update({c: chr(c - 0xF000) for c in range(0xF020, 0xF07F) if c not in SYMBOL_FONT})
SYMBOL_FONT.update({c: "" for c in list(range(0xF0E7, 0xF0F0)) + list(range(0xF0F3, 0xF100)) if c not in SYMBOL_FONT})  # bracket pieces


def download(code):
    path = f"{PDF_DIR}/DB{code}.pdf"
    if not os.path.exists(path):
        r = requests.get(f"{BASE}/{code}/DB{code}.pdf", timeout=180)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        time.sleep(1)
    return path


def section_of(header_lines, code):
    """'HS 3 Calidad del aire' -> ('HS3', 'HS 3 Calidad del aire'); 'Anejo A. Terminología' -> ('AnejoA', ...)."""
    for h in header_lines[1:]:
        m = re.match(rf"^({code})\s?(\d+)\b", h)
        if m:
            return m.group(1) + m.group(2), h
        m = re.match(r"^Anejo\s+([A-Z])\b", h)
        if m:
            return "Anejo" + m.group(1), h
        if h.upper().startswith("INTRODUCCI"):
            return "Intro", "Introducción"
        if h.upper().startswith("ÍNDICE"):
            return "Indice", "Índice"
    return code, header_lines[0] if header_lines else code   # HR has no sub-sections


def merge_lines(page):
    """Pymupdf splits '3.1.1' and 'Viviendas' into separate lines; join pieces with the same y."""
    pieces = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans = [s for s in l["spans"] if s["text"].strip()]
            if spans:
                pieces.append({"x": l["bbox"][0], "y": l["bbox"][1], "y1": l["bbox"][3],
                               "text": "".join(s["text"] for s in l["spans"]).strip(),   # keep space-only spans
                               "bold": all(s["flags"] & 16 for s in spans),
                               "size": max(s["size"] for s in spans)})
    pieces.sort(key=lambda p: (round(p["y"]), p["x"]))
    lines = []
    for p in pieces:
        if lines and abs(lines[-1]["y"] - p["y"]) <= 2.5:
            last = lines[-1]
            last["text"] += " " + p["text"]
            last["bold"] = last["bold"] and p["bold"]
            last["size"] = max(last["size"], p["size"])
            last["y1"] = max(last["y1"], p["y1"])
        else:
            lines.append(dict(p))
    return lines


def table_rows(page_words, bbox):
    """Rebuild a table as 'cell | cell' rows from the position of each word."""
    words = [w for w in page_words
             if w[0] >= bbox[0] - 1 and w[2] <= bbox[2] + 1 and w[1] >= bbox[1] - 1 and w[3] <= bbox[3] + 1]
    words.sort(key=lambda w: (round(w[1]), w[0]))
    rows = []
    for w in words:
        if rows and abs(rows[-1][0][1] - w[1]) <= 2.5:
            rows[-1].append(w)
        else:
            rows.append([w])
    out = []
    for row in rows:
        row.sort(key=lambda w: w[0])
        cells, cur, last_x1 = [], [], None
        for w in row:
            if last_x1 is not None and w[0] - last_x1 > 5:
                cells.append(" ".join(cur))
                cur = []
            cur.append(w[4])
            last_x1 = w[2]
        cells.append(" ".join(cur))
        out.append(" | ".join(cells))
    return out


def inside(line, bbox):
    cy = (line["y"] + line["y1"]) / 2
    return bbox[0] - 2 <= line["x"] <= bbox[2] and bbox[1] - 2 <= cy <= bbox[3] + 2


def clean(text):
    text = text.translate(SYMBOL_FONT)
    text = re.sub(r"(\w)-\n([a-záéíóúñ])", r"\1\2", text)   # rejoin words split across lines: "mecáni-\nca"
    return text.strip()


def pdf_to_chunks(path, code, in_force):
    doc = pymupdf.open(path)
    url = f"{BASE}/{code}/DB{code}.pdf"
    chunks, cur, carry = [], None, ""

    def close():
        nonlocal cur, carry
        if cur is None:
            return
        body = clean("\n".join(cur["lines"][1:]))
        if not body or (cur["intro"] and len(body) < 150):
            # heading with no text of its own ("3 Diseño", a section title page): keep it for the next chunk
            carry += "\n".join(cur["lines"]) + "\n"
        else:
            chunks.append({
                "norm_id": f"CTE-DB-{code}", "norm": f"CTE-DB-{code}", "level": "national",
                "block_id": cur["id"], "block_type": "seccion", "title": cur["title"],
                "in_force_from": in_force,
                "source_url": f"{url}#page={cur['page']}",
                "text": clean(cur["carry"] + "\n".join(cur["lines"])),
            })
            carry = ""
        cur = None

    def start(prefix, sec_label, num, heading, page_no, first_line):
        nonlocal cur
        close()
        cur = {"id": f"{prefix}-{num}" if num else prefix,
               "title": f"{sec_label} · {num} {heading}".strip() if num else sec_label,
               "page": page_no, "lines": [first_line], "carry": carry, "intro": num is None}

    sec = prefix = None
    for i, page in enumerate(doc):
        if i == 0:
            continue   # cover page
        lines = merge_lines(page)
        header = [l["text"] for l in lines if l["y"] < HEADER_Y]
        page_sec, sec_label = section_of(header, code)
        if page_sec == "Indice":
            continue
        if page_sec != sec:
            sec = prefix = page_sec
            start(prefix, sec_label, None, None, i + 1, sec_label)

        tables = [t.bbox for t in page.find_tables().tables]
        page_words = page.get_text("words") if tables else []
        items = [(l["y"], "line", l) for l in lines
                 if HEADER_Y <= l["y"] < FOOTER_Y and not any(inside(l, b) for b in tables)]
        items += [(b[1], "table", b) for b in tables]
        items.sort(key=lambda it: it[0])

        for _, kind, obj in items:
            if kind == "table":
                cur["lines"] += ["[Tabla]"] + table_rows(page_words, obj) + ["[/Tabla]"]
                continue
            m = HEADING.match(obj["text"])
            a = ANNEX.match(obj["text"])
            if a and obj["bold"] and obj["size"] >= 12:
                # unnumbered annex inside a section (HS 6 "Apéndice A", HR "Anejo A"): its own prefix
                name = ("Apendice" if a.group(1) == "Apéndice" else "Anejo") + a.group(2)
                prefix = sec if sec.startswith(name) else (name if sec == code else f"{sec}-{name}")
                sec_label = obj["text"]
                start(prefix, sec_label, None, None, i + 1, obj["text"])
                cur["intro"] = False
            elif m and obj["bold"] and obj["size"] >= 9.5 and len(obj["text"]) < 160:
                start(prefix, sec_label, m.group(1), m.group(2), i + 1, obj["text"])
            else:
                cur["lines"].append(obj["text"])
    close()

    seen = {}   # make block_id unique if a heading number repeats
    for c in chunks:
        n = seen.get(c["block_id"], 0)
        seen[c["block_id"]] = n + 1
        if n:
            c["block_id"] += f"-{n + 1}"
    return chunks, doc.page_count


def main():
    os.makedirs(PDF_DIR, exist_ok=True)
    all_chunks, rows = [], []
    for db in DBS:
        print("Processing", f"DB-{db['code']}")
        path = download(db["code"])
        chunks, pages = pdf_to_chunks(path, db["code"], db["in_force"])
        all_chunks += chunks
        rows.append({"norm": f"CTE-DB-{db['code']}", "pages": pages, "chunks": len(chunks),
                     "tables": sum(c["text"].count("[Tabla]") for c in chunks),
                     "downloaded": date.today().isoformat(), "why": db["why"]})

    with open(f"{OUT}/cte_db_chunks.jsonl", "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/cte_db_summary.csv", index=False)
    print(df[["norm", "pages", "chunks", "tables"]])
    print("Total CTE-DB chunks:", len(all_chunks), "(run src/collect/build_rulebook.py to merge)")


if __name__ == "__main__":
    main()
