"""Nomad - Step 1d: PGM (Pla General Metropolità) documents for Barcelona, from the
Registre de Planejament Urbanístic de Catalunya (RPUC), saved in 4_laws_and_rules/input/pgm/raw/.

Most RPUC documents are SCANS. 4_laws_and_rules/code/ocr_pgm.py makes the text first:
  <name>.ocr.pdf      whole document, OCR'd (Tesseract cat+spa)
  <name>.columns.txt  pages printed in two columns, OCR'd column by column (the articles themselves)
Each document is described by its "parts": which pages (or the columns file) hold the memòria and the articles.
Pieces are cut at "Art. N" / "Article N" / additional-provision headings. OCR pieces carry a note.
"""
import json, os, re
import pymupdf

RAW = "4_laws_and_rules/input/pgm/raw"
OUT = "4_laws_and_rules/input/pgm/pgm_chunks.jsonl"
RPUC = "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/"
OCR_NOTE = ("OCR from a scanned RPUC document: wording checked by sample, but verify every number "
            "against the PDF page before using it")

DOCS = [
    {"file": "MPGM-1999-art225", "exp": "96749", "num": "1998/002587/B", "published": "19990203",
     "norm": "MPGM 1999 art. 225 (Barcelona)",
     "title": "Modificació de l'article 225 de les NNUU del PGM: ús d'habitatge en planta baixa i entresolat",
     "parts": [("memoria", "pages", 1, 7), ("art225", "columns", None, None)],
     "note": "document from the provisional-approval stage (Sept 1998) filed as the expedient's document unitari"},
    {"file": "MPGM-2004-habitatges-parcela", "exp": "215050", "num": "2004/012783/B", "published": "20041210",
     "norm": "MPGM 2004 nombre màxim d'habitatges (Barcelona)",
     "title": "Modificació de les NNUU del PGM en relació a la limitació del nombre màxim d'habitatges a la ciutat de Barcelona",
     "parts": [("memoria", "pages", 1, 20), ("articulat", "columns", None, None)]},
    {"file": "MPGM-B1600", "exp": "283290", "num": "2018/067588/B", "published": "20181214",
     "norm": "MPGM B1600 habitatge protecció pública SUC (Barcelona)",
     "title": "Modificació del PGM per a l'obtenció d'habitatge de protecció pública al sòl urbà consolidat de Barcelona",
     "parts": [("document", "pages", 1, None)],
     "note": "TSJC ruling 6/7/2021 (RCA 33/2019) declared the Disposició final segona of these NNUU null; the rest stands"},
    {"file": "MPGM-B1600-acord-sentencia-2022", "exp": "283290", "num": "2018/067588/B", "published": "20220214",
     "norm": "MPGM B1600 habitatge protecció pública SUC (Barcelona)",
     "title": "Acord Subcomissió d'Urbanisme 31/5/2022: assabentat sentència TSJC RCA 33/2019 (nul·litat Disposició final segona)",
     "parts": [("acord", "pages", 1, None)], "text_layer": True},
    # AMB compilations (saved by hand from amb.cat NUMAMB): real text, cut at "Art. N."
    {"file": "OME", "exp": None, "num": "OME 1978 (AMB recull)", "published": "19780718",
     "norm": "Ordenances metropolitanes d'edificació (OME)",
     "title": "Ordenances metropolitanes d'edificació (aprovació definitiva 15/06/1978, BOP 18/07/1978)",
     "parts": [("ome", "pages", 1, None)], "text_layer": True, "split": True,
     "url": "https://www.amb.cat/web/territori/gestio-i-organitzacio/numamb",
     "note": "AMB compilation, information only ('no té cap valor normatiu'); in Barcelona the dwelling module is 80 m² "
             "(MPGM 2004, art. 318), not the 100 m² of OME art. 180"},
    {"file": "OM-rehabilitacio", "exp": None, "num": "OMR 1985 (AMB recull)", "published": "19850515",
     "norm": "Ordenança metropolitana de rehabilitació",
     "title": "Ordenança metropolitana de rehabilitació (aprovació definitiva 18/04/1985, BOP 15/05/1985)",
     "parts": [("omr", "pages", 1, None)], "text_layer": True, "split": True,
     "url": "https://www.amb.cat/web/territori/gestio-i-organitzacio/numamb",
     "note": "AMB compilation, information only ('no té cap valor normatiu'); modifications up to 31/12/2009"},
]
START = re.compile(r"^[\W_]{0,3}\s*(Art(?:icle|\.)\s*\d+[\w.]*(?:\s?(?:bis|ter|quater))?\.?(?:\s.*)?|"
                   r"Disposici(?:ó|ons)\s+(?:addicional|transitòria|derogatòria|final)s?\b.*|"
                   r"DISPOSICIONS\s+ADDICIONALS.*|(?:PRIMERA|SEGONA|TERCERA|QUARTA|CINQUENA)\.\s.*)$")
M2 = re.compile(r"(\d)\s?(?:m[£é?*íÿ²2]|n[xy]|mí)(?=[\s.,;:)]|$)")


def clean(lines):
    """Drop OCR noise (stray 1-2 character lines from stamps and margins), fix m², join split 'Art.' headings."""
    out = []
    for l in lines:
        l = l.strip()
        # never drop letters/digits: in one-word-per-line OCR, "no", "de", "i" are real words ("no comptabilitzarà")
        if not l or (len(l) <= 3 and not re.search(r"[\wÀ-ÿ]", l)):
            continue
        if re.fullmatch(r"[\W_—–-]{3,}", l):   # rules / underlines
            continue
        if out and re.fullmatch(r"Art(?:icle|\.)", out[-1]) and re.match(r"^\d", l):
            out[-1] = f"{out[-1]} {l}"
            continue
        out.append(M2.sub(r"\1 m²", l))
    return out


