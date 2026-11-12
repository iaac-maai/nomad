# NOMAD — the whole pipeline, element by element (12 Nov 2026)

For every part of NOMAD: **what it is for, which sources it uses (and their licence), which scripts do the work, what
files they make, and where the result is used** (the app, Rhino, the lab book, the team repo). Private file: `docs/`
is kept off GitHub.

Words used below
- **App** = the local website `app/index.html` (preview `nomad-site`, http://localhost:8766/app/index.html). It runs NOMAD's Python
  in the browser (Pyodide). **Share copy** = `old/site_share/` (port 8767), made by `app/code/make_share.py`.
- **Engine** = the plan generator and checks; the same Python runs in Rhino and in the app (copies in `app/py/src/*.txt`).
- **Private use only** = Catastro Sede web content (Visor 3D, Consulta_DNPRC service, facade photos): used on this
  computer, never published or shared.

---

## 0. The flow at a glance (folder by folder)

```
 FOLDER               INPUT (what goes in)              CODE (what does the work)     OUTPUT → SHOWS IN THE APP
 ══════════════════════════════════════════════════════════════════════════════════════════════════════

 0_shared_input       catastro/  (INSPIRE buildings, CAT file, addresses)        used by steps 1, 2, 3, 6
                      census/    (city census 2024)                              used by steps 1, 2
                      zoning/    (MUC zoning map)                                used by steps 1, 6
                      lidar/     (ICGC LiDAR grids)                              used by steps 2, 3
        │
        ▼
 1_find_the_shops     input/amb/                        zoning.py, warehouses.py,     output/zoning, warehouses,
                      + 0_shared_input                  amb.py, amb_base.py,          avoid  → app/data/premises.json
                                                        avoid.py                      → map, Find your shop
        │
        ▼
 2_building           input/topo1000/ (1:1000 map)      catastro_buildings.py,        output/real_shops, heights,
                      + 0_shared_input                  real_shops.py, light_wells,   plan_reading → app/data/shells,
                      + private/ (Visor 3D)*            lidar_heights.py, shop_data   doors, cut_shells, cores, facts
                                                        (units, doors, shapes, halls) → The building, step 1 card
        │
        ▼
 3_facade             private/catastro_facade_photos*   facade.py                     output/<ref>/ → you APPROVE →
                      + 0_shared_input/lidar            (straighten, read, analyse,   output/approved.json
                                                        draw, approve, export)        → app/data/facades.json → 3D
        │
        ▼
 4_laws_and_rules     input/national, catalonia, pgm,   fetch_*.py, ocr_pgm.py,       output/rulebook.jsonl, rules/,
                      barcelona_guide, golden_set       build_rulebook.py,            rulebook/ (law book), eval/
                                                        build_rules.py, run_golden,   → rule cards, The laws
                                                        compile_rulebook.py
        │
        ▼
 5_daylight           input/bars_exp1_daylight          bars_daylight.py              output/ (lit depth)
                      (the daylight model's runs)                                     → app/data/daylight.json
        │
        ▼
 6_check_the_shop     4_laws_and_rules/output/rules     flags.py, run_flags.py        output/ (verdicts)
                      + app/data/annex4_grup.json                                     → YES / PARTLY / NO, Grup B/C/D
        │
        ▼
 7_floor_plans        input/datasets (Swiss Dwellings,  build_library.py, plan3.py,   output/library, generation,
                      ResPlan), input/own_plans         library_fit.py, furnish.py,   model3d, sheets → Your homes:
                                                        prisms.py, export_ifc.py, ai  5 layouts, 3D, IFC
        │
        ▼
 8_report_and_city    input/value (idealista18),        value.py, city_runs.py,       output/value, city, dashboard
                      input/costs                       refresh_outcomes.py           → For the city, results page

 app                  app/data (written by the steps)   app/code/build_site.py,       index.html (the website)
                      + the code, library, law book     nomad_web.py, make_share.py   share_copy/ only when sharing
                        read from the step folders
 lab_book             experiments.json, figures/        lab_book/code/build_book.py   site/index.html (the notebook)
 rhino_grasshopper    NOMAD.3dm, NOMAD.gh               code/ (nomad_core.py …)       sheets, 3D in Rhino

 * private: Catastro Sede content (private use only) — stays in private/, never shared
```

Supporting the whole: the **lab book** (`lab_book/`), **Rhino** (`rhino_grasshopper/NOMAD.3dm`, one file), the **approval checkpoint**
for facades, the **share copy**, and the **team repo** (only what Bars needs).

---

## 1. FIND THE SHOPS (empty premises and unused buildings)

**Purpose.** Know every empty ground-floor premises in Barcelona, where its door is, and whether its zone could take homes.

| Source | Licence | Stored | Used for |
|---|---|---|---|
| Cens de locals en planta baixa 2024 (Ajuntament de Barcelona, Open Data BCN) | CC BY 4.0, credit "Ajuntament de Barcelona" | `0_shared_input/census/2024_CensComercial_BCN.csv` | every premises: door point, address, empty or active, offer (rent / sale), activity, flags (street, market, gallery, centre, shopping street, night, 24 h), cadastral reference |
| Mapa Urbanístic de Catalunya, "Qualificació" (Generalitat, via gissrv.diba.cat ArcGIS) | Generalitat open data, attribution | `0_shared_input/zoning/` | the PGM zone of each premises |
| Catastro INSPIRE Buildings (AMB towns) | INSPIRE licence, transformed, cite DGC | `1_find_the_shops/input/amb/` | unused buildings in the 35 other AMB towns |
| idealista18 asking prices 2018 | ODbL (credit, share-alike for databases) | `8_report_and_city/output/value/` (via `8_report_and_city/code/value.py`) | €/m² nearby, shown as a hint |

**Scripts (in order).**
1. `1_find_the_shops/code/zoning.py` — joins each census door to its MUC zone (a door in a street polygon takes the building's zone
   within 8 m) and applies the zoning gate (step 3) → `1_find_the_shops/output/zoning/lookup.json`, `empty_premises_zoning.csv`.
2. `1_find_the_shops/code/warehouses.py` — Catastro industrial / retail / office buildings with no homes → `1_find_the_shops/output/warehouses/`,
   `app/data/warehouses.json` (census hint "empty premises / no active business / active business": a hint, not proof).
3. `1_find_the_shops/code/amb.py`, `1_find_the_shops/code/amb_base.py` — the metropolitan area → `app/data/amb.json`, `amb_base.json`.
4. `1_find_the_shops/code/avoid.py` — NOMAD's answer per premises (not allowed / not liveable / keep it a shop / candidate / not
   modelled; "keep it a shop" = lowest 10 % of retail within 100 m, a design choice).
