# Licences

Every repo, dataset and library we use, with its licence.

| Name | Type | Licence | Link | Notes |
|---|---|---|---|---|
| requests | Python library | Apache 2.0 | https://github.com/psf/requests | |
| pandas | Python library | BSD 3-Clause | https://github.com/pandas-dev/pandas | |
| PyMuPDF | Python library | AGPL-3.0 (or commercial) | https://github.com/pymupdf/PyMuPDF | AGPL: if Nomad is ever offered as a closed web service, check this or switch to pdfplumber |
| pdfplumber | Python library | MIT | https://github.com/jsvine/pdfplumber | |
| pydantic | Python library | MIT | https://github.com/pydantic/pydantic | |
| Swiss Dwellings v3.0.0 (Archilyse / Zenodo 7788422) | Floor-plan dataset (test set) | CC BY 4.0 | https://zenodo.org/records/7788422 | Credit "Swiss Dwellings, Archilyse AG" in any presentation |
| shapely 2.2 | Python library | BSD 3-Clause | https://github.com/shapely/shapely | Room geometry checks |
| Tesseract OCR 5.4 (UB-Mannheim Windows build, via winget) | OCR engine | Apache 2.0 | https://github.com/tesseract-ocr/tesseract | Installed in C:\Program Files\Tesseract-OCR |
| tessdata_best cat + spa | OCR language models | Apache 2.0 | https://github.com/tesseract-ocr/tessdata_best | In nomad/tools/tessdata/ |
| Portal Jurídic de Catalunya consolidated texts | Legal texts (Generalitat) | Public legal texts; "no tenen caràcter oficial" | https://portaljuridic.gencat.cat | Cite ELI link |
| RPUC documents | Planning documents (Generalitat) | Public register (art. 103 TRLU: planning is public) | https://planejamenturbanisme.territori.gencat.cat/rpucportal/ | Cite RPUC record |
| CTE Documentos Básicos (codigotecnico.org) | Official PDFs (Ministerio de Vivienda) | Site terms not yet read | https://www.codigotecnico.org/DocumentosCTE/DocumentosCTE.html | Official regulatory text; cite the PDF + page |
| BOE legislación consolidada | Official open data (API) | Reuse terms of boe.es, not yet read | https://www.boe.es/datosabiertos/ | Legal texts themselves are not under copyright in Spain (LPI art. 13); still cite BOE as source |
| MitUNet | Wall model (code + weights) | Code MIT; weights CC BY-NC 4.0 (trained on CubiCasa5K) | https://github.com/aliasstudio/mitunet | external/mitunet; tested only; non-commercial weights = master use only |
| matplotlib | Python library | Matplotlib licence (BSD-style) | https://matplotlib.org | Lab book charts (src/book/make_figures.py) |
| CubiCasa5K | 5,000 real floor-plan scans + SVG answers (Exp 1 real-scan test; test split only) | CC BY-NC-SA 4.0 (non-commercial, share alike) | https://zenodo.org/records/2613548 (DOI 10.5281/zenodo.2613548) | data/datasets/cubicasa5k/raw; master use only, not a product |
| IfcOpenShell | Python library (IFC export, Stage 7) | LGPL-3.0 (used as a library, not modified) | https://ifcopenshell.org | src/model3d/export_ifc.py |
| trimesh | Python library (glTF export, Stage 7) | MIT | https://github.com/mikedh/trimesh | src/model3d/export_ifc.py |
| mapbox-earcut | Python library (polygon triangulation for trimesh) | ISC | https://github.com/skogler/mapbox_earcut_python | src/model3d/export_ifc.py |
| Cens de locals en planta baixa 2024 | Open data (Ajuntament de Barcelona) | CC BY 4.0 | https://opendata-ajuntament.barcelona.cat/data/dataset/cens-locals-planta-baixa-act-economica | Step 3 zoning (src/zoning/zoning.py); cite "Ajuntament de Barcelona" |
| Mapa Urbanístic de Catalunya (MUC) | Zoning polygons (Generalitat, Departament de Territori) | Generalitat open data (terms on territori.gencat.cat, attribution required); served by Diputació de Barcelona's ArcGIS | https://territori.gencat.cat/ca/06_territori_i_urbanisme/observatori_territori/mapa_urbanistic_de_catalunya/ | Step 3 zoning; cite "MUC, Departament de Territori" |
| Catastro INSPIRE Buildings, Barcelona (08900) | Building footprints + building parts with floors (Dirección General del Catastro) | Free reuse of Catastro data with attribution ("Dirección General del Catastro"), per the Catastro's reuse terms | https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/08/08900-BARCELONA/A.ES.SDGC.BU.08900.zip | data/barcelona/catastro/raw (zip kept: read in place, never unpacked); src/building/catastro_buildings.py, real_shops.py |
| Catastro INSPIRE Buildings, the other 35 AMB towns | Building footprints, use, dwellings, floors (Dirección General del Catastro) | Same Catastro reuse terms, attribution "Dirección General del Catastro" | links from https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/08/ES.SDGC.BU.atom_08.xml | data/amb (zips deleted after reading; only buildings with no homes kept); src/zoning/amb.py. MUC zoning for these towns from the same service as Barcelona |
| Arbrat viari / zona / parcs (street, zone and park trees) | Open Data BCN (Ajuntament de Barcelona), 222,617 trees | CC BY 4.0 | https://opendata-ajuntament.barcelona.cat/data/dataset/arbrat-viari (+ arbrat-zona, arbrat-parcs) | data/barcelona/trees/trees_*.csv (position, size class, palm, species; raw CSVs deleted after processing); 3D city |
| Pyodide | Python in the browser (website engine) | MPL-2.0 | https://pyodide.org | site/py (bundled, unmodified) |
| three.js | 3D in the browser | MIT | https://threejs.org | site/index.html (cdn.jsdelivr three@0.147.0) |