NEW_PARA = re.compile(r"^(\d+\.|[a-zI]\)|[IVX]+\.|Art(?:icle|\.)\s|Secció|Capítol|Títol|Zona\s|Disposici|PRIMERA|SEGONA|TERCERA|QUARTA)")


def paragraphs(lines):
    """OCR of justified text gives one word per line; rebuild paragraphs, breaking only at numbered points/headings."""
    paras = []
    for l in lines:
        if not paras or NEW_PARA.match(l):
            paras.append(l)
        elif paras[-1].endswith("-") and l[:1].islower():
            paras[-1] = paras[-1][:-1] + l
        else:
            paras[-1] += " " + l
    return "\n".join(paras)


def columns_text(page):
    """OCR'd page -> text in reading order. Tesseract often joins a row across two columns, so we go
    word by word: find an empty vertical gap (gutter) near the middle, put each word on its side,
    then rebuild lines from the word heights. Pages without a gutter are read as one column."""
    ws = page.get_text("words")
    if not ws:
        return ""
    W = page.rect.width
    cover = [0] * (int(W) + 2)
    for w in ws:
        for x in range(max(0, int(w[0])), min(len(cover) - 1, int(w[2])) + 1):
            cover[x] += 1
    lo, hi = int(W * 0.35), int(W * 0.65)
    gutter, run = None, []
    for x in range(lo, hi):
        if cover[x] <= 1:
            run.append(x)
            if len(run) >= 6 and (gutter is None or len(run) > gutter[1]):
                gutter = (run[len(run) // 2], len(run))
        else:
            run = []
    cols = [ws] if gutter is None else [[w for w in ws if (w[0] + w[2]) / 2 < gutter[0]],
                                        [w for w in ws if (w[0] + w[2]) / 2 >= gutter[0]]]
    out = []
    for col in cols:
        lines = []
        for w in sorted(col, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
            yc = (w[1] + w[3]) / 2
            if lines and abs(lines[-1][0] - yc) < 4:
                lines[-1][1].append(w)
            else:
                lines.append([yc, [w]])
        out += [" ".join(x[4] for x in sorted(l[1], key=lambda w: w[0])) for l in lines]
    return "\n".join(out)


def read_part(d, kind, first, last):
    if kind == "columns":
        with open(f"{RAW}/{d['file']}.columns.txt", encoding="utf-8") as f:
            return [(None, f.read())]
    path = f"{RAW}/{d['file']}.pdf" if d.get("text_layer") else f"{RAW}/{d['file']}.ocr.pdf"
    saved = f"{RAW}/{d['file']}.ocr.json"            # page texts of the OCR copy (the 1.4 GB .ocr.pdf was deleted to save space)
    if not d.get("text_layer") and not os.path.exists(path) and os.path.exists(saved):
        pages = json.load(open(saved, encoding="utf-8"))
        last = last or len(pages)
        return [(i + 1, pages[str(i + 1)]) for i in range(first - 1, last)]
    if not os.path.exists(path):
        return None
    doc = pymupdf.open(path)
    last = last or doc.page_count
    read = (lambda p: p.get_text()) if d.get("text_layer") else columns_text
    return [(i + 1, read(doc[i])) for i in range(first - 1, last)]


def chunk_doc(d):
    out, seen = [], {}
    for part, kind, first, last in d["parts"]:
        pages = read_part(d, kind, first, last)
        if pages is None:
            return None
        chunks, cur = [], None
        for page_no, text in pages:
            for line in clean(text.splitlines()):
                if START.match(line) and len(line) < 140 and part != "memoria" and (d.get("split") or not d.get("text_layer")):
                    cur = {"id": re.sub(r"[^a-z0-9.]+", "-", line.lower())[:32].strip("-"), "title": line,
                           "page": page_no, "lines": [line]}
                    chunks.append(cur)
                    continue
                if cur is None:
                    cur = {"id": part, "title": f"{d['title']} ({part})", "page": page_no or first, "lines": []}
                    chunks.append(cur)
                cur["lines"].append(line)
        for c in chunks:
            bid = f"{d['file']}:{c['id']}"
            k = seen.get(bid, 0)
            seen[bid] = k + 1
            piece = {
                "norm_id": f"RPUC {d['num']}", "norm": d["norm"], "level": "pgm",
                "block_id": bid + (f"-{k + 1}" if k else ""), "block_type": "planejament",
                "title": c["title"].replace("\t", " "), "in_force_from": d["published"],
                "source_url": d.get("url") or RPUC + d["exp"],
                "text": c["lines"] and (re.sub(r"(\w)[-\xad]\n(\w)", r"\1\2", "\n".join(c["lines"])).replace("\t", " ")
                                        if d.get("text_layer")
                                        else paragraphs(c["lines"])),
            }
            notes = [n for n in (d.get("note"), None if d.get("text_layer") else OCR_NOTE) if n]
            if notes:
                piece["note"] = "; ".join(notes)
            out.append(piece)
    return out


def main():
    all_chunks, todo = [], []
    for d in DOCS:
        chunks = chunk_doc(d)
        if chunks is None:
            todo.append(d["file"])
            print(f"{d['file']:34} NEEDS OCR (run 4_laws_and_rules/code/ocr_pgm.py)")
            continue
        all_chunks += chunks
        print(f"{d['file']:34} {len(chunks):3} pieces")
    with open(OUT, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print("PGM pieces:", len(all_chunks), "| still need OCR:", todo)


if __name__ == "__main__":
    main()