5. `app/code/build_site.py` — writes `app/data/premises.json` (6,149 empty premises), `basemap.json`, the 3D city tiles
   `app/data/city/` and `nomad.json`.

**Where used.** City in 3D (every building raised from its floor count: 5 m + 3 m a floor, an estimate), the 2D map, Find
your shop (search, verdict pill), For the city.

---

## 2. READ THE BUILDING

**Purpose.** For each premises: its true shape, its street facade, light wells, the building's hall and stair, doors,
heights, and the facts about the building — every piece marked real or assumed.

### 2a. Footprint and street facade
| Source | Licence | Stored |
|---|---|---|
| Catastro INSPIRE Buildings, Barcelona 08900 (footprints, building parts, floors above / below) | INSPIRE licence: transformed data, cite "Dirección General del Catastro" | `0_shared_input/catastro/raw/` (zip read in place), `buildings.json.gz` |

Scripts: `2_building/code/catastro_buildings.py` (reads the zip) → `2_building/code/real_shops.py` (each premises' building:
ground floor outline, street facade = edges facing a street polygon, simplified 0,15 m, local metres) →
`2_building/output/real_shops/shells.json` (5,322 buildings), `app/data/shells.json`. Where used: the shop shape when nothing
better is known ("Shape: the building's whole ground floor").

### 2b. Units of each building (sizes, uses, floors, year)
| Source | Licence | Stored |
|---|---|---|
| **Catastro CAT file**, Barcelona urban `08900U_14082026.CAT.gz` (accessed 11 Nov 2026) | Download licence: transformed data may be published (cl. 6), never the original online (cl. 5, 8); cite DGC + access date (cl. 12) | `0_shared_input/catastro/CAT_files/` (never committed) |
| ~~Consulta_DNPRC web service~~ (old unit list `units.jsonl`, `2_building/code/catastro_units.py`) | Sede legal notice: **private use only** | replaced by the CAT file on 11 Nov |

Script: `2_building/code/shop_data.py` **step 0** reads records 15 (each unit: floor, door, use letter, built m² with its share
of common parts) and 14 (each construction: year) → `0_shared_input/catastro/units_cat.jsonl` (5,331 buildings, 188,178
units). Where used: rule A/B cuts (2c), the facts panel (2g).

