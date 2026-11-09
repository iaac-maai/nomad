# AI use log

IAAC asks us to declare every AI tool we use. Add one row each time.

| Date | Who | Tool | What for | What we kept |
| --- | --- | --- | --- | --- |
| 2026-10-26 | | Claude | Starter kit scripts for experiments 1 and 2 | Scripts in exp1_daylight/ and exp2_rules/, reviewed by the team |
| 2026-10-27 | Bars | Claude | Debugging Grasshopper/Honeybee setup, switching Exp 1 to ground-floor shops, training script | Scripts and settings, reviewed by Bars |
| 2026-10-27 | Bars | Gemini 3.5 Flash Lite (API) | Drafting 10 rule cards x 5 runs from Decret 141/2012 (Exp 2) | Drafts only, scored against human gold cards |
| 2026-10-28 | Bars | Google Translate | Translating Decret 141/2012 from Catalan to write the gold cards | Nothing kept; gold cards checked against the Catalan PDF |
| 2026-10-28 | Bars | open-notebook + Gemini embeddings | Vector search over Decret 141/2012 (Exp 2c) | Search results used as excerpts for the rule cards |
| 2026-10-28 | Bars | Claude | Code for real-shop data (shops_from_catastro.py, predict_shops.py, map_shops.py), hypercadaster_ES setup, slide deck | Scripts, maps and slides, reviewed by Bars; 5 shops checked in Grasshopper/Radiance (mean error 0.27 DF) |
| 2026-10-28 | Bars | XGBoost (Exp 1 model) | Predicting daylight for 1,376 empty Eixample shops (Catastro via hypercadaster_ES, Open Data BCN census) | Predictions marked v0; only 4 % of shops inside the training range |
| 2026-11-01 | Bars | Claude | Street-width fix (ray from the street facade), EN 17037 thresholds from the Barcelona TMYx weather file (climate.onebuilding.org), lit-depth model and livability classes | Scripts and results reviewed by Bars; lit depth checked on 5 shops against Radiance (mean error 0.55 m) |
| 2026-11-03 | Bhavini | Claude | NOMAD pipeline (laws, zoning, plan reader, rule cards, real-plan library, plan generator, daylight in the check, whole buildings, city view, website, Rhino/Grasshopper, lab book E01-E32), organised into `Bhavini_NOMAD Files/` | Code, results and documents, reviewed by Bhavini; every legal number quoted from the downloaded law |
| 2026-11-03 | Bars | Claude | 30 extra Grasshopper variants for narrow streets and deep shops, whole-Barcelona shop extraction and map, livability classes (36 m2 home in the daylit zone, Decret 141) | Lit depth checked on 5 real shops against Radiance: mean error 0.30 m |
| 2026-11-04 | Bars | Claude | Website daylight update on branch site-daylight-update: new data file from exp1_daylight (80 Radiance simulations, EN 17037 thresholds, lit depth and classes for the 2024 census), 5 m + 3 m building heights in the 3D city, Exp 4 numbering in the docs, Sources table | Changes reviewed by Bars; lit-depth validation re-run (`predict_shops.py --compare`: mean error 0.30 m on 5 shops) |
| 2026-11-04 | Bars | Claude | 3D city colours on site-daylight-update: NOMAD answer per building from the daylight class (zone answer as fallback) and PGM typology per building from data/basemap.json zones labelled by the census shops, computed in the page without rebuilding the tiles | Checked in headless Chrome on 6 central tiles (8,417 buildings): both modes coloured; reviewed by Bars |
| 2026-11-05 | Bhavini | Claude | Website: App / Research layout, workflow order, City in 3D first, 3D clicks linked to Find your shop, percentage weights, plan AI engine; merged with Bars's daylight update. Lab book E33 |  |

## Sources, tools and licences

The same list as the website's Sources table. "to check" = licence not confirmed yet.

| What | Source | Licence |
| --- | --- | --- |
| Empty ground-floor premises | Cens de locals en planta baixa 2024, Ajuntament de Barcelona, Open Data BCN (CC BY 4.0) | CC BY 4.0 |
| Buildings | Catastro (Dirección General del Catastro) via hypercadaster_ES | EUPL-1.2 (hypercadaster_ES); Catastro data: reuse with attribution |
| Weather file | Barcelona TMYx (ESP_CT_Barcelona.081800_TMYx.epw), climate.onebuilding.org | to check |
| Daylight method | EN 17037 (daylight in buildings): D_target and D_minimum for Barcelona (exp1_daylight/daylight_thresholds.json) | European standard, method cited |
| Test shops and flats | Swiss Dwellings v3.0.0, Zenodo (zenodo.org/record/7788422) | CC BY 4.0 |
| Real flat plans | ResPlan, github.com/m-agour/ResPlan | CC BY 4.0 (data); MIT (code) |
| Real plan scans | CubiCasa5K, test split only (zenodo.org/records/2613548) | CC BY-NC-SA 4.0, non-commercial use only |
| Rule cards (Exp 3) | open-notebook (vector search) and Gemini 3.5 Flash Lite (drafting) | MIT (open-notebook); Gemini: Google API terms |
| AI assistant and code help | Claude (Anthropic): the website's "Ask NOMAD" assistant and help writing the code | Anthropic terms of use |
| Base map (data/basemap.json) | Barcelona's zones from the Mapa Urbanístic de Catalunya (MUC, muc_qualificacio_bcn.geojson), merged and simplified (Bhavini_NOMAD Files/02_Code/src/app/build_site.py) | Generalitat open data, attribution |
| Metropolitan area, 36 towns (data/amb.json) | Catastro INSPIRE Buildings (one file per town) and MUC zoning served by the Diputació de Barcelona (Bhavini_NOMAD Files/02_Code/src/zoning/amb.py) | Catastro data: reuse with attribution; MUC: Generalitat open data, attribution; Diputació service: to check |
| Price estimates | idealista18 dataset (2018 asking prices) | ODbL |
| Trees in the 3D city | Open Data BCN street, zone and park trees | CC BY 4.0 |
| 3D viewer | three.js 0.147 | MIT |
| Rulebook viewer | PDF.js 3.11 | Apache-2.0 |
| PDF report | jsPDF 2.5 | MIT |
| Python in the browser | Pyodide | MPL-2.0 |
| Fonts | Inter, Inter Tight, JetBrains Mono | SIL OFL 1.1 |
