"""Nomad - Step 1d (OCR): make searchable copies <name>.ocr.pdf of the scanned RPUC documents.

Uses Tesseract (installed with winget, UB-Mannheim build) through PyMuPDF, languages Catalan + Spanish
(tessdata_best files in tools/tessdata/). The left ~9% of each page is cropped: it holds the
binding holes, which Tesseract otherwise reads as rows of 'e' and 'o'.
Run:  python 4_laws_and_rules/code/ocr_pgm.py [file-stem ...]   (default: all scans listed in fetch_pgm.DOCS)
"""
import os, sys, time
import pymupdf

RAW = "4_laws_and_rules/input/pgm/raw"
TESSDATA = os.path.abspath("tools/tessdata")
TESSERACT_DIR = r"C:\Program Files\Tesseract-OCR"
LEFT_CROP = 0.09
DPI = 300


def has_text(path):
    doc = pymupdf.open(path)
    return sum(len(p.get_text().strip()) for p in doc) > 60 * doc.page_count


def ocr(stem):
    src, dst = f"{RAW}/{stem}.pdf", f"{RAW}/{stem}.ocr.pdf"
    doc, out = pymupdf.open(src), pymupdf.open()
    t0 = time.time()
    for i, page in enumerate(doc):
        r = page.rect
        clip = pymupdf.Rect(r.x0 + r.width * LEFT_CROP, r.y0, r.x1, r.y1)
        pix = page.get_pixmap(dpi=DPI, clip=clip)
        out.insert_pdf(pymupdf.open("pdf", pix.pdfocr_tobytes(language="cat+spa", tessdata=TESSDATA)))
        if (i + 1) % 10 == 0:
            print(f"  {stem}: {i + 1}/{doc.page_count} pages ({time.time() - t0:.0f}s)", flush=True)
    out.save(dst, garbage=3, deflate=True)
    print(f"{stem}: {doc.page_count} pages -> {dst} ({time.time() - t0:.0f}s)", flush=True)


# Pages printed in two columns. Tesseract interleaves them line by line, so OCR each column separately:
# "right" = keep only the right column (1999: "redactat actual | redactat proposat" -> the new wording),
# "both"  = left column then right column (2004: the articulat is set like a newspaper).
COLUMNS = {"MPGM-1999-art225": ([8, 9, 10, 11], "right"),
           "MPGM-2004-habitatges-parcela": ([21, 22, 23, 24, 25], "both")}


def ocr_columns(stem):
    pages, mode = COLUMNS[stem]
    doc, parts = pymupdf.open(f"{RAW}/{stem}.pdf"), []
    halves = [(0.50, 1.0)] if mode == "right" else [(LEFT_CROP, 0.53), (0.50, 1.0)]
    for n in pages:
        r = doc[n - 1].rect
        for a, b in halves:
            clip = pymupdf.Rect(r.x0 + r.width * a, r.y0, r.x0 + r.width * b, r.y1)
            pix = doc[n - 1].get_pixmap(dpi=DPI, clip=clip)
            parts.append(pymupdf.open("pdf", pix.pdfocr_tobytes(language="cat+spa", tessdata=TESSDATA))[0].get_text())
    with open(f"{RAW}/{stem}.columns.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"{stem}: {mode} column(s) of pages {pages} -> {RAW}/{stem}.columns.txt", flush=True)


def main():
    os.environ["TESSDATA_PREFIX"] = TESSDATA
    os.environ["PATH"] = TESSERACT_DIR + os.pathsep + os.environ["PATH"]
    sys.path.insert(0, "4_laws_and_rules/code")
    from fetch_pgm import DOCS
    stems = sys.argv[1:] or [d["file"] for d in DOCS if not has_text(f"{RAW}/{d['file']}.pdf")]
    for s in stems:
        if s.endswith(":columns"):
            ocr_columns(s[:-8])
        else:
            ocr(s)


if __name__ == "__main__":
    main()
