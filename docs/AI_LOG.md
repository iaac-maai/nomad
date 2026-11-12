# AI use log

IAAC asks us to declare every AI tool we use. Add one row each time.

| Date | Who | Tool | What for | What we kept |
| --- | --- | --- | --- | --- |
| 2026-10-26 | | Claude | Starter kit scripts for experiments 1 and 2 | Scripts in exp1_daylight/ and exp2_rules/, reviewed by the team |
| 2026-10-27 | Bars | Claude | Debugging Grasshopper/Honeybee setup, switching Exp 1 to ground-floor shops, training script | Scripts and settings, reviewed by Bars |
| 2026-10-27 | Bars | Gemini 3.5 Flash Lite (API, model `gemini-3.5-flash-lite`, set as GEMINI_MODEL in .env; 5 of the 155 logged drafts in outputs/run_pdf used the code default `gemini-2.5-flash`) | Drafting 10 rule cards x 5 runs from Decret 141/2012 (Exp 2) | Drafts only, scored against human gold cards |
| 2026-10-28 | Bars | Google Translate | Translating Decret 141/2012 from Catalan to write the gold cards | Nothing kept; gold cards checked against the Catalan PDF |
| 2026-10-28 | Bars | open-notebook + Gemini embeddings | Vector search over Decret 141/2012 (Exp 2c) | Search results used as excerpts for the rule cards |
| 2026-10-28 | Bars | Claude | Code for real-shop data (shops_from_catastro.py, predict_shops.py, map_shops.py), hypercadaster_ES setup, slide deck | Scripts, maps and slides, reviewed by Bars; 5 shops checked in Grasshopper/Radiance (mean error 0.27 DF) |
| 2026-10-28 | Bars | XGBoost (Exp 1 model) | Predicting daylight for 1,376 empty Eixample shops (Catastro via hypercadaster_ES, Open Data BCN census) | Predictions marked v0; only 4 % of shops inside the training range |
| 2026-11-01 | Bars | Claude | Street-width fix (ray from the street facade), EN 17037 thresholds from the Barcelona TMYx weather file (climate.onebuilding.org), lit-depth model and livability classes | Scripts and results reviewed by Bars; lit depth checked on 5 shops against Radiance (mean error 0.55 m) |
| 2026-11-03 | Bhavini | Claude | NOMAD pipeline (laws, zoning, plan reader, rule cards, real-plan library, plan generator, daylight in the check, whole buildings, city view, website, Rhino/Grasshopper, lab book E01-E32), organised into `Bhavini_NOMAD Files/` | Code, results and documents, reviewed by Bhavini; every legal number quoted from the downloaded law |
| 2026-11-03 | Bars | Claude | 30 extra Grasshopper variants for narrow streets and deep shops, whole-Barcelona shop extraction and map, livability classes (36 m2 home in the daylit zone, Decret 141) | Lit depth checked on 5 real shops against Radiance: mean error 0.30 m |
| 2026-11-04 | Bars | Claude | Website daylight update on branch site-daylight-update: new data file from exp1_daylight (80 Radiance simulations, EN 17037 thresholds, lit depth and classes for the 2024 census), 5 m + 3 m building heights in the 3D city, Exp 4 numbering in the docs, Sources table | Changes reviewed by Bars; lit-depth validation re-run (`predict_shops.py --compare`: mean error 0.30 m on 5 shops) |
| 2026-11-04 | Bars | Claude | 3D city colours on site-daylight-update: NOMAD answer per building from the daylight class (zone answer as fallback) and PGM typology per building from data/basemap.json zones labelled by the census shops, computed in the page without rebuilding the tiles | Checked in headless Chrome on 6 central tiles (8,417 buildings): both modes coloured; reviewed by Bars |
| 2026-11-05 | Bhavini | Claude | Website: App / Research layout, workflow order, City in 3D first, 3D clicks linked to Find your shop, percentage weights, plan AI engine; merged with Bars's daylight update. Lab book E33 | Reverted on 9 Nov, not in main (kept on branch parked/bhavini-v43) |
| 2026-11-05 | Bhavini | Claude | Website v41: selected building in 3D (see-through neon), checks open their law in the rulebook, laws list with the open law lit and + dropdowns, Saved and For the city closed with + / -, The laws after step 2, metro base map (amb_base.py), Sources extended | Reverted on 9 Nov, not in main (kept on branch parked/bhavini-v43) |
| 2026-11-05 | Bhavini | Claude | E34 space optimisation: eval_space.py, room placer and connection table (placed_plans.py), homes with their own street door, efficiency figure on the site; website v43 with scrolling columns. City rerun with the new engine still running: city counts are from the old engine | Reverted on 9 Nov, not in main (kept on branch parked/bhavini-v43) |
| 2026-11-09 | Bars | Claude | Post-midterm cleanup on branch cleanup-after-midterm (removals, parked features, data in the repo, law-text check, Sources); see CLEANUP.md | Every change reviewed by Bars before the pull request |
| 2026-11-10 | Bars | Claude | Conversion rules (Decret 141/2012 Annex 4) on branch conversion-rules-annex4: which card applies to new buildings or conversions, Annex 4 note with pages, Grup C/D per shop from the Catastro CAT file (tool and tests; no real CAT data yet), the "≤" checked in DOGC 6245, docs/OPEN_QUESTIONS.md | Every quote checked word for word on its page; no rule value changed; for Bars's review before merging |
| 2026-11-10 | Bars | Claude | Page layout (intro first, For the city and Saved closed by default, official districts), Bhavini's 3D city features restored (click to Find your shop, highlight, sun 12:30; her code, credited), trees layer filled from Open Data BCN (tools/add_trees.py) | Tested in Chrome on the real GPU; PRs #6–#8 |
| 2026-11-11 | Bhavini | Claude | Data on branch bhavini-data-2026-11-11: building entrances (Catastro INSPIRE Addresses) and premises doors (census 2024), census facts and floors per building, and shop_data.py; the cut shop shapes and unit lists are held back until rebuilt from the CAT file (their source, Consulta_DNPRC, is private use only) | Licence check by Bars and Bhavini against the Sede legal notice and the CAT download licence |
| 2026-11-11 | Bhavini | Claude | Same branch: unit list rebuilt from the Catastro CAT file (shop_data.py step 0, records 14/15), cut shop shapes (rules A and B) and unit counts by use added back, transformed for the download licence | Checked against the old list: unit counts match in 5,325 of 5,328 buildings, shop areas within about 1 m² |
| 2026-11-11 | Bars | Claude | Annex 4 v2 (PR #12): tools/annex4_grup.py rewritten (building area per parcel or own construction unit; shop area = ground-floor non-housing space + own basement; data-mismatch check), Grup B added to tools/annex4_cards.py and the site; run on the real CAT file (B 60, C 5,094, D 151, unknown 767) | 10/10 tests, 20/20 Annex 4 quotes (check_quotes.py), spot check by Bars of shops in each group; site checked after publishing |
| 2026-11-12 | Bhavini | Claude | shop_data.py moved to tools/ (as Bars asked), paths set for the repo root and the CAT file in nomad/02_Code/data/barcelona/catastro/cat/ | Script parses; same code as Bhavini's local version |
| 2026-11-12 | Bhavini | Claude | docs/PIPELINE.md: the whole NOMAD pipeline, step by step, with every source, licence, script, output and where it is used | Every path checked against Bhavini's folder; team-repo equivalents listed at the top |

## Sources, tools and licences

The same list as the website's Sources table (9 Nov 2026). No row is left "to check".

| What | Source | Licence |
| --- | --- | --- |
| Empty ground-floor premises | Cens de locals en planta baixa 2024, Ajuntament de Barcelona, Open Data BCN | CC BY 4.0 |
| Buildings (footprints, floors) | Catastro (Dirección General del Catastro) via hypercadaster_ES | EUPL-1.2 (hypercadaster_ES); Catastro data: reuse with attribution |
| Built areas for Annex 4 Grup B/C/D | Catastro alphanumeric data, CAT format, Barcelona urban (Dirección General del Catastro), downloaded by a registered user | Catastro download licence: transformed data may be published citing the DGC and the access date; the original file is not published (docs/ANNEX4.md) |
| Zoning (qualificació) | Mapa Urbanístic de Catalunya, Generalitat de Catalunya, January 2023 | Generalitat open data, attribution |
| Housing rules | Decret 141/2012, CTE, PGM art. 225 (MPGM 1999), MPGM 2004, Ajuntament guide on change of use (2025) | Official texts, cited by article |
| Test shops and flats | Swiss Dwellings v3.0.0, Zenodo (zenodo.org/record/7788422) | CC BY 4.0 |
| Real plan scans | CubiCasa5K, test split only (zenodo.org/records/2613548) | CC BY-NC-SA 4.0, **not for commercial use** |
| Plan reader model | floorplan-to-3d (Yytsi), trained on CubiCasa5K | MIT |
| Daylight, validated examples (Exp 4) | Ladybug Tools + Radiance: 5 empty shops simulated by Bars (exp1_daylight/results_shops.csv, tools/daylight_validated.py). The XGBoost prediction model was dropped. | AGPL-3.0 (Ladybug Tools) |
| Daylight method | EN 17037 (daylight in buildings): D_target and D_minimum for Barcelona (exp1_daylight/daylight_thresholds.json) | European standard, method cited |
| Weather file | Barcelona TMYx (ESP_CT_Barcelona.081800_TMYx.epw), climate.onebuilding.org (Lawrie and Crawley, "Development of Global Typical Meteorological Years (TMYx)") | No licence stated on the site (checked 9 Nov 2026); cited as the site asks; the file is not redistributed (not in the repo) |
| Rule cards (Exp 3) | open-notebook (vector search) and Gemini 3.5 Flash Lite, model `gemini-3.5-flash-lite` (drafting) | MIT (open-notebook); Gemini: Google API terms |
| Code help | Claude (Anthropic) | Anthropic terms of use |
| Base map (data/basemap.json) | Barcelona's zones from the MUC (muc_qualificacio_bcn.geojson), merged and simplified (nomad/02_Code/src/app/build_site.py) | Generalitat open data, attribution |
| OCR of PGM/RPUC legal texts for the rulebook | Tesseract OCR (nomad/02_Code/src/collect/ocr_pgm.py) | Apache-2.0 |
| Trees in the 3D city | Open Data BCN street, zone and park trees | CC BY 4.0 |
| 3D viewer | three.js 0.147 | MIT |
| Rulebook viewer | PDF.js 3.11 | Apache-2.0 |
| PDF report | jsPDF 2.5 | MIT |
| Fonts | Inter, Inter Tight, JetBrains Mono | SIL OFL 1.1 |

Removed on 9 Nov 2026 with the features that used them: ResPlan, IfcOpenShell/trimesh and Pyodide (parked layout
engine, see PARKED.md), the metropolitan-area data (Results section), idealista18 prices, Catastro Visor 3D units.