### 2c. The premises' true shape — rules A and B (assumed)
`2_building/code/shop_data.py` **step 2** → `app/data/cut_shells.json` (2,931 premises).
- **Rule A** (one shop unit on the ground floor): the part behind its door on its street facade, as deep as the unit's m²;
  narrower and centred on the door when the front is long. 501 premises.
- **Rule B** (2+ shop units): the street front shared between the census doors (halfway to the next door); area within the
  smallest–largest unit; shallower than 4 m → narrowed round the door. 2,470 premises.
- Rejected (footprint kept): cuts under 2,5 m wide, doors > 8 m from the building, cuts that lose the street facade.
- App order: the premises' own Catastro unit plan (private, 2f) > cut shape ("assumed rule A/B") > footprint.

### 2d. Light wells (patis de llums)
`2_building/code/light_wells.py` — holes in the INSPIRE ground floor = light wells open to the sky (2,856 shops, 4,817 wells);
holes above a roofed ground floor kept as information (610 shops) → `patios`, `wells_above` in `shells.json`. Where used:
the engine never puts a flat over a well (`plan3._PATIOS`); drawn hatched blue in the plans.

### 2e. The building's hall and stair — real or rule C (assumed)
- **Real** (private use only): Catastro Visor 3D ground-floor "Local COMUN" polygons, `2_building/code/existing_core.py`
  → `existing` in `shells.json` (531 buildings).
- **Rule C** (shareable): `2_building/code/shop_data.py` **step 2b** → `app/data/cores.json` (2,942 buildings). From the land
  registry entrance point: a 3,5 m hall to the **stair tower** (the building's smallest INSPIRE part as tall as the tallest;
  right place in 93 % of 171 tested buildings), else to the nearest **light well** with the stair beside it (91 % of 88),
  else a 3,5 × 7,6 m **box** (72 % of 294). 3,5 × 7,6 m = median of 1,692 real halls. Labelled with method + accuracy.
- Where used: the engine keeps homes off it and may use it as the flats' way in (`existing`, `coreAssumed`).