## Catastro CAT file (src/building/cat_file.py)
- Data: Dirección General del Catastro, alphanumeric CAT file, municipality 08900 Barcelona. Free download after a request on the Sede Electrónica del Catastro; reuse under the Catastro's open-data conditions (attribution "Dirección General del Catastro"). Saved by hand in data/barcelona/catastro/CAT_files/.
- Record layout read from hypercadaster_ES (BeeGroup-cimne, EUPL-1.2, `downloaders.catstruct[14]`). We only reuse the published field positions (the CAT format itself), no code copied.

## Rulebook book (src/rulebook/compile_rulebook.py)
- BOE consolidated PDFs (LOE, CTE Part I, TRLSRU, Ley 12/2023, LPH): Agencia Estatal Boletín Oficial del Estado; legislative texts are not subject to copyright (Ley de Propiedad Intelectual art. 13); BOE reuse terms apply (cite the source). Saved in data/national/raw/.
- The other 18 PDFs are the official texts already listed above (codigotecnico.org, Portal Jurídic, Agència de l'Habitatge, RPUC, AMB, Ajuntament). Pages are reproduced unchanged; NOMAD adds cover, index, dividers, page numbers, bookmarks, OCR text on scans.
- PDF.js 3.11.174 (Mozilla, Apache-2.0), loaded from cdnjs on the website to show the pages.

## Bars's daylight model (src/daylight/bars_daylight.py)
- Code and data: Bars Babila, NOMAD team, repository iaac-maai/nomad (private, IAAC MaAI), folder exp1_daylight (results.csv = 50 Ladybug/Honeybee runs). No licence file: used inside the NOMAD team project with the author's agreement (the user asked to apply it). Cloned to external/bars-nomad. Ladybug Tools (AGPL-3.0 core, run by Bars in Grasshopper) is not redistributed here; only his results CSV and his model settings are used. XGBoost (Apache-2.0), scikit-learn (BSD-3).

## Catastro ground-floor plans (step 3, added 2026-11-01)
- Source: Sede Electrónica del Catastro, Visor 3D (per-floor unit polygons from FXCC sketches), read by src/zoning/catastro_plans.py.
- Terms (Sede aviso legal): the licence for its contents is limited to download and private use, contents kept intact, source cited (Ley 37/2007). We cite "Dirección General del Catastro" under every plan.
- OK for the master project and our private website. Before sharing the site publicly or using it in a product, check Catastro's reuse licence for this data (the Visor 3D is not an official download service).

## NOMAD plan AI (src/ai, added 2026-11-03)
- Training data: the plan library built from Swiss Dwellings v3.0.0 (CC BY 4.0) and ResPlan (CC BY 4.0, github.com/m-agour/ResPlan); attribution kept. Model code is our own (PyTorch, BSD-style licence); no third-party model code or weights used. GSDiff (GPL-3.0) and DiffPlanner (no licence) were read as reference only.

## Metropolitan base map (src/zoning/amb_base.py, added 2026-11-05)
- MUC zones of the 36 AMB towns (Generalitat open data, attribution), merged and simplified to site/data/amb_base.json.
