# NOMAD — the whole pipeline, element by element (12 Nov 2026)

For every part of NOMAD: **what it is for, which sources it uses (and their licence), which scripts do the work, what
files they make, and where the result is used** (the app, Rhino, the lab book, the team repo). Private file: `docs/`
is kept off GitHub.

Words used below
- **App** = the local website `site/index.html` (preview `nomad-site`, http://localhost:8766). It runs NOMAD's Python
  in the browser (Pyodide). **Share copy** = `site_share/` (port 8767), made by `src/app/make_share.py`.
- **Engine** = the plan generator and checks; the same Python runs in Rhino and in the app (copies in `site/py/src/*.txt`).
- **Private use only** = Catastro Sede web content (Visor 3D, Consulta_DNPRC service, facade photos): used on this
  computer, never published or shared.

---

## 0. The flow at a glance

```
 SOURCE (file on this computer)          CODE                         OUTPUT                  SHOWS IN
 ════════════════════════════════════════════════════════════════════════════════════════════════════

 1 FIND THE SHOPS
 City census 2024                        src/zoning/zoning.py         results/zoning/
   data/barcelona/census/                  (door → zone, gate)          lookup.json
   2024_CensComercial_BCN.csv                                           empty_premises_zoning.csv
 MUC zoning (Generalitat)                src/zoning/warehouses.py ──► site/data/warehouses.json
   data/barcelona/zoning/                src/zoning/amb.py ─────────► site/data/amb.json
 Catastro INSPIRE, 35 AMB towns          src/zoning/amb_base.py ────► site/data/amb_base.json
   data/amb/                             src/check/avoid.py           (answer per premises)
                                         src/app/build_site.py ─────► site/data/premises.json ─► City in 3D,
                                                                      basemap.json, city/,       map, Find
                                                                      nomad.json                 your shop

 2 READ THE BUILDING
 Catastro INSPIRE Buildings 08900        src/building/              data/barcelona/catastro/
   data/barcelona/catastro/raw/ (zip)      catastro_buildings.py ───► buildings.json.gz
                                         src/building/real_shops.py ► site/data/shells.json ───► Find your shop,
                                         src/building/light_wells.py  (patios, wells_above)      The building
 Catastro CAT file                       src/building/shop_data.py
   data/barcelona/catastro/CAT_files/      step 0 units ────────────► data/barcelona/catastro/
   08900U_14082026.CAT.gz                                               units_cat.jsonl
 Catastro INSPIRE Addresses                step 1 doors ────────────► site/data/doors.json ────► door marks
   data/barcelona/catastro/addresses/      step 2 shapes (A/B) ─────► site/data/cut_shells.json ► shop shape
   A.ES.SDGC.AD.08900.zip                  step 2b cores (C) ───────► site/data/cores.json ────► hall + stair
                                           step 3 facts ────────────► site/data/facts/f_XX.json ► Facts panel
                                           step 4 team ─────────────► team copy (transformed)
 Catastro Visor 3D *                     src/building/existing_core.py ► existing in shells.json
                                         src/zoning/catastro_plans.py
                                         src/zoning/catastro_site.py► site/data/catastro/b_XX.json ► floor
                                         src/building/unit_shells.py► site/data/unit_shells.json     by floor
                                                                      unit_skips.json
 ICGC LiDAR v3.1                         src/building/              results/heights/heights.csv
   data/lidar/ (grid/*.npz)                lidar_heights.py ────────► site/data/heights.json ──► height box
 Catastro facade photo *                 src/facade/facade.py       results/facade/<ref>/
   data/barcelona/catastro/facades/        straighten → read →        inventory.json, openings.json,
 Grounding DINO + OpenCV                   analyse → floors → draw    elevation.png, *.jpg (private)
   (tools/train-venv)                      approve (you) ───────────► results/facade/approved.json
                                                                      results/facade/approved/<ref>/
                                           export ──────────────────► site/data/facades.json ──► The building,
                                         src/rhino/record_facade.py ► rhino/NOMAD.3dm             3D openings
 CartoBCN 1:1000 (product 144)           (not wired in yet)
   data/barcelona/topo1000/cartobcn/gpkg/

 3 ZONING
 MUC zoning + PGM art. 225.7 (OCR)       src/zoning/zoning.py (gate) ► results/zoning/ ──────► verdict pill,
   data/pgm/                                                                                     "WHY"

 4 THE RULES
 BOE texts (CTE, LOE, TRLSRU, LPH…)      src/collect/fetch_national.py
   data/national/                        src/collect/fetch_cte_db.py
 CTE DB-HS / SUA / SI / HR / HE          src/collect/fetch_catalonia.py
   data/national/cte_db/                 src/collect/ocr_pgm.py, fetch_pgm.py
 Decret 141/2012, DOGC                   src/collect/fetch_bcn_guide.py
   data/catalonia/raw/                   src/collect/build_rulebook.py ► data/rulebook.jsonl
 PGM / MPGM normes                       src/rules/build_rules.py ──► rules/rules.json ───────► rule cards,
   data/pgm/                                                          rules/review.json          citations
 Barcelona guide + ordinances            src/eval/run_golden.py ────► checks eval/golden_set.csv
   data/barcelona/                       src/rulebook/compile_rulebook.py
                                         src/rulebook/add_anchors.py► site/rulebook/ ─────────► The laws
                                                                                                 (flipbook)
 5 DAYLIGHT
 Radiance runs (team repo)               src/daylight/              results/daylight/
   exp1_daylight/results.csv               bars_daylight.py ────────► site/data/daylight.json ─► daylight bands
 Weather ESP_CT_Barcelona.081800_TMYx

 6 CHECK THE SHOP
 rules/rules.json                        src/check/flags.py ────────► YES / PARTLY / NO ───────► verdict, cards
 Annex 4 groups (team, by Bars)          src/app/nomad_web.py       Grup B / C / D card ──────► Your homes
   site/data/annex4_grup.json              (_annex4)

 7 FIT THE HOMES
 Swiss Dwellings v3.0.0                  src/generate/clean_dataset.py
   data/datasets/                        src/generate/learn_room_programs.py ► site/data/room_programs.json
 ResPlan                                 src/learn/habitability.py
 Your own DXF / JSON plans               src/library/build_library.py, build_resplan.py,
                                           placed_plans.py, own_plans.py
                                         src/library/street_library.py ► src/generate/library_street.json
                                         src/library/fit_table.py ──► fit_table.json
                                         src/ai/ (U-Net) ───────────► results/library/library_ai.json
                                         src/generate/plan3.py
                                           + library_fit.py ────────► 5 layouts ──────────────► Your homes
                                         src/model3d/prisms.py ─────► 3D prisms ──────────────► 3D view
                                         src/model3d/export_ifc.py ─► results/model3d/*.ifc, *.glb ► IFC
                                         src/rhino/nomad_core.py,
                                           nomad_model.py ──────────► rhino/NOMAD.3dm
                                         src/app/nomad_web.py ──────► site/py/src/*.txt (Pyodide)

 8 REPORT
 idealista18 prices 2018                 src/app/value.py ──────────► results/value/ ─────────► €/m² hint
 all of the above                        site/index.html (save, compare, PDF) ─────────────────► Saved, PDF
                                         src/check/city_runs.py ────► results/city/homes.csv
                                                                      site/data/city_homes.json ► For the city
                                         src/app/refresh_outcomes.py► results/dashboard/ ──────► results page

 ACROSS ALL
 book/experiments.json                   src/book/build_book.py ────► book/site/index.html (lab book)
 site/                                   src/app/make_share.py ─────► site_share/ (safe copy)
 ════════════════════════════════════════════════════════════════════════════════════════════════════
 * private use only (Catastro Sede): never on GitHub, the site or the team
```

Supporting the whole: the **lab book** (`book/`), **Rhino** (`rhino/NOMAD.3dm`, one file), the **approval checkpoint**
for facades, the **share copy**, and the **team repo** (only what Bars needs).

---

## 1. FIND THE SHOPS (empty premises and unused buildings)

**Purpose.** Know every empty ground-floor premises in Barcelona, where its door is, and whether its zone could take homes.

| Source | Licence | Stored | Used for |
|---|---|---|---|
| Cens de locals en planta baixa 2024 (Ajuntament de Barcelona, Open Data BCN) | CC BY 4.0, credit "Ajuntament de Barcelona" | `data/barcelona/census/2024_CensComercial_BCN.csv` | every premises: door point, address, empty or active, offer (rent / sale), activity, flags (street, market, gallery, centre, shopping street, night, 24 h), cadastral reference |
| Mapa Urbanístic de Catalunya, "Qualificació" (Generalitat, via gissrv.diba.cat ArcGIS) | Generalitat open data, attribution | `data/barcelona/zoning/` | the PGM zone of each premises |
| Catastro INSPIRE Buildings (AMB towns) | INSPIRE licence, transformed, cite DGC | `data/amb/` | unused buildings in the 35 other AMB towns |
| idealista18 asking prices 2018 | ODbL (credit, share-alike for databases) | `results/value/` (via `src/app/value.py`) | €/m² nearby, shown as a hint |

**Scripts (in order).**
1. `src/zoning/zoning.py` — joins each census door to its MUC zone (a door in a street polygon takes the building's zone
   within 8 m) and applies the zoning gate (step 3) → `results/zoning/lookup.json`, `empty_premises_zoning.csv`.
2. `src/zoning/warehouses.py` — Catastro industrial / retail / office buildings with no homes → `results/warehouses/`,
   `site/data/warehouses.json` (census hint "empty premises / no active business / active business": a hint, not proof).
3. `src/zoning/amb.py`, `src/zoning/amb_base.py` — the metropolitan area → `site/data/amb.json`, `amb_base.json`.
4. `src/check/avoid.py` — NOMAD's answer per premises (not allowed / not liveable / keep it a shop / candidate / not
   modelled; "keep it a shop" = lowest 10 % of retail within 100 m, a design choice).
