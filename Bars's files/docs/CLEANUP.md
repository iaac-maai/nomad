# Cleanup after the midterm (9–10 Nov 2026)

Branch `cleanup-after-midterm`, one small commit per item. Base: Bars's site of 4 Nov (`b082ba6`), the version that was
published. Nothing is lost: everything removed from `main` is on a branch (see the end).

## 0. The base

- Bhavini's three commits of 5 Nov (`13f4ace`, `594c46b`, `d1e8044`: site v34–v43, plan AI, space optimisation) were
  undone with `git revert` (no history rewritten, no force-push). They are kept untouched on `parked/bhavini-v43`.
- After the reverts the tree is identical to `b082ba6`, and `index.html` matches the published page byte for byte
  (apart from the wrapper the publisher adds).
- `docs/AI_LOG.md`: Bhavini's three rows are marked "reverted on 9 Nov, not in main".

## 1. Removed

| What | Why | How |
| --- | --- | --- |
| **Exp 4: the XGBoost daylight model**, the per-shop daylight classes and the "dark → not liveable" rule | A prediction is not a simulation; per-shop daylight will come from a grid simulation | Removed `train_daylight.py`, `predict_shops.py`, `map_shops.py`, `shops_bcn_pred.csv`, `daylight_site.py`, `bars_daylight.py`, `data/daylight.json` and their outputs, and the xgboost dependency. The site now says "daylight: per-shop grid simulation, coming". The 5 shops simulated in Radiance stay as **validated examples** (`Bars's files/5_daylight/code/daylight_validated.py`, read straight from the sensor grid, no model); the experiments page keeps "tried, dropped, replaced by grid simulation". |
| **Layouts and home counts from footprints** ("Your homes", Results, For the city) | A count of homes is a design result, not a zoning answer; the counts were never checked by an architect | "Your homes" parked (below). The Results section removed (it also held the metropolitan-area map, which went with it). Every place now has a **category**: candidate (zone YES, no avoid flag) / risky (zone CHECK, or "keep it a shop": the 10 % of shops with the fewest shops within 100 m) / zoning doesn't allow (NO), on the shop answer, the map and the 3D city. **For the city** counts the three categories per district and lists the places; no charts. **Saved** and the **PDF report** keep only the zoning answer and its sources. `build_site.py` no longer writes home counts. |
| **Catastro Visor 3D units** | Not open data ("download and private use"; Catastro legal notice: reproduction, distribution, public communication and transformation "totalmente prohibida salvo que medie autorización expresa") | The building of a shop is drawn from the Catastro building parts only; the 600 buildings that only had Visor units point to City in 3D. `catastro_plans.py` (the Visor scraper) removed; `catastro_site.py` no longer reads it. |
| **idealista18 prices** | A 2018 asking price is not a value; the feature was not asked for | Price box, comparison row and source row removed; `value.py` and `premises_value.csv` removed; `build_site.py` no longer writes prices. |

## 2. Parked (on `parked/before-cleanup`, see Bars's files/docs/PARKED.md)

The weight sliders, the "Your homes" layout engine (with its Pyodide worker, demo shops and data), the plan upload
(`readPlanImage`, DXF/JSON plans) and "Ask NOMAD". Bars's files/docs/PARKED.md lists each one's files and what must be true before it
comes back. The layout engine's data, which had lived only in the published artifact, was committed to that branch so it
cannot be lost. The shared-housing text (Llei 18/2007 art. 18 bis) is parked with "Your homes": Catalonia gives 24 m²
private + at least 6 m² common, at least 36 m² in total (Decret llei 50/2020, transitional provision 10); no official
source was found for the 40 m² the old text used.

## 3. Kept

The rulebook flipbook, the 16 rule cards and their source sentences, the precedents table, and the 3D city, now titled
"estimated heights, for context only" (heights come from the Catastro floor count: 5 m + 3 m per floor).

## 4. Fixed

- **a) Data.** The site's data lived only in the published artifact (321 files, 60 MB). The 235 files the cleaned site
  uses (27 MB) are now in git (`tools/import_site_data.py`); every one of the 321 is listed in `docs/DATA_INVENTORY.md`
  with its type, size, origin, use and fate. No file is over 5 MB, so Git LFS was not needed. Pyodide is not in the
  repo (only the parked engine used it; it will come from a pinned CDN). The 23 law PDFs are downloaded from their
  official URLs (BOE, codigotecnico.org, Portal Jurídic ELI, Agència de l'Habitatge, RPUC, AMB, Ajuntament) by
  `Bars's files/4_laws_and_rules/code/get_rulebook.py`, which builds the book's pages. **One command opens the site: `python serve.py`.**
- **b) Law texts.** The 16 rule cards' sentences were compared with the official PDFs: 12 are found word for word in
  the text PDFs; 4 come from the MPGM 2004 scan (no text layer) and were read by eye on the page images. 7 were
  corrected (4 OCR errors, 2 table-markup or cut-off quotes, 1 missing quote); none had to be removed; no value
  changed. Every change is listed in `docs/LAW_TEXT_CHECK.md`; `Bars's files/4_laws_and_rules/code/check_quotes.py` repeats the check.
- **c) 18 bis** — see section 2 and Bars's files/docs/PARKED.md.
- **d) AI log.** Bhavini's rows marked. The model the code calls is `gemini-3.5-flash-lite` (GEMINI_MODEL in `.env`;
  150 of the 155 logged drafts), so "Gemini 3.5 Flash Lite" was right; the exact id is now in the log and Sources.
- **Golden-set score removed (10 Nov, option B).** The score (16 questions, "100 % answered right by NOMAD's code")
  was computed by `run_golden.py` on the layout engine's code, which is parked, so main cannot reproduce it. The score
  boxes and the Exp 3 "after the fixes" chart were removed; the Rule cards page keeps "16 / 16 cards checked against
  the official text". The score comes back with the engine (Bars's files/docs/PARKED.md).
