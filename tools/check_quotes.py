"""NOMAD - check the 16 rule cards' source sentences against the official PDFs.

For a PDF with text (Decret 141/2012, CTE): the quote must be found word for word in the PDF's text (spaces, line breaks,
line-break hyphens and apostrophe styles are ignored). For a scan with no text layer (MPGM 2004): the script cannot
read it; it prints the page the card says was checked by eye, so a person can look again.
Needs the PDFs from tools/get_rulebook.py and pymupdf.   Run from the repo root:  python tools/check_quotes.py
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Bhavini_NOMAD Files" / "02_Code" / "data"
RULES = ROOT / "Bhavini_NOMAD Files" / "07_Rules_and_evaluation" / "rules" / "rules.json"
PDF = {"Decret 141/2012": "catalonia/raw/D141-2012.pdf", "MPGM 2004": "pgm/raw/MPGM-2004-habitatges-parcela.pdf",
       "CTE-DB-SUA": "national/cte_db/DBSUA.pdf", "CTE DB-SUA": "national/cte_db/DBSUA.pdf"}


def fold(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("ŀ", "l").replace("­", "")
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)                        # a word split at the end of a line
    return re.sub(r"\s+", " ", s).strip()


def main():
    cards, bad = json.loads(RULES.read_text(encoding="utf-8")), 0
    texts = {}
    for c in cards:
        norm = c["source"]["norm"]
        rel = next((v for k, v in PDF.items() if norm.startswith(k)), None)
        if rel is None or not (DATA / rel).exists():
            print(f"?    {c['rule_id']:<26} no PDF for '{norm}' (run tools/get_rulebook.py)"); bad += 1; continue
        if rel not in texts:
            texts[rel] = fold(" ".join(p.get_text() for p in pymupdf.open(DATA / rel)))
        q = c.get("quote") or ""
        if len(texts[rel]) < 500:                                    # a scan
            print(f"EYE  {c['rule_id']:<26} scan, no text layer: {c.get('checked', 'NOT CHECKED')}")
            bad += "checked" not in c
        elif q and fold(q) in texts[rel]:
            print(f"OK   {c['rule_id']:<26} found word for word")
        else:
            print(f"FAIL {c['rule_id']:<26} quote not found in {rel}"); bad += 1
    print(f"\n{len(cards) - bad} of {len(cards)} cards checked")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