5. `src/app/build_site.py` — writes `site/data/premises.json` (6,149 empty premises), `basemap.json`, the 3D city tiles
   `site/data/city/` and `nomad.json`.

**Where used.** City in 3D (every building raised from its floor count: 5 m + 3 m a floor, an estimate), the 2D map, Find
your shop (search, verdict pill), For the city.

---

## 2. READ THE BUILDING

**Purpose.** For each premises: its true shape, its street facade, light wells, the building's hall and stair, doors,
heights, and the facts about the building — every piece marked real or assumed.

### 2a. Footprint and street facade
| Source | Licence | Stored |
|---|---|---|
| Catastro INSPIRE Buildings, Barcelona 08900 (footprints, building parts, floors above / below) | INSPIRE licence: transformed data, cite "Dirección General del Catastro" | `data/barcelona/catastro/raw/` (zip read in place), `buildings.json.gz` |

Scripts: `src/building/catastro_buildings.py` (reads the zip) → `src/building/real_shops.py` (each premises' building:
ground floor outline, street facade = edges facing a street polygon, simplified 0,15 m, local metres) →
`results/real_shops/shells.json` (5,322 buildings), `site/data/shells.json`. Where used: the shop shape when nothing
better is known ("Shape: the building's whole ground floor").

### 2b. Units of each building (sizes, uses, floors, year)
| Source | Licence | Stored |
|---|---|---|
| **Catastro CAT file**, Barcelona urban `08900U_14082026.CAT.gz` (accessed 11 Nov 2026) | Download licence: transformed data may be published (cl. 6), never the original online (cl. 5, 8); cite DGC + access date (cl. 12) | `data/barcelona/catastro/CAT_files/` (never committed) |
| ~~Consulta_DNPRC web service~~ (old unit list `units.jsonl`, `src/building/catastro_units.py`) | Sede legal notice: **private use only** | replaced by the CAT file on 11 Nov |

