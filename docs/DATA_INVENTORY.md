# The website's files

Every file of the published site (claude.ai artifact MBLnc4q9R1XusSQQyjkvYX, version of 4 Nov 2026): 321 files,
114.2 MB. Written by `tools/import_site_data.py` on 9 Nov 2026. Sizes are those of the published copy.

| File | Type | Size | Where it came from | Where the site uses it | Now |
| --- | --- | ---: | --- | --- | --- |
| `data/amb.json` | JSON | 280 kB | nomad/02_Code/src/zoning/amb.py: 36 metropolitan towns | nothing (Results section removed) | not copied: removed |
| `data/basemap.json` | JSON | 1,365 kB | nomad/02_Code/src/app/build_site.py basemap(): MUC zones merged and simplified | the 2D map, 3D city typology | in the repo |
| `data/catastro/b_* (94 files)` | JSON | 14,676 kB | nomad/02_Code/src/zoning/catastro_site.py: Catastro building parts per parcel | Find your shop: the building | in the repo, without the 600 Visor 3D unit buildings |
| `data/city/index.json` | JSON | 815 kB | nomad/02_Code/src/app/build_site.py city(): tile index and empty-shop façades | City in 3D | in the repo |
| `data/city/layers.json` | JSON | 3,170 kB | nomad/02_Code/src/app/build_site.py city(): MUC ground layers (no trees: the trees are in the tiles) | City in 3D | in the repo |
| `data/city/t_* (132 files)` | JSON | 14,290 kB | nomad/02_Code/src/app/build_site.py city(): Catastro INSPIRE building parts, 1 km tiles | City in 3D | in the repo; trees added on 10 Nov 2026 (below) |
| `data/city_homes.json` | JSON | 87 kB | nomad/02_Code/src/check/city_runs.py: home counts per place | nothing (home counts removed) | not copied: home counts removed |
| `data/daylight.json` | JSON | 419 kB | nomad/02_Code/src/app/daylight_site.py (XGBoost predictions, Exp 4) | nothing (removed) | not copied: Exp 4 model removed |
| `data/demo_shops.json` | JSON | 4 kB | nomad/02_Code/src/app/build_site.py engine(): five test shops | nothing (parked) | not copied: parked layout engine |
| `data/nomad.json` | JSON | 242 kB | nomad/02_Code/src/app/build_site.py (rules from 07_Rules_and_evaluation, experiment results from 06_Results) | rule cards, golden set, experiments, workflow, tally | in the repo, without demos / real / check / golden_rows (layout results) |
| `data/premises.json` | JSON | 1,952 kB | nomad/02_Code/src/app/build_site.py premises(): census 2024 + MUC zoning + street life (src/check/avoid.py) | Find your shop, the map, categories, For the city, 3D city | in the repo, only x, y, address, district, ref, zone, answer, why, offer, shops |
| `data/room_programs.json` | JSON | 2 kB | nomad/02_Code/src/app/build_site.py engine(): flat programmes from Swiss Dwellings | nothing (parked) | not copied: parked layout engine |
| `data/shells.json` | JSON | 2,337 kB | nomad/02_Code/src/app/build_site.py engine(): shop outlines for the layout engine | nothing (parked) | not copied: parked layout engine |
| `data/warehouses.json` | JSON | 2,950 kB | nomad/02_Code/src/zoning/warehouses.py: Catastro buildings with no homes + MUC zoning | map mode 'warehouses', For the city | in the repo, without shells (layout-engine outlines) |
| `img/city_still.jpg` | JPEG image | 140 kB | screenshot of the 3D city | City in 3D when WebGL is off | in the repo |
| `img/D* (26 files)` | PNG image | 778 kB | nomad/02_Code/src/rhino/make_demo.py, redraw_demos.py: plans of the five demo shops | nothing (unused before the cleanup) | not copied: parked |
| `index.html` | HTML | 276 kB | the page itself (hand-written) | the whole site | in the repo |
| `models/* (6 files)` | JSON | 583 kB | nomad/02_Code/src/rhino/ glTF export of the demo shops | nothing (unused before the cleanup) | not copied: parked |
| `py/pyodide-lock.json` | JSON | 106 kB | Pyodide 0.26.4 distribution (MPL-2.0) | nothing (parked layout engine) | not copied: load from the CDN when the engine returns |
| `py/pyodide.asm.js` | JavaScript | 1,229 kB | Pyodide 0.26.4 distribution (MPL-2.0) | nothing (parked layout engine) | not copied: load from the CDN when the engine returns |
| `py/pyodide.asm.wasm` | WebAssembly | 10,088 kB | Pyodide 0.26.4 distribution (MPL-2.0) | nothing (parked layout engine) | not copied: load from the CDN when the engine returns |
| `py/pyodide.js` | JavaScript | 15 kB | Pyodide 0.26.4 distribution (MPL-2.0) | nothing (parked layout engine) | not copied: load from the CDN when the engine returns |
| `py/python_stdlib.json` | JSON | 3,123 kB | Pyodide 0.26.4 standard library | nothing (parked layout engine) | not copied: load from the CDN when the engine returns |
| `py/src/* (15 files)` | Python source as text | 1,456 kB | nomad/02_Code/src/* (the engine's Python, copied as .txt) | nothing (parked) | on parked/before-cleanup |
| `py/worker.js` | JavaScript | 2 kB | hand-written worker for the layout engine | nothing (parked) | on parked/before-cleanup |
| `rulebook/anchors.json` | JSON | 5 kB | nomad/02_Code/src/rulebook/compile_rulebook.py | The laws (rule bookmarks) | in the repo |
| `rulebook/index.json` | JSON | 14 kB | nomad/02_Code/src/rulebook/compile_rulebook.py | The laws (flipbook index) | in the repo |
| `rulebook/parts/* (26 files)` | PDF | 53,817 kB | nomad/02_Code/src/rulebook/compile_rulebook.py from the official PDFs | The laws (pages) | not copied: tools/get_rulebook.py downloads the official PDFs |

No data file in the repo is over 5 MB (the largest, data/city/layers.json, is 3.2 MB), so none needs Git LFS.
If a file over 5 MB is added, track it with `git lfs track <file>` before committing it.

## Added since the cleanup

| File | Type | Size | Where it came from | Where the site uses it | Licence |
| --- | --- | ---: | --- | --- | --- |
| `data/city/t_* (trees)` | JSON, in the tiles | 15,704 kB for all 134 tiles (+1,414 kB of trees) | `tools/add_trees.py`: Ajuntament de Barcelona, Open Data BCN, street trees (arbrat viari, 145,552), zone trees (arbrat zona, 44,067), park trees (arbrat parcs, 33,299), version of 1 Oct 2026: 222,918 trees, size class from categoria_arbrat, palms from tipus_element. The published tiles had been built without them, so the layer drew nothing; 2 tiles in the index had no file and now hold trees only | City in 3D, "trees" layer (loaded with the tiles near the view) | CC BY 4.0 |
| `data/city/index.json` | JSON | 816 kB | as above, plus the tree count and its source (`trees`) | City in 3D: the layer's label | — |
| `data/districts.json` | JSON | 92 kB | `tools/districts.py`: Ajuntament de Barcelona, Open Data BCN, Unitats administratives (district boundaries), simplified to 1 m | For the city: districts | CC BY 4.0 |
| `data/annex4_grup.json` | JSON | <1 kB until filled | `tools/annex4_grup.py`: Decret 141/2012 Annex 4 Grup C or D per shop, from the Catastro CAT file (pending) | Find your shop: conversion rules | derived from Catastro data, see docs/ANNEX4.md |
| `data/daylight_validated.json` | JSON | 1 kB | `tools/daylight_validated.py`: the 5 Radiance shops (exp1_daylight) | Find your shop, Experiments | team's own |