### 2f. Floor plans of the whole building (private use only)
`2_building/code/catastro_plans.py` (Visor 3D per-floor unit polygons, ~600 parcels) → `2_building/code/catastro_site.py` →
`app/data/catastro/b_XX.json`; `2_building/code/unit_shells.py` → `app/data/unit_shells.json` (640 premises' own unit) and
`unit_skips.json`. Where used: "The building" floor by floor, 2D and 3D. **Never shared**: the share copy replaces them
with INSPIRE outlines.

### 2g. Doors, entrances and facts
| Source | Licence | Stored |
|---|---|---|
| Catastro INSPIRE Addresses, Barcelona `A.ES.SDGC.AD.08900.zip` (3,7 MB; points marked "Entrance") | INSPIRE licence, cite DGC | `0_shared_input/catastro/addresses/` |
| City census 2024 (2-1) | CC BY 4.0 | |

`2_building/code/shop_data.py` **step 1** → `0_shared_input/catastro/entrances.json`, `app/data/doors.json` (3,479 buildings
with an entrance, 13,833 premises doors). **Step 3** → `app/data/facts/f_XX.json` (census rows per building, CAT units,
year, floors). Where used: Find your shop › Show the details (status, offer, where, other premises, doors, building),
dots and squares on the shop plan in Your homes.

### 2h. Heights (LiDAR)
| Source | Licence | Stored |
|---|---|---|
| ICGC Territorial LiDAR v3.1 (2021-2023) | CC BY 4.0 | `0_shared_input/lidar/` (grids `0_shared_input/lidar/grid/*.npz`) |

`2_building/code/lidar_heights.py` → `2_building/output/heights/heights.csv`, `app/data/heights.json` (street level, roof p25/p50/p75,
floor height estimate). Where used: the height box in Your homes ("Estimated from ICGC LiDAR"), unless an approved facade
gives the ground floor's own height.

### 2i. The facade (read from a photo) — with the approval checkpoint
| Source | Licence | Stored |
|---|---|---|
| Catastro facade photo service (one 1024 × 768 photo per parcel) | Sede: **private use only**; photos and pictures from them never on GitHub, the site or the team | `private/catastro_facade_photos/` |
| ICGC LiDAR (2h) | CC BY 4.0 | |
| Grounding DINO base (IDEA-Research) | Apache-2.0 | Hugging Face cache, run in `tools/train-venv` |
| OpenCV | Apache-2.0 | |

One file, `3_facade/code/facade.py` (method: `docs/facade_workflow.md`):
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
7. **approve** (user) — `facade.py <ref> approve` freezes a copy in `3_facade/output/approved/<ref>/`;
8. **export** — only approved copies → `app/data/facades.json` (with the facade line's ends).
Approved: Av. Diagonal 413 (5,75 + 6 × 3,80 m), Pl. Sortidor 4 (4,30 + 5 × 3,15 m).
Where used: The building (facade drawing, floors at measured heights, openings on the 3D), the height box; Rhino 2D
(`rhino_grasshopper/code/record_facade.py`, when Rhino is closed). Not yet: the shop's street-wall openings in the plans (item 8).

### 2j. The 1:1000 city map (downloaded, not wired in yet)
CartoBCN `TOPO1000_GPKG.zip` (product 144, Dec 2025), CC BY 4.0 → `2_building/input/topo1000/cartobcn/gpkg/`: building
polygons, street / inner-block facade lines, party walls, floor counts (roman numerals), patio labels Pi / Pe / T. Checked:
no stairs drawn inside buildings. Planned: facade and party-wall lines for windows; patio labels for light.

### 2k. Plan source label (checklist item 3)
`app/index.html` `basisRows / basisHtml / basisText`: every picked shop carries its basis — plan source (real plan /
Catastro unit / building footprint / assumed shape) and, per part, real or assumed (shape, hall and stair, light wells,
windows, height). Shown above the layouts, in Saved and Compare, and in the PDF report.

---

## 3. ZONING — may this ground floor take homes?

| Source | Licence |
|---|---|
| MUC zoning (step 1) | Generalitat open data |
| PGM 1976 / MPGM 1999 art. 225.7 (RPUC scans, OCR) | public planning register |

`1_find_the_shops/code/zoning.py` gate: **YES** zones 12, 13a, 13b, 14b, 15 (built along street lines); **CHECK** 18, 20, 22@,
14 remodelling (a detailed plan decides); **NO** industry and urban systems. Barcelona: 5,026 of 6,149 (82 %) YES.
AMB towns fall back to MUC codes (A1/A2/N = NO, R = CHECK). Where used: the verdict pill and "WHY" in Find your shop;
NO forces NO and CHECK caps the layouts at PARTLY (`nomad_core.add_zoning`, "Zoning" card first).

---

## 4. THE RULES — from official texts to checkable rule cards

| Source | Licence | Stored |
|---|---|---|
| BOE consolidated texts (CTE Part I, LOE, TRLSRU, Ley 12/2023, LPH) via the BOE open-data API | legislative texts, no copyright (LPI art. 13), cite BOE | `4_laws_and_rules/input/national/` |
| CTE Documentos Básicos (DB-HS, SUA, SI, HR, HE), codigotecnico.org | official, cite | `4_laws_and_rules/input/national/cte_db/` |
| Decret 141/2012 and other Catalan texts (Portal Jurídic / DOGC, saved by hand: robots disallow bots) | public legal texts | `4_laws_and_rules/input/catalonia/raw/` |
| PGM / MPGM normes (RPUC, scanned → Tesseract OCR cat+spa) | public register | `4_laws_and_rules/input/pgm/` |
| Barcelona guide "canvi d'ús de locals a habitatge" (2025-03), ordinances | Ajuntament | `4_laws_and_rules/input/barcelona_guide/` |

Scripts: `4_laws_and_rules/code/fetch_national.py`, `fetch_cte_db.py`, `fetch_catalonia.py`, `ocr_pgm.py` → `fetch_pgm.py`,
`fetch_bcn_guide.py` → `4_laws_and_rules/code/build_rulebook.py` → `4_laws_and_rules/output/rulebook.jsonl` (one chunk per article, current wording,
tables as rows). `4_laws_and_rules/code/build_rules.py` → `4_laws_and_rules/output/rules/rules.json`: **16 rule cards**, each with value, article, page and the
exact sentence (checked word for word); `4_laws_and_rules/output/rules/review.json`. `4_laws_and_rules/code/run_golden.py` on `4_laws_and_rules/input/golden_set/golden_set.csv`
(16 questions, answers checked in the source). `4_laws_and_rules/code/compile_rulebook.py` + `add_anchors.py` → the law book
(23 official PDFs, 1,408 pages, index, bookmarks, highlighted lines) in `4_laws_and_rules/output/rulebook/`.
Not built: the RAG knowledge base; rule cards were made from the rulebook directly.
Where used: every check card cites its rule and opens the law in The laws (flipbook). Private: the law book (`4_laws_and_rules/output/rulebook`
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

`5_daylight/code/bars_daylight.py` (his model on NOMAD's shells) → `5_daylight/output/`, `app/data/daylight.json` (lit depth
per shop, class livable / needs a change / not livable). Where used: the daylight line in Your shop; the engine's
liveability rule (living rooms and bedrooms need half their floor within the lit depth; 5,5 m assumed where no
prediction). Daylight is liveability, not a legal fail. Owned by Bars: NOMAD does not refine it.

---

## 6. CHECK THE SHOP

- `6_check_the_shop/code/flags.py` — rule cards on the shop and its flats → YES / PARTLY / NO with margin and citation; the "flats
  inside the shop" geometry test; daylight bands.
- **Conversion group** — team data `annex4_grup.json` (`tools/annex4_grup.py` in the team repo, by Bars, from the CAT file: the shop's built
  area ÷ the building's) → Grup C (≤ 50 %: building rules exempt except 2.2.1), Grup D (> 50 %: 2.1, 2.2.2, 2.6, patios
  −10 %), Grup B (whole building). Copied to `app/data/annex4_grup.json`; `app/code/nomad_web.py` `_annex4` puts a
  "Conversion group" card first and checks the community room for Grup D with 8+ homes (fail → YES becomes PARTLY).
- Where used: Your homes › Checks; Find your shop › RULES.

---

## 7. FIT THE HOMES — 2D layouts, furniture, 3D

### 7a. The plan library (real flats)
| Source | Licence | Stored |
|---|---|---|
| Swiss Dwellings v3.0.0 (Archilyse, Zenodo 7788422) | CC BY 4.0 | `7_floor_plans/input/datasets/` |
| ResPlan (m-agour) | CC BY 4.0 | |
| CubiCasa5K (test only, Exp 1) | CC BY-NC-SA 4.0 — never in the product | `7_floor_plans/input/datasets/test_plans_cubicasa` |

Scripts: `7_floor_plans/code/clean_dataset.py`, `learn_room_programs.py` (room sizes from 13,444 rule-passing flats →
`app/data/room_programs.json`), `7_floor_plans/code/habitability.py` (`docs/habitability_rules.md`),
`7_floor_plans/code/build_library.py`, `build_resplan.py`, `placed_plans.py` (room placer, NOMAD placed), `own_plans.py` (your
DXF / JSON plans), `street_library.py` → `7_floor_plans/output/library/library_street.json` (the flats NOMAD can use), `fit_table.py` →
`fit_table.json`. **Plan AI** `7_floor_plans/code/` (U-Net trained on the library, RTX 3060, `tools/train-venv`) →
`7_floor_plans/output/library/library_ai.json`, merged as "NOMAD AI".

### 7b. The generator
`7_floor_plans/code/plan3.py` (the engine) with `library_fit.py` (stretch solver, plan-graph and door / turning checks,
circulation filter), `furnish.py` (legal furniture: wardrobe, bed square, worktop, WC / basin / shower, washing machine,
1,20 m circle), `shared.py` (shared-space homes, Llei 18/2007), `building.py` (whole buildings, Annex 4 Grup B: cores,
stairs, lifts, mezzanines, patios, exits), `layout.py`, `plan2.py`, `better.py` (older strategies kept as parts).
Rules inside: street lobby, shared hall, flats along every facade within 25 m, street-cut flats ≤ 9 m, side-entered flats,
real halls / rule C halls and light wells never built over, evaluation matrix (`_score`).
Runs in: Rhino (`rhino_grasshopper/code/nomad_core.py`), the app (Pyodide, `app/py/worker.js` + `app/py/src/*.txt`, via
`app/code/nomad_web.py`).

### 7c. 3D and exports
`7_floor_plans/code/prisms.py` (walls, windows 60 % × 1,5 m on street walls, doors, furniture as prisms) → the app's 3D;
`7_floor_plans/code/export_ifc.py` (IfcOpenShell, LGPL; trimesh, MIT) → `7_floor_plans/output/model3d/*.ifc`, `*.glb`;
`rhino_grasshopper/code/nomad_model.py` → Rhino walls models. three.js r147 (MIT) in the app.

Where used: Your homes (5 layouts, cards, daylight bands, real-plan gallery, furniture, 3D walls / zoning), Rhino
(`rhino_grasshopper/NOMAD.3dm` layers "06 NOMAD experiments", "07 NOMAD lab book").

---

## 8. REPORT, SAVED, THE CITY

- **Saved / Compare** — `app/index.html` (`saveShop`, `drawSaved`, `drawCompare`), stored per user in the artifact
  database when published, else in the browser; carries the plan source label.
- **PDF report** — jsPDF 2.5 (MIT) in the page: plans, rule cards, 3D, plan source.
- **For the city** — `8_report_and_city/code/city_runs.py` → `8_report_and_city/output/city/homes.csv`, `app/data/city_homes.json` (12,755 homes on
  flat heights; the user chose not to rerun with LiDAR heights).
- **Results page** (`8_report_and_city/output/dashboard/`, `8_report_and_city/code/refresh_outcomes.py`) and **deck / videos** (`app/code/add_deck_slides.py`,
  `presentation/videos/`).

---

## 9. ACROSS ALL STEPS

### Privacy and sharing
| What | Who sees it |
|---|---|
| App `app/`, code (every `<step>/code/`), lab book `lab_book/`, law book, `docs/`, `CLAUDE.md` | you only (your private repo `bhavinimanot-arch/nomad`; most paths in `.gitignore`) |
| Catastro facade photos and pictures from them | this computer only (`.gitignore`: `3_facade/output/**/*.jpg`) |
| Visor 3D plans, Consulta_DNPRC units | this computer / your app only |
| **Share copy** `old/site_share/` (`app/code/make_share.py`) | safe to share: Visor data → INSPIRE outlines, unit sizes → counts, no facades, rounded shapes |
| Team repo `iaac-maai/nomad` | only what Bars needs: PR #13 (merged) = `tools/shop_data.py` + `nomad/06_Results/shops_doors_facts/` in the team repo (transformed) |

### Checkpoints
- **Facades**: nothing reaches the app before you approve the drawing (frozen copies).
- **Publishing**: nothing is published or pushed without your word.
- **Rhino**: one file `rhino_grasshopper/NOMAD.3dm`; never written while Rhino has it open; backup first.

### Records
- Lab book `lab_book/experiments.json` → `lab_book/code/build_book.py` → `lab_book/site/index.html` (E01-E48).
- Checklist `docs/floorplan_checklist.md`; facade method `docs/facade_workflow.md`; licences `docs/licences.md`.

### Environments
- `.venv` — data, engine, drawing (shapely, pandas, matplotlib, pymupdf).
- `tools/train-venv` — GPU work: Grounding DINO, OpenCV, PyTorch (plan AI, facades).
- Pyodide in the browser — the engine in the app. Rhino 7.1 IronPython — Grasshopper / Rhino scripts.

---

## 10. RUN IT AGAIN, IN ORDER

```
# 1 shops + zoning
.venv/Scripts/python 1_find_the_shops/code/zoning.py
.venv/Scripts/python 1_find_the_shops/code/warehouses.py
# 2 building
.venv/Scripts/python 2_building/code/catastro_buildings.py
.venv/Scripts/python 2_building/code/real_shops.py
.venv/Scripts/python 2_building/code/light_wells.py
.venv/Scripts/python 2_building/code/lidar_heights.py
.venv/Scripts/python 2_building/code/shop_data.py            # units (CAT) → doors → shapes A/B → halls C → facts
# 2i facades (per building; you check, then approve)
tools/train-venv/Scripts/python.exe 3_facade/code/facade.py <ref>          # straighten, read, analyse
.venv/Scripts/python 3_facade/code/facade.py <ref> draw
.venv/Scripts/python 3_facade/code/facade.py <ref> approve
# 4 rules
.venv/Scripts/python 4_laws_and_rules/code/build_rulebook.py
.venv/Scripts/python 4_laws_and_rules/code/build_rules.py
.venv/Scripts/python 4_laws_and_rules/code/run_golden.py
# 5 daylight
.venv/Scripts/python 5_daylight/code/bars_daylight.py
# 7 library (after changes to plans or checks)
.venv/Scripts/python 7_floor_plans/code/street_library.py
.venv/Scripts/python 7_floor_plans/code/fit_table.py 7
# 8 site + share copy + lab book
.venv/Scripts/python app/code/build_site.py
.venv/Scripts/python app/code/make_share.py
.venv/Scripts/python lab_book/code/build_book.py
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