Script: `src/building/shop_data.py` **step 0** reads records 15 (each unit: floor, door, use letter, built m² with its share
of common parts) and 14 (each construction: year) → `data/barcelona/catastro/units_cat.jsonl` (5,331 buildings, 188,178
units). Where used: rule A/B cuts (2c), the facts panel (2g).

### 2c. The premises' true shape — rules A and B (assumed)
`src/building/shop_data.py` **step 2** → `site/data/cut_shells.json` (2,931 premises).
- **Rule A** (one shop unit on the ground floor): the part behind its door on its street facade, as deep as the unit's m²;
  narrower and centred on the door when the front is long. 501 premises.
- **Rule B** (2+ shop units): the street front shared between the census doors (halfway to the next door); area within the
  smallest–largest unit; shallower than 4 m → narrowed round the door. 2,470 premises.
- Rejected (footprint kept): cuts under 2,5 m wide, doors > 8 m from the building, cuts that lose the street facade.
- App order: the premises' own Catastro unit plan (private, 2f) > cut shape ("assumed rule A/B") > footprint.

### 2d. Light wells (patis de llums)
`src/building/light_wells.py` — holes in the INSPIRE ground floor = light wells open to the sky (2,856 shops, 4,817 wells);
holes above a roofed ground floor kept as information (610 shops) → `patios`, `wells_above` in `shells.json`. Where used:
the engine never puts a flat over a well (`plan3._PATIOS`); drawn hatched blue in the plans.

