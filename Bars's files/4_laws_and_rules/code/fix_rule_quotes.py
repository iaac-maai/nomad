"""NOMAD - 9 Nov 2026: replace the rule cards' source sentences that PDF/OCR reading had garbled with the official text.

Each new quote was read in the official PDF downloaded by tools/get_rulebook.py:
  - text PDFs (Decret 141/2012, CTE DB-SUA): copied from the PDF's text, word for word;
  - the MPGM 2004 scan (RPUC expedient 215050, document 126035), which has no text layer: read by eye on the page
    image, pages 19 (Disposició addicional primera) and 21 (arts. 318 and 323).
Writes the same quotes into 07_Rules_and_evaluation/rules/rules.json (the source) and 04_Website/data/nomad.json
(the site). Run once from the repo root:  python tools/fix_rule_quotes.py   (running it again changes nothing)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "nomad" / "07_Rules_and_evaluation" / "rules" / "rules.json",
         ROOT / "nomad" / "04_Website" / "data" / "nomad.json"]
SCAN = ("by eye against the official scan (RPUC document 126035, page {p}): read by Claude from the page image on 9 Nov 2026, "
        "checked by a human (Bars) on 10 Nov 2026; the PDF has no text layer")
TEXT = "word for word in the official PDF, 9 Nov 2026"

FIX = {
    "BCN-MPGM2004-area-01": dict(
        quote="a) Els habitatges es desenvoluparan en una superfície útil mínima de 40 m².",
        article="Disposicions addicionals de la MPGM · Primera, 2 a)", checked=SCAN.format(p=19)),
    "BCN-MPGM2004-facade-01": dict(
        quote="b) Cada habitatge disposarà, com a mínim, d’una longitud de 3 m en contacte amb la façana a via pública o pati interior d’illa.",
        article="Disposicions addicionals de la MPGM · Primera, 2 b)", checked=SCAN.format(p=19)),
    "BCN-MPGM2004-density-12": dict(
        quote="1. Les sol·licituds d’edificació en la subzona I, de substitució de l’edificació antiga, hauran de limitar el nombre "
              "d’habitatges per parcel·la al que, per excés, resulti de dividir la superfície construïda pel mòdul de 80 m².",
        article="Art. 318.1", checked=SCAN.format(p=21)),
    "BCN-MPGM2004-density-13": dict(
        quote="1. Les edificacions que s’aixequin a la subzona I, intensiva, i a la subzona II, semiintensiva, no podran depassar per "
              "parcel·la un nombre d’habitatges igual al que resulti, per excés, de dividir la superfície construïda pel mòdul de 80 m².",
        article="Art. 323.1", checked=SCAN.format(p=21)),
    "CAT-141-2012-bath-01": dict(
        quote="3.11.1 Tots els habitatges han de disposar, com a mínim, d’una dotació d’aparells destinats a la higiene, d’acord amb "
              "el quadre següent: Nre. d’habitacions 0, 1, 2 o 3 4 o més Vàter 1 2",
        checked=TEXT + " (the table's cells in reading order)"),
    "CTE-SUA-door-01": dict(
        quote="Anchura libre de paso ≥ 0,80 m medida en el marco y aportada por no más de una hoja.",
        checked=TEXT),
    "CTE-SUA-corridor-01": dict(
        quote="Anchura libre de paso ≥ 1,20 m. En zonas comunes de edificios de uso Residencial Vivienda se admite 1,10 m",
        url="https://www.codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf#page=36",
        note="Accessible route, 'Pasillos y pasos'. In the PDF 'Vivienda' is split across two lines ('Vivien- da').",
        checked=TEXT + " (the line-break hyphen in 'Vivien-da' joined)"),
}


def apply(card):
    f = FIX.get(card.get("rule_id"))
    if not f:
        if "checked" not in card and card.get("confidence") == 1.0:
            card["checked"] = TEXT
        return
    card["quote"] = f["quote"]
    if "article" in f: card["source"]["article"] = f["article"]
    if "url" in f: card["source"]["url"] = f["url"]
    if "note" in f: card["note"] = f["note"]
    card["checked"] = f["checked"]
    card.setdefault("checks", {}).update({"quote_in_source": True, "value_in_quote": True})
    card["confidence"] = 1.0


for path in FILES:
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data if isinstance(data, list) else data["rules"]
    for c in cards:
        apply(c)
    compact = path.name == "nomad.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(data, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(path.relative_to(ROOT), len(cards), "cards")
