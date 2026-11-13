# Law texts: the rule cards checked against the official PDFs (9 Nov 2026)

Every rule card on the website shows the sentence of the law its number comes from. On 9 Nov 2026 each sentence was
compared with the official PDF, downloaded from the body that publishes it (`Bars's files/4_laws_and_rules/code/get_rulebook.py`).

- **Text PDFs** (Decret 141/2012 from the Portal Jurídic, CTE DB-SUA from codigotecnico.org): the sentence must be
  found word for word in the PDF's text. `python "Bars's files/4_laws_and_rules/code/check_quotes.py"` repeats this check.
- **Scans** (MPGM 2004 from the RPUC, document 126035): the official PDF is a picture of the pages, with no text.
  The old sentences came from our own OCR (Tesseract), which made mistakes. They were replaced by the text read on
  the page images (rendered at 110–150 dpi) and typed by Claude, the AI assistant; this is not OCR. **Checked by a
  human (Bars) on 10 Nov 2026**: numbers, articles and sentences match the scan (pages 19 and 21);
  `docs/law_check_scans/CHECK.md` shows each page crop next to our quote. `check_quotes.py` cannot read a scan; it
  lists the page to look at.

Result: all 16 cards now match the official text. No quote had to be removed. No rule value changed.
The fixes are applied by `tools/fix_rule_quotes.py` to both `07_Rules_and_evaluation/rules/rules.json` and the site's
`04_Website/data/nomad.json`. Each card now says how it was checked (`"checked"`), and the website shows it.

## What changed

| Card | Source | Problem | Before | After (official text) |
| --- | --- | --- | --- | --- |
| BCN-MPGM2004-area-01 | MPGM 2004, Disposició addicional primera 2 a), scan p. 19 | OCR errors | `S a) Els habitatges es desenvoluparan en una y superficie Útil mínima de 40 m².` | `a) Els habitatges es desenvoluparan en una superfície útil mínima de 40 m².` |
| BCN-MPGM2004-facade-01 | MPGM 2004, Disposició addicional primera 2 b), scan p. 19 | OCR errors ("t i d'una"); quote held a), b) and c) | `… disposarà, com a mínim, t i d'una longitud de 3 m …` (+ a, c) | `b) Cada habitatge disposarà, com a mínim, d’una longitud de 3 m en contacte amb la façana a via pública o pati interior d’illa.` |
| BCN-MPGM2004-density-12 | MPGM 2004, art. 318.1, scan p. 21 | OCR errors ("sollicituds", "parcel-la", "construida") and the number "2." of the next paragraph | `Les sollicituds d'edificació … per parcel-la … construida pel mòdul de 80 m² 2.` | `1. Les sol·licituds d’edificació en la subzona I, de substitució de l’edificació antiga, hauran de limitar el nombre d’habitatges per parcel·la al que, per excés, resulti de dividir la superfície construïda pel mòdul de 80 m².` |
| BCN-MPGM2004-density-13 | MPGM 2004, art. 323.1, scan p. 21 | OCR mixed the page heading into the sentence | `… no podran —depassar per parcella un nombre Es) DIFICACIÓ DE LES NORMES URBANISTIQUES XIM D'HABITATGES PER PARCEL:LA, DINS EL d'habitatges …` | `1. Les edificacions que s’aixequin a la subzona I, intensiva, i a la subzona II, semiintensiva, no podran depassar per parcel·la un nombre d’habitatges igual al que resulti, per excés, de dividir la superfície construïda pel mòdul de 80 m².` |
| CAT-141-2012-bath-01 | Decret 141/2012, Annex 1 3.11.1, p. 18 | table markup (`|`, `[/Tabla]`) added when the PDF was read | `Nre. d’habitacions \| 0, 1, 2 o 3 \| 4 o més Vàter \| 1 \| 2 … [/Tabla] …` | `3.11.1 Tots els habitatges han de disposar, com a mínim, d’una dotació d’aparells destinats a la higiene, d’acord amb el quadre següent: Nre. d’habitacions 0, 1, 2 o 3 4 o més Vàter 1 2` (the table's cells in reading order) |
| CTE-SUA-door-01 | CTE DB-SUA, Anejo A, p. 36 | started in the middle of a word ("…da se admite") and held table markup; its link pointed to `#page=35` (fixed on 10 Nov) | `[Tabla] da se admite 1,10 m - \| Estrechamientos … - \| Puertas \| - \| Anchura libre de paso ≥ 0,80 m …` (link `#page=35`) | `Anchura libre de paso ≥ 0,80 m medida en el marco y aportada por no más de una hoja.` (link `#page=36`) |
| CTE-SUA-corridor-01 | CTE DB-SUA, Anejo A, p. 36 | had no quote (the row was garbled when the PDF was read); confidence 0.33 | (no quote; link to `#page=35`) | `Anchura libre de paso ≥ 1,20 m. En zonas comunes de edificios de uso Residencial Vivienda se admite 1,10 m` (the PDF splits "Vivien-da" across two lines); link to `#page=36` |

The other 9 cards (Decret 141/2012: useful area, façade, heights, bedrooms, living room, windows, patios) were
already found word for word; only the new `"checked"` field was added.

## The rulebook's own text

In this version the flipbook shows the official PDF pages themselves (`Bars's files/4_laws_and_rules/code/get_rulebook.py`); it adds no quotes of
its own, and the scanned PGM pages carry no OCR text (it is added only if `ocr_pgm.py` has been run with Tesseract).
So there was no rulebook quote to correct. (Bhavini's later version, on `parked/bhavini-v43`, added OCR text under
some bookmarks, with the same errors as above: it is not on main.)
