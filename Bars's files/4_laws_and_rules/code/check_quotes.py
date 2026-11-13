"""NOMAD - check the 16 rule cards' source sentences against the official PDFs.

For a PDF with text (Decret 141/2012, CTE): the quote must be found word for word in the PDF's text (spaces, line breaks,
line-break hyphens and apostrophe styles are ignored). For a scan with no text layer (MPGM 2004): the script cannot
read it; it prints the page the card says was checked by eye, so a person can look again.
Needs the PDFs from Bars's files/4_laws_and_rules/code/get_rulebook.py and pymupdf.
Run from the repo root:  python "Bars's files/4_laws_and_rules/code/check_quotes.py"
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
BARS = ROOT / "Bars's files"
DATA = ROOT / "nomad" / "02_Code" / "data"
RULES = BARS / "4_laws_and_rules" / "output" / "rules" / "rules.json"
ANNEX4 = RULES.with_name("annex4.json")
PDF = {"Decret 141/2012": "catalonia/raw/D141-2012.pdf", "MPGM 2004": "pgm/raw/MPGM-2004-habitatges-parcela.pdf",
       "CTE-DB-SUA": "national/cte_db/DBSUA.pdf", "CTE DB-SUA": "national/cte_db/DBSUA.pdf"}


def fold(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("ŀ", "l").replace("­", "")
    s = s.replace("≤", "")                                          # the consolidated Decret 141 PDF drops it (Annex 4 Grup C)
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)                        # a word split at the end of a line
    return re.sub(r"\s+", " ", s).replace("( ", "(").strip()


def check_annex4(cards, bad):
    """The Annex 4 quotes (extra quotes on the cards, rules/annex4.json): word for word, and on the page they give."""
    pdf = pymupdf.open(DATA / PDF["Decret 141/2012"])
    pages = [fold(p.get_text()) for p in pdf]
    quotes = [(c["rule_id"] + " +", q["quote"], q["page"]) for c in cards for q in c.get("extra_quotes", [])]
    quotes += [(c["rule_id"] + " p.", c["quote"], c["source"]["page"]) for c in cards if c["source"].get("page")]
    a4 = json.loads(ANNEX4.read_text(encoding="utf-8"))
    quotes += [("Annex 4 Grup " + g["grup"], g["quote"], g["page"]) for g in a4["groups"]]
    quotes += [("Grup D apartat " + a["apartat"], a["quote"], a["page"]) for a in a4["grup_d_apartat2"]]
    for name, q, page in quotes:
        here = fold(q) in pages[page - 1] or fold(q) in fold(pages[page - 1] + " " + (pages[page] if page < len(pages) else ""))
        print(f"{'OK  ' if here else 'FAIL'} {name:<30} p. {page}")
        bad += not here
    return bad, len(quotes)


def main():
    cards, bad = json.loads(RULES.read_text(encoding="utf-8")), 0
    texts = {}
    for c in cards:
        norm = c["source"]["norm"]
        rel = next((v for k, v in PDF.items() if norm.startswith(k)), None)
        if rel is None or not (DATA / rel).exists():
            print(f"?    {c['rule_id']:<26} no PDF for '{norm}' (run Bars's files/4_laws_and_rules/code/get_rulebook.py)"); bad += 1; continue
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
    print("\nAnnex 4 (conversions): the extra quotes, rules/annex4.json and each Decret 141 card's page")
    bad4, n4 = check_annex4(cards, 0)
    print(f"\n{n4 - bad4} of {n4} Annex 4 quotes found on their page")
    sys.exit(1 if bad or bad4 else 0)


if __name__ == "__main__":
    main()
