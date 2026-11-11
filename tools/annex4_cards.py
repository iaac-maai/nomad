"""NOMAD - Decret 141/2012 Annex 4 (conversions) on the rule cards. No rule value changes: only which card applies when.

1. Every Decret 141 card gets `scope` (new buildings / conversions, Annex 4 Grup B, C or D), `conversion` (what changes for
   a conversion, in plain words) and `source.page` (its page in the official PDF).
2. height-04C and patio-01 get `extra_quotes`: the other sentences that decide them, each with its page.
3. rules/annex4.json: the Annex 4 note for the Rule cards page: Grups B, C and D word for word, and the parts of
   Annex 1 apartat 2 that apply in Grups B and D (2.1, 2.2.2, 2.6; whether the lift rule 2.4.1 a) applies is open).
Every quote must be found word for word in the official PDF (the one tools/get_rulebook.py downloads, pinned in
nomad/04_Website/rulebook/sources.lock.json), or the script stops. The pages are the PDF's own page numbers.

The consolidated PDF prints Grup C as "( 50%": the "≤" is missing. It is in the original DOGC 6245 (2 Nov 2012,
page 53451); the note says so, and the comparison ignores the "≤".
Writes the same data into 07_Rules_and_evaluation/rules/rules.json (the source) and 04_Website/data/nomad.json (the site).
Needs pymupdf.   Run from the repo root:  python tools/annex4_cards.py
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "nomad" / "02_Code" / "data" / "catalonia" / "raw" / "D141-2012.pdf"
RULES = ROOT / "nomad" / "07_Rules_and_evaluation" / "rules" / "rules.json"
ANNEX4 = ROOT / "nomad" / "07_Rules_and_evaluation" / "rules" / "annex4.json"
SITE = ROOT / "nomad" / "04_Website" / "data" / "nomad.json"
LOCK = ROOT / "nomad" / "04_Website" / "rulebook" / "sources.lock.json"
DOGC = {"issue": "DOGC 6245, 2 Nov 2012", "page": 53451,
        "url": "https://portaldogc.gencat.cat/utilsEADOP/PDF/6245/1267583.pdf"}

BOTH = "new buildings (Annex 1) and conversions (Annex 4 Grups B, C and D keep it)"
SCOPE = {   # rule_id -> (scope, what changes for a conversion)
    "CAT-141-2012-area-01": (BOTH, "unchanged"),
    "CAT-141-2012-facade-01": (BOTH, "unchanged"),
    "CAT-141-2012-bedroom-01": (BOTH, "unchanged"),
    "CAT-141-2012-bedroom-02": (BOTH, "unchanged"),
    "CAT-141-2012-living-01": (BOTH, "unchanged"),
    "CAT-141-2012-window-01": (BOTH, "unchanged"),
    "CAT-141-2012-bath-01": (BOTH, "unchanged"),
    "CAT-141-2012-height-01": ("new buildings (Annex 1)",
                                "a conversion uses the 2,40 m card (Annex 4 Grups B, C and D)"),
    "CAT-141-2012-height-04C": ("conversions (Annex 4 Grups B, C and D)",
                                "2,40 m; 2,20 m in bathrooms, kitchens and circulation; 2,30 m over at most 20 % of a room"),
    "CAT-141-2012-patio-01": ("new buildings (Annex 1); conversions: see the change",
                                "not required in Grup C; areas −10 % in Grups B and D (8,1 m² / 5,4 m²)"),
}
NOTE_04C = ("Annex 4 sets 2,40 m in place of 2,50 m in Grups A to F (the same sentence each time), so it applies to a "
            "shop conversion in Grups B, C and D. The rest of Annex 1 3.5 stays: 2,20 m in bathrooms, kitchens and "
            "circulation, and 2,30 m over at most 20 % of a room.")
EXTRA = {
    "CAT-141-2012-height-04C": [
        ("Annex 1 · 3.5 Alçada mínima habitable",
         "En el cas de cambres higièniques, cuines i espais de circulació, aquesta alçada no serà inferior a 2,20 m."),
        ("Annex 1 · 3.5 Alçada mínima habitable",
         "Al menjador, sala d’estar i habitacions s’admetrà, excepcionalment, 2,30 m d’alçada per al pas tècnic "
         "d’instal·lacions i per a elements estructurals que no afectin més del 20% de la superfície de la peça."),
    ],
    "CAT-141-2012-patio-01": [
        ("Annex 4 · Apartat 2 · Grup C",
         "Grup C Intervencions: canvi d’ús d’un edifici (≤ 50% de la superfície construïda sobre o sota rasant). "
         "Annex aplicable i excepcions: annex 1 amb les excepcions següents: Apartat 2 íntegrament exempt, excepte 2.2.1."),
        ("Annex 4 · Apartat 2 · Grup D",
         "Grup D Intervencions: canvi d’ús d’un edifici (> 50% de la superfície construïda sobre o sota rasant). "
         "Annex aplicable i excepcions: annex 1 amb les excepcions següents: Apartat 2.5.1 s’accepta una reducció "
         "del 10% en les superfícies."),
    ],
}
GROUPS = [
    ("B", "the whole building changes use",
     "Grup B Intervencions: canvi d’ús total d’un edifici (sobre o sota rasant). "
     "Annex aplicable i excepcions: annex 1 amb les excepcions següents: Apartat 2.5.1 s’accepta una reducció del 10% "
     "en les superfícies. Apartat 3.5: mínim de 2,40 m en comptes de 2,50 m, la resta igual.",
     "Annex 1 applies in full, except: ventilation patios (2.5.1) may be 10 % smaller (8,1 m² / 5,4 m²); clear height "
     "2,40 m. So apartat 2 applies (below)."),
    ("C", "≤ 50 % of the building's built area changes use",
     "Grup C Intervencions: canvi d’ús d’un edifici (≤ 50% de la superfície construïda sobre o sota rasant). "
     "Annex aplicable i excepcions: annex 1 amb les excepcions següents: Apartat 2 íntegrament exempt, excepte 2.2.1. "
     "Apartat 3.5: mínim de 2,40 m en comptes de 2,50 m, la resta igual.",
     "Annex 1 applies, except: apartat 2 (the building's shared parts) does not apply, only 2.2.1 (each home is reached "
     "from a public, common or annex space); clear height 2,40 m."),
    ("D", "> 50 % of the building's built area changes use",
     "Grup D Intervencions: canvi d’ús d’un edifici (> 50% de la superfície construïda sobre o sota rasant). "
     "Annex aplicable i excepcions: annex 1 amb les excepcions següents: Apartat 2.5.1 s’accepta una reducció del 10% "
     "en les superfícies. Apartat 3.5: mínim de 2,40 m en comptes de 2,50 m, la resta igual.",
     "Annex 1 applies in full, except: ventilation patios (2.5.1) may be 10 % smaller (8,1 m² / 5,4 m²); clear height "
     "2,40 m. So apartat 2 applies (below)."),
]
APARTAT2_D = [
    ("2.1", "accessible route to every home",
     "Tots els edificis plurifamiliars d’obra nova i els que resultin de la reconversió d’un edifici existent i d’obres "
     "de gran rehabilitació que afectin el conjunt de l’edifici han de disposar d’un itinerari accessible per accedir a "
     "cada un dels habitatges."),
    ("2.2.2", "1,50 m landing in front of the lift",
     "Els espais comuns situats davant de la porta de l’ascensor han de permetre la inscripció d’un cercle d’1,50 m de "
     "diàmetre."),
    ("2.6", "shared facilities from 8 homes",
     "Els edificis plurifamiliars, a partir de 8 habitatges, han de disposar d’un espai, per edifici o escala, per a ús "
     "de la comunitat, accessible des de l’exterior o zones comunes, d’1,20 m × 0,80 m com a mínim i una alçada no "
     "inferior a 2,20 m."),
]


def fold(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("ŀ", "l").replace("­", "").replace("≤", "")
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)
    return re.sub(r"\s+", " ", s).replace("( ", "(").strip()


def main():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))["docs"]["Decret 141/2012"]
    doc = pymupdf.open(PDF)
    pages = [fold(p.get_text()) for p in doc]
    # quotes may run over a page break: also search each page joined with the next, minus the page footer
    joined = [fold(re.sub(r"Portal Jurídic de Catalunya\s*\d+\s*$", "", doc[i].get_text().strip()) + " " +
                   (doc[i + 1].get_text() if i + 1 < len(doc) else "")) for i in range(len(doc))]

    def page_of(quote):
        q = fold(quote)
        for i, t in enumerate(pages):
            if q in t:
                return i + 1
        for i, t in enumerate(joined):
            if q in t:
                return i + 1
        sys.exit(f"NOT FOUND in {PDF.name}: {quote[:90]}")

    cards = json.loads(RULES.read_text(encoding="utf-8"))
    for c in cards:
        if c["source"]["norm"] != "Decret 141/2012":
            continue
        scope, change = SCOPE[c["rule_id"]]
        c["scope"], c["conversion"] = scope, change
        c["source"]["page"] = page_of(c["quote"])
        if c["rule_id"] == "CAT-141-2012-height-04C":
            c["note"] = NOTE_04C
        if c["rule_id"] in EXTRA:
            c["extra_quotes"] = [{"article": a, "quote": q, "page": page_of(q)} for a, q in EXTRA[c["rule_id"]]]
        print(f"{c['rule_id']:<26} p. {c['source']['page']:>2}  {scope}")
    annex4 = {
        "about": "Decret 141/2012 Annex 4: which rules apply when part of a building (a shop) becomes homes. "
                 "Built by tools/annex4_cards.py; every quote checked word for word in the official PDF.",
        "source": {"norm": "Decret 141/2012", "url": lock["url"], "version_date": lock["version_date"]},
        "symbol_note": (f"The consolidated PDF prints Grup C as \"( 50%\": the \"≤\" is missing. The original "
                    f"{DOGC['issue']}, page {DOGC['page']}, prints \"(≤ 50% …\"."),
        "dogc": DOGC,
        "groups": [{"grup": g, "when": w, "quote": q, "page": page_of(q), "plain": p} for g, w, q, p in GROUPS],
        "grup_d_apartat2": [{"apartat": a, "what": w, "quote": q, "page": page_of(q)} for a, w, q in APARTAT2_D],
        "grup_d_note": "Grups B and D: apartat 2 applies (accessible route, 1.50 m landing, shared facilities from 8 homes). "
                       "Whether the lift rule 2.4.1 a) applies to conversions is still open.",
        "decide": "Grup B, C or D: the shop's built area ÷ the building's total built area (above and below ground), "
                  "from the Catastro CAT data (tools/annex4_grup.py). Grup B when the shop is the whole building (no "
                  "homes in it).",
    }
    for g in annex4["groups"]:
        print(f"Grup {g['grup']}  p. {g['page']}")
    for a in annex4["grup_d_apartat2"]:
        print(f"apartat {a['apartat']:<9} p. {a['page']}")
    RULES.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    ANNEX4.write_text(json.dumps(annex4, ensure_ascii=False, indent=1), encoding="utf-8")
    site = json.loads(SITE.read_text(encoding="utf-8"))
    site["rules"], site["annex4"] = cards, annex4
    SITE.write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()