- **e) Sources.** Tesseract: "OCR of PGM/RPUC legal texts for the rulebook". CubiCasa5K: not for commercial use.
  The weather file (TMYx, climate.onebuilding.org): checked, no licence stated, cited as the site asks, not
  redistributed. The metropolitan "to check" row went with the Results section. No row is left "to check".

## 5. Files

Every file was sorted into used by the site / experiment / dead (approved on 10 Nov):
- **Dead (removed):** `.vscode/settings.json` (personal settings, already in .gitignore; `git rm --cached`).
- **Experiments (moved to `archive/experiments`, 395 files):** Exp 2/3 rule-card drafting, Bhavini's lab book E01–E32,
  Rhino/Grasshopper, the layout engine and plan-reading code, results and research documents. `experiments/README.md`
  keeps one line for each. `Bars's files/5_daylight/` stays on main: the grid simulation builds on it.
- **Main now:** 312 files, 33 MB. README.md has a map of every folder and file.

## 6. How it was tested

- **Revert:** `git diff b082ba6 HEAD` was empty after the three reverts; `index.html` compared with the published page.
- **The site, in Chrome** (Playwright driving the installed Chrome, headless, 30 checks on every section): start page,
  nav, shop search and answer (category, daylight note, validated example), the building in 2D/3D, save two shops,
  compare them, download the PDF report, the three map modes, For the city (table, list, switch, open a place),
  City in 3D (title, loaded, category key), the laws (pages drawn, a bookmark opens its page), workflow, 16 rule
  cards, Exp 4 and Exp 5 notes, precedents, sources (no "to check", no removed sources), Catalan, simple view, phone
  width. **Result: 29 of 30 pass**; the console shows only the missing favicon. The one failure is below.
- **A fresh clone** of the branch: `check_setup.py` all good, `serve.py` serves the site and its data; without the
  law PDFs the site works and the book says how to get them (28 of 30: the book's pages and the same phone failure).
- **The rulebook:** all 23 PDFs downloaded from their official URLs; the book compiled (1,409 pages); every bookmark
  of a text page checked to be on the page that holds its phrase.
- **Law texts:** `Bars's files/4_laws_and_rules/code/check_quotes.py`: 16 of 16 cards checked.

## 7. Open, for later

- **Phone width:** the rulebook's "previous page" arrow sticks out by 2 px at 390 px wide (it did before the cleanup too).
- **Licence audit (10 Nov 2026):** `docs/LICENCES.md`. Two digital signatures in the book of laws (Circular 10/2025,
  book p. 671; Circular 8, book p. 677, whose signature showed the signer's DNI) are blacked out by the book build, which
  now stops if an ID number appears; the published book had not shown them (the signature fields were not copied),
  but the full book did. Open: the Catastro building files, TMYx, the Ajuntament guide ("check" in LICENCES.md).
- **The building floor by floor (10 Nov 2026):** the Visor 3D units stay out: the Catastro's legal notice allows only
  download and private use of its web content, so showing unit outlines and m² on a public site would need its written
  permission. Instead every shop in Find your shop has "Open this building in the Catastro 3D viewer", a link to the
  Catastro's own viewer for the parcel (new tab); no data is copied. Until the CAT file arrives, the Annex 4 line is
  NOMAD's estimate from the building parts (at least one floor above the ground floor: likely Grup C).
- **Trees in the 3D city** (222,918, Open Data BCN, added 10 Nov 2026): on the Intel UHD GPU a frame takes about 35–39 ms
  with them instead of 15 ms (about 28 fps instead of 60), so the layer is off by default; the checkbox stays. A lighter
  tree (fewer triangles, no shadows) could let it be on.
- **Llei 18/2007** has a newer consolidated version (10 Nov 2026, 136 pages instead of 135): only arts. 22.4 and
  123.1 e) changed (terminology, Llei 15/2026), no rule card cites the law, art. 18 bis is unchanged. The book grew by
  one page and the later bookmarks moved by one. Since PR #3 every law version is pinned
  (`rulebook/sources.lock.json`) and `get_rulebook.py --check` lists the articles that change.
- **Rebuilding the data** needs the raw data (`02_Code/data`, not in git, on the machine that built it). `avoid.py` still
  computes daylight and layout answers that the site no longer reads; only its street-life count is used.
- **The scanned PGM pages** have no OCR text in the book unless `ocr_pgm.py` (Tesseract) is run first.
- **Bhavini's newer site** (her published artifact, after v43) holds work that is in no branch; ask her to push it.
- ~~**Rename** `Bhavini_NOMAD Files/` to `nomad/`~~ — done on 10 Nov 2026 in PR #2 (every path updated, all tests and the clean-clone test run again).
- **Legal questions** (Annex 4 Grup C/D, "sobre o sota rasant", whether MPGM 2004 area-01 and facade-01 are still in
  force after the OME) are now in `Bars's files/docs/OPEN_QUESTIONS.md`. The missing "≤" of Grup C was checked on 10 Nov 2026:
  it is in the original DOGC 6245, page 53451.
- **Source of the Exp 3 chart** (keyword search 4/10, vector search 8/10): `outputs/run_pdf/exp2_summary.md` (keyword)
  and `outputs/run_notebook/exp2_summary.md` (vector), on the branch `archive/experiments`; also in `AGENTS.md`
  before the cleanup ("keyword 23/50 drafts correct, vector 38/50"). The 4 and 8 count the questions whose majority
  card (check and value) matches the gold card. The site says "fully correct": by the stricter measure (all 5 runs
  right) the result is 4 → 7, so the wording should name the measure.