### 2e. The building's hall and stair — real or rule C (assumed)
- **Real** (private use only): Catastro Visor 3D ground-floor "Local COMUN" polygons, `src/building/existing_core.py`
  → `existing` in `shells.json` (531 buildings).
- **Rule C** (shareable): `src/building/shop_data.py` **step 2b** → `site/data/cores.json` (2,942 buildings). From the land
  registry entrance point: a 3,5 m hall to the **stair tower** (the building's smallest INSPIRE part as tall as the tallest;
  right place in 93 % of 171 tested buildings), else to the nearest **light well** with the stair beside it (91 % of 88),
  else a 3,5 × 7,6 m **box** (72 % of 294). 3,5 × 7,6 m = median of 1,692 real halls. Labelled with method + accuracy.
- Where used: the engine keeps homes off it and may use it as the flats' way in (`existing`, `coreAssumed`).

### 2f. Floor plans of the whole building (private use only)
`src/zoning/catastro_plans.py` (Visor 3D per-floor unit polygons, ~600 parcels) → `src/zoning/catastro_site.py` →
`site/data/catastro/b_XX.json`; `src/building/unit_shells.py` → `site/data/unit_shells.json` (640 premises' own unit) and
`unit_skips.json`. Where used: "The building" floor by floor, 2D and 3D. **Never shared**: the share copy replaces them
with INSPIRE outlines.

### 2g. Doors, entrances and facts
| Source | Licence | Stored |
|---|---|---|
| Catastro INSPIRE Addresses, Barcelona `A.ES.SDGC.AD.08900.zip` (3,7 MB; points marked "Entrance") | INSPIRE licence, cite DGC | `data/barcelona/catastro/addresses/` |
| City census 2024 (2-1) | CC BY 4.0 | |

`src/building/shop_data.py` **step 1** → `data/barcelona/catastro/entrances.json`, `site/data/doors.json` (3,479 buildings
with an entrance, 13,833 premises doors). **Step 3** → `site/data/facts/f_XX.json` (census rows per building, CAT units,
year, floors). Where used: Find your shop › Show the details (status, offer, where, other premises, doors, building),
dots and squares on the shop plan in Your homes.

### 2h. Heights (LiDAR)
| Source | Licence | Stored |
|---|---|---|
| ICGC Territorial LiDAR v3.1 (2021-2023) | CC BY 4.0 | `data/lidar/` (grids `data/lidar/grid/*.npz`) |

`src/building/lidar_heights.py` → `results/heights/heights.csv`, `site/data/heights.json` (street level, roof p25/p50/p75,
floor height estimate). Where used: the height box in Your homes ("Estimated from ICGC LiDAR"), unless an approved facade
gives the ground floor's own height.

### 2i. The facade (read from a photo) — with the approval checkpoint
| Source | Licence | Stored |
|---|---|---|
| Catastro facade photo service (one 1024 × 768 photo per parcel) | Sede: **private use only**; photos and pictures from them never on GitHub, the site or the team | `data/barcelona/catastro/facades/` |
| ICGC LiDAR (2h) | CC BY 4.0 | |
| Grounding DINO base (IDEA-Research) | Apache-2.0 | Hugging Face cache, run in `tools/train-venv` |
| OpenCV | Apache-2.0 | |

One file, `src/facade/facade.py` (method: `docs/facade_workflow.md`):
1. **straighten** — lens bend (division model), vertical + horizontal vanishing points, turned to face the facade.
2. **heights** — LiDAR street level (pavement strip 1-4 m out) and cornice (strip 0,5-2,5 m in).
3. **read** — edges that make the Catastro width fit the LiDAR scale; Grounding DINO on the whole facade, tiles, ground floor,
   bay by bay; trees = hidden; street level only from low doors; whole facade searched again if the crop was too narrow.
4. **analyse** (3b) — level the leftover tilt; cut the floors into bands, line them up, compare (≥ 0,55 = same type); blend
   each type into one clean typical floor; vote across floors; read it as an architect (a balcony has a door, a pier makes
   two windows, a railing is not a window) → `inventory.json`, `analysis_PRIVATE.jpg`.
5. **floor heights** — ground floor g + every upper floor one height s, both in 5 cm steps, fitted to the photo's floors; top
   floor ≤ LiDAR top + 0,5 m (city model 5 + 3 × floors is a check only).
6. **draw** — every floor from its type (or the older tidy + symmetry test) → `openings.json`, `elevation.png`.
7. **approve** (user) — `facade.py <ref> approve` freezes a copy in `results/facade/approved/<ref>/`;
8. **export** — only approved copies → `site/data/facades.json` (with the facade line's ends).
Approved: Av. Diagonal 413 (5,75 + 6 × 3,80 m), Pl. Sortidor 4 (4,30 + 5 × 3,15 m).
Where used: The building (facade drawing, floors at measured heights, openings on the 3D), the height box; Rhino 2D
(`src/rhino/record_facade.py`, when Rhino is closed). Not yet: the shop's street-wall openings in the plans (item 8).

### 2j. The 1:1000 city map (downloaded, not wired in yet)
CartoBCN `TOPO1000_GPKG.zip` (product 144, Dec 2025), CC BY 4.0 → `data/barcelona/topo1000/cartobcn/gpkg/`: building
polygons, street / inner-block facade lines, party walls, floor counts (roman numerals), patio labels Pi / Pe / T. Checked:
no stairs drawn inside buildings. Planned: facade and party-wall lines for windows; patio labels for light.

### 2k. Plan source label (checklist item 3)
`site/index.html` `basisRows / basisHtml / basisText`: every picked shop carries its basis — plan source (real plan /
Catastro unit / building footprint / assumed shape) and, per part, real or assumed (shape, hall and stair, light wells,
windows, height). Shown above the layouts, in Saved and Compare, and in the PDF report.

---

## 3. ZONING — may this ground floor take homes?

| Source | Licence |
|---|---|
| MUC zoning (step 1) | Generalitat open data |
| PGM 1976 / MPGM 1999 art. 225.7 (RPUC scans, OCR) | public planning register |

`src/zoning/zoning.py` gate: **YES** zones 12, 13a, 13b, 14b, 15 (built along street lines); **CHECK** 18, 20, 22@,
14 remodelling (a detailed plan decides); **NO** industry and urban systems. Barcelona: 5,026 of 6,149 (82 %) YES.
AMB towns fall back to MUC codes (A1/A2/N = NO, R = CHECK). Where used: the verdict pill and "WHY" in Find your shop;
NO forces NO and CHECK caps the layouts at PARTLY (`nomad_core.add_zoning`, "Zoning" card first).

---

## 4. THE RULES — from official texts to checkable rule cards

| Source | Licence | Stored |
|---|---|---|
| BOE consolidated texts (CTE Part I, LOE, TRLSRU, Ley 12/2023, LPH) via the BOE open-data API | legislative texts, no copyright (LPI art. 13), cite BOE | `data/national/` |
| CTE Documentos Básicos (DB-HS, SUA, SI, HR, HE), codigotecnico.org | official, cite | `data/national/cte_db/` |
| Decret 141/2012 and other Catalan texts (Portal Jurídic / DOGC, saved by hand: robots disallow bots) | public legal texts | `data/catalonia/raw/` |
| PGM / MPGM normes (RPUC, scanned → Tesseract OCR cat+spa) | public register | `data/pgm/` |
| Barcelona guide "canvi d'ús de locals a habitatge" (2025-03), ordinances | Ajuntament | `data/barcelona/` |

Scripts: `src/collect/fetch_national.py`, `fetch_cte_db.py`, `fetch_catalonia.py`, `ocr_pgm.py` → `fetch_pgm.py`,
`fetch_bcn_guide.py` → `src/collect/build_rulebook.py` → `data/rulebook.jsonl` (one chunk per article, current wording,
tables as rows). `src/rules/build_rules.py` → `rules/rules.json`: **16 rule cards**, each with value, article, page and the
exact sentence (checked word for word); `rules/review.json`. `src/eval/run_golden.py` on `eval/golden_set.csv`
(16 questions, answers checked in the source). `src/rulebook/compile_rulebook.py` + `add_anchors.py` → the law book
(23 official PDFs, 1,408 pages, index, bookmarks, highlighted lines) in `site/rulebook/`.
Not built: the RAG knowledge base (`src/kb/` is empty); rule cards were made from the rulebook directly.
Where used: every check card cites its rule and opens the law in The laws (flipbook). Private: the law book (`site/rulebook`
is gitignored and left out of the share copy).

Key numbers in use (each from its card): clear height 2,40 m for a conversion (Decret 141/2012 Annex 4 Grup C, Annex 1
3.5); 40 m² useful and 3 m facade (MPGM 2004, Barcelona); doors 0,80 / 0,70 m, 1,20 m circles (Annex 1 3.4); living
2,80 m, kitchen 1,60 m; facade ≥ S/9 (3.6.2); patio 3 m circle and 9 m² (2.5.1); corridor 1,20 m, lobby 1,50 m
(CTE DB-SUA Anejo A); 25 m to a street door (CTE DB-SI SI 3); density art. 318 / 323.

---

## 5. DAYLIGHT (the daylight model, team)

| Source | Licence |
|---|---|
| Bars Babila's Radiance / Ladybug runs, `exp1_daylight/results.csv` (team repo) and his XGBoost model | team project, author's agreement; XGBoost Apache-2.0 |
| EN 17037 targets, Barcelona weather file ESP_CT_Barcelona.081800_TMYx | standard / public |

`src/daylight/bars_daylight.py` (his model on NOMAD's shells) → `results/daylight/`, `site/data/daylight.json` (lit depth
per shop, class livable / needs a change / not livable). Where used: the daylight line in Your shop; the engine's
liveability rule (living rooms and bedrooms need half their floor within the lit depth; 5,5 m assumed where no
prediction). Daylight is liveability, not a legal fail. Owned by Bars: NOMAD does not refine it.

---

## 6. CHECK THE SHOP

- `src/check/flags.py` — rule cards on the shop and its flats → YES / PARTLY / NO with margin and citation; the "flats
  inside the shop" geometry test; daylight bands.
- **Conversion group** — team data `annex4_grup.json` (`tools/annex4_grup.py` in the team repo, by Bars, from the CAT file: the shop's built
  area ÷ the building's) → Grup C (≤ 50 %: building rules exempt except 2.2.1), Grup D (> 50 %: 2.1, 2.2.2, 2.6, patios
  −10 %), Grup B (whole building). Copied to `site/data/annex4_grup.json`; `src/app/nomad_web.py` `_annex4` puts a
  "Conversion group" card first and checks the community room for Grup D with 8+ homes (fail → YES becomes PARTLY).
- Where used: Your homes › Checks; Find your shop › RULES.

---

## 7. FIT THE HOMES — 2D layouts, furniture, 3D

### 7a. The plan library (real flats)
| Source | Licence | Stored |
|---|---|---|
| Swiss Dwellings v3.0.0 (Archilyse, Zenodo 7788422) | CC BY 4.0 | `data/datasets/` |
| ResPlan (m-agour) | CC BY 4.0 | |
| CubiCasa5K (test only, Exp 1) | CC BY-NC-SA 4.0 — never in the product | `data/datasets/test_plans_cubicasa` |

Scripts: `src/generate/clean_dataset.py`, `learn_room_programs.py` (room sizes from 13,444 rule-passing flats →
`site/data/room_programs.json`), `src/learn/habitability.py` (`docs/habitability_rules.md`),
`src/library/build_library.py`, `build_resplan.py`, `placed_plans.py` (room placer, NOMAD placed), `own_plans.py` (your
DXF / JSON plans), `street_library.py` → `src/generate/library_street.json` (the flats NOMAD can use), `fit_table.py` →
`fit_table.json`. **Plan AI** `src/ai/` (U-Net trained on the library, RTX 3060, `tools/train-venv`) →
`results/library/library_ai.json`, merged as "NOMAD AI".

### 7b. The generator
`src/generate/plan3.py` (the engine) with `library_fit.py` (stretch solver, plan-graph and door / turning checks,
circulation filter), `furnish.py` (legal furniture: wardrobe, bed square, worktop, WC / basin / shower, washing machine,
1,20 m circle), `shared.py` (shared-space homes, Llei 18/2007), `building.py` (whole buildings, Annex 4 Grup B: cores,
stairs, lifts, mezzanines, patios, exits), `layout.py`, `plan2.py`, `better.py` (older strategies kept as parts).
Rules inside: street lobby, shared hall, flats along every facade within 25 m, street-cut flats ≤ 9 m, side-entered flats,
real halls / rule C halls and light wells never built over, evaluation matrix (`_score`).
Runs in: Rhino (`src/rhino/nomad_core.py`), the app (Pyodide, `site/py/worker.js` + `site/py/src/*.txt`, via
`src/app/nomad_web.py`).

### 7c. 3D and exports
`src/model3d/prisms.py` (walls, windows 60 % × 1,5 m on street walls, doors, furniture as prisms) → the app's 3D;
`src/model3d/export_ifc.py` (IfcOpenShell, LGPL; trimesh, MIT) → `results/model3d/*.ifc`, `*.glb`;
`src/rhino/nomad_model.py` → Rhino walls models. three.js r147 (MIT) in the app.

Where used: Your homes (5 layouts, cards, daylight bands, real-plan gallery, furniture, 3D walls / zoning), Rhino
(`rhino/NOMAD.3dm` layers "06 NOMAD experiments", "07 NOMAD lab book").

---

## 8. REPORT, SAVED, THE CITY

- **Saved / Compare** — `site/index.html` (`saveShop`, `drawSaved`, `drawCompare`), stored per user in the artifact
  database when published, else in the browser; carries the plan source label.
- **PDF report** — jsPDF 2.5 (MIT) in the page: plans, rule cards, 3D, plan source.
- **For the city** — `src/check/city_runs.py` → `results/city/homes.csv`, `site/data/city_homes.json` (12,755 homes on
  flat heights; the user chose not to rerun with LiDAR heights).
- **Results page** (`results/dashboard/`, `src/app/refresh_outcomes.py`) and **deck / videos** (`src/app/add_deck_slides.py`,
  `video/`).

---

## 9. ACROSS ALL STEPS

### Privacy and sharing
| What | Who sees it |
|---|---|
| App `site/`, code `src/`, lab book `book/`, law book, `docs/`, `CLAUDE.md` | you only (your private repo `bhavinimanot-arch/nomad`; most paths in `.gitignore`) |
| Catastro facade photos and pictures from them | this computer only (`.gitignore`: `results/facade/**/*.jpg`) |
| Visor 3D plans, Consulta_DNPRC units | this computer / your app only |
| **Share copy** `site_share/` (`src/app/make_share.py`) | safe to share: Visor data → INSPIRE outlines, unit sizes → counts, no facades, rounded shapes |
| Team repo `iaac-maai/nomad` | only what Bars needs: PR #13 (merged) = `tools/shop_data.py` + `nomad/06_Results/shops_doors_facts/` in the team repo (transformed) |

### Checkpoints
- **Facades**: nothing reaches the app before you approve the drawing (frozen copies).
- **Publishing**: nothing is published or pushed without your word.
- **Rhino**: one file `rhino/NOMAD.3dm`; never written while Rhino has it open; backup first.

### Records
- Lab book `book/experiments.json` → `src/book/build_book.py` → `book/site/index.html` (E01-E48).
- Checklist `docs/floorplan_checklist.md`; facade method `docs/facade_workflow.md`; licences `docs/licences.md`.

### Environments
- `.venv` — data, engine, drawing (shapely, pandas, matplotlib, pymupdf).
- `tools/train-venv` — GPU work: Grounding DINO, OpenCV, PyTorch (plan AI, facades).
- Pyodide in the browser — the engine in the app. Rhino 7.1 IronPython — Grasshopper / Rhino scripts.

---

## 10. RUN IT AGAIN, IN ORDER

```
# 1 shops + zoning
.venv/Scripts/python src/zoning/zoning.py
.venv/Scripts/python src/zoning/warehouses.py
# 2 building
.venv/Scripts/python src/building/catastro_buildings.py
.venv/Scripts/python src/building/real_shops.py
.venv/Scripts/python src/building/light_wells.py
.venv/Scripts/python src/building/lidar_heights.py
.venv/Scripts/python src/building/shop_data.py            # units (CAT) → doors → shapes A/B → halls C → facts
# 2i facades (per building; you check, then approve)
tools/train-venv/Scripts/python.exe src/facade/facade.py <ref>          # straighten, read, analyse
.venv/Scripts/python src/facade/facade.py <ref> draw
.venv/Scripts/python src/facade/facade.py <ref> approve
# 4 rules
.venv/Scripts/python src/collect/build_rulebook.py
.venv/Scripts/python src/rules/build_rules.py
.venv/Scripts/python src/eval/run_golden.py
# 5 daylight
.venv/Scripts/python src/daylight/bars_daylight.py
# 7 library (after changes to plans or checks)
.venv/Scripts/python src/library/street_library.py
.venv/Scripts/python src/library/fit_table.py 7
# 8 site + share copy + lab book
.venv/Scripts/python src/app/build_site.py
.venv/Scripts/python src/app/make_share.py
.venv/Scripts/python src/book/build_book.py
```

---

## 11. STATUS AND OPEN ITEMS (12 Nov 2026)

Done: items 1-6 and 3 of the floor-plan checklist; facades for 2 buildings, approved; approval checkpoint; share copy.
Open:
- Item 8: real street-wall openings from an approved facade into the plans (today: 60 % glass assumed).
- Items 7, 9: ground floor split by the facade's arches; mezzanine check (MPGM 1999 art. 225).
- Items 10-13: privacy from the pavement, the deep back part, noise, lofts.
- 1:1000 map: facade / party-wall lines and patio labels into the plans.
- Floor heights that change upwards (the rule keeps one upper height).
- Hall size per building (rule C uses one typical size); real plans from the Arxiu / COAC (item 15).
- RAG knowledge base not built; city counts on the older engine.
