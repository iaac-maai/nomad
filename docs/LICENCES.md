# Licences of everything NOMAD publishes

> **Scope: NOMAD is an academic, non-commercial project of IAAC (Master in AI for Architecture and Business
> Innovation, 2026-27), for now.** The statuses below are for that use. If that changes, see the last section.

Audit of 10 Nov 2026, for the published site (claude.ai artifact MBLnc4q9R1XusSQQyjkvYX: 267 files) and every source
in the site's Sources table; the four open items were closed the same day. **Status:** OK = public use allowed and the
attribution is shown · not allowed = must not be published (nothing is).

## The licences behind it

| Licence / terms | What it allows | Attribution it asks for | Text |
| --- | --- | --- | --- |
| **CC BY 4.0** (Open Data BCN) | any use, incl. commercial | the source: "Ajuntament de Barcelona" | creativecommons.org/licenses/by/4.0 |
| **Llicència oberta d'ús d'informació – Catalunya** (Generalitat open data, e.g. the MUC) | reuse and derived works | "Generalitat de Catalunya. Departament de …", and the date of the last update | web.gencat.cat/ca/generalitat/dades-indicadors/dades-obertes/llicencies |
| **Catastro INSPIRE licence** v1.0, July 2016 (Buildings BU, Parcels CP, Addresses AD) | public and commercial use of **transformed** data; the original data "no puede ser difundida por Internet ni por ningún otro medio sin su previa transformación"; new products must not call themselves "cartografía catastral" or "información catastral" | none stated (we cite the Dirección General del Catastro) | catastro.hacienda.gob.es/webinspire/documentos/Licencia.pdf |
| **Catastro download licence** (CAT files) | public and commercial use of transformed data; the original file never online | "Dirección General del Catastro" and the date of access | catastro.hacienda.gob.es/pdf/ovc/licdescargaES.pdf |
| **Catastro legal notice** (web content, incl. the Visor 3D) | download and private use only; reproduction, distribution, public communication and transformation "totalmente prohibida salvo que medie autorización expresa" | the source | catastro.hacienda.gob.es/ayuda/avisolegal.htm |
| **BOE reuse conditions** | reuse, commercial and non-commercial | "Fuente de los datos: Agencia Estatal Boletín Oficial del Estado"; the date of the last update; any change marked as such; no suggestion of official status | boe.es/informacion/aviso_legal |
| **Spanish copyright act, art. 13 (RDL 1/1996)** | laws, regulations, their drafts, court rulings and the acts and opinions of public bodies are not subject to copyright | — | — |
| **Ajuntament de Barcelona** documents | it must allow reuse (Llei 37/2007, Llei 18/2015), as a rule under CC BY, but "per conèixer els usos permesos de cada document s'ha de consultar la metadada 'Condicions d'ús'" | authorship | ajuntament.barcelona.cat/sedac/ca/serveis/reutilitzacio-de-la-documentacio |
| **climate.onebuilding.org** (TMYx) | no licence stated; the site's footer says "All Rights Reserved" | the citation the site asks for: Lawrie, L. K., Crawley, D. B. (2022), Development of Global Typical Meteorological Years (TMYx) | climate.onebuilding.org |
| MIT · Apache-2.0 · SIL OFL 1.1 | any use, keep the notice | the licence notice | — |

## The 267 published files

| Files | What they hold | Source and licence | Attribution on the site | Status |
| --- | --- | --- | --- | --- |
| `index.html` | the page | NOMAD's own code; loads three.js 0.147 (MIT), PDF.js 3.11 (Apache-2.0), jsPDF 2.5 (MIT) from CDNs and Inter / Inter Tight / JetBrains Mono (SIL OFL 1.1) from Google Fonts | Sources rows | OK |
| `data/nomad.json` | the 16 rule cards with their source sentences, the Annex 4 note, experiment results | own; quotes of laws and regulations (art. 13: not subject to copyright; BOE / Generalitat conditions) | each card names its norm, article and page | OK |
| `data/premises.json` | 6,149 empty premises: address, position, district, cadastral reference, zone, street life | Open Data BCN census 2024 (CC BY 4.0) + MUC zoning (Generalitat open licence), joined and classified by NOMAD | Sources rows 1 and 5 | OK |
| `data/basemap.json` | Barcelona's zones, merged and simplified | MUC (Generalitat open licence, data of January 2023) | Sources row | OK |
| `data/warehouses.json` | 4,823 buildings with no homes: reference, built and ground area, floors, façade lengths, zone, census status | Catastro INSPIRE Buildings (via hypercadaster_ES, EUPL-1.2) + MUC + census, selected and combined by NOMAD | Sources row; areas shown as "about" / "≈" | OK (transformed: `tools/transform_catastro.py` rounds built and ground area to 10 m² and the façade lengths, computed by NOMAD, to 0,5 m) |
| `data/catastro/b_*.json` (94) | the building parts of each empty shop's parcel: simplified outlines (local metres) and floors above / below ground; use, dwellings, units | Catastro INSPIRE Buildings (building parts) | Sources row; the panel says "NOMAD's drawing based on Dirección General del Catastro data (INSPIRE)" | OK (transformed: `tools/transform_catastro.py` keeps only the fields the site uses, simplifies every outline (Douglas-Peucker, 0,5 m) and rounds it to 0,5 m: 261,000 → 203,000 points, footprint areas within 0,7 % at the median, every floor count kept) |
| `data/city/t_*.json` (134) | the 3D city tiles: building parts simplified to 0,4 m and quantised, floors, NOMAD typology; trees | Catastro INSPIRE Buildings (transformed into a 3D model) + MUC + Open Data BCN trees (CC BY 4.0, version of 1 Oct 2026) | Sources rows; "estimated heights, for context only" | OK (transformed: a different work) |
| `data/city/index.json`, `data/city/layers.json` | tile index, empty-shop façade bands, tree count; ground layers (roads, paths, parks, rail, water, facilities, zoning tint) | as above; layers from the MUC | Sources rows | OK |
| `data/districts.json` | Barcelona's 10 districts, simplified to 1 m | Open Data BCN, Unitats administratives (CC BY 4.0) | Sources row | OK |
| `data/daylight_validated.json` | 5 shops simulated in Radiance; EN 17037 thresholds | own simulations (Ladybug Tools, AGPL-3.0, as tools); thresholds derived from the Barcelona TMYx weather file | Sources rows (method, weather file with the citation) | OK for this academic project: we publish only derived thresholds, not the file |
| `data/annex4_grup.json` | pending: Grup C / D and a percentage per shop | will be derived from the Catastro CAT file (download licence: transformed data, citing the DGC and the access date) | each answer names the source and date | OK (only the group and the %, never the m²) |
| `img/city_still.jpg` | picture of the 3D city | own rendering of the tiles above | — | OK |
| `rulebook/index.json`, `rulebook/anchors.json` | the book's index and bookmark positions | own | — | OK |
| `rulebook/parts/00.pdf` | cover, how to read, index | own | — | OK |
| `rulebook/parts/01, 02, 08, 09, 10.pdf` | LOE, CTE Part I, TRLSRU, Ley 12/2023, LPH | BOE consolidated texts; laws (art. 13); BOE reuse conditions | Sources row (now with the BOE wording); each part keeps its BOE header and date; the book marks NOMAD's additions | OK |
| `rulebook/parts/03–07.pdf` | CTE DB-SUA, HS, SI, HR, HE | codigotecnico.org; Documentos Básicos approved by Real Decreto 314/2006 (regulations, art. 13) | Sources row | OK |
| `rulebook/parts/11, 14, 15, 16.pdf` | Decret 141/2012, Llei 18/2007, DL 50/2020, TRLU | Portal Jurídic de Catalunya, consolidated texts ("no tenen caràcter oficial"); laws (art. 13) | Sources row; the version date of each is in the index | OK |
| `rulebook/parts/12, 13.pdf` | Circulars 10/2025 and 8 | Agència de l'Habitatge de Catalunya; acts of a public body (art. 13) | Sources row | OK, **after the fix**: both digital signatures blacked out (book pages 671 and 677); Circular 8's showed the signer's DNI |
| `rulebook/parts/17–22.pdf` | MPGM 1999 art. 225, MPGM 2004, MPGM B1600 (3 files), the 2022 agreement on the TSJC ruling | RPUC, Generalitat (planning instruments: regulations, art. 13; Generalitat licence) | Sources row | OK |
| `rulebook/parts/23, 24.pdf` | Ordenances metropolitanes d'edificació, de rehabilitació | AMB (regulations, art. 13) | Sources row | OK |
| `rulebook/parts/25.pdf` | the "4 · Barcelona" divider page only: it names the Ajuntament's guide "Informació bàsica … canvi d'ús de locals" and links to it | own; the guide itself (an information guide, not a regulation) states no reuse terms, so it is **not reproduced**: the book's index and the site link to the official PDF on ajuntament.barcelona.cat | the index entry says "© Ajuntament de Barcelona" and "not reproduced" | OK (link only) |

No file holds a person's ID number: the book build now blacks out every digital signature and stops if an ID number
appears anywhere (`compile_rulebook.py`).

## The Sources table

| Row | Licence | Status |
| --- | --- | --- |
| Empty ground-floor premises 2024 (Open Data BCN) | CC BY 4.0 | OK |
| Buildings: footprints and floors (Catastro INSPIRE, via hypercadaster_ES) | INSPIRE licence (transformed data only); hypercadaster_ES EUPL-1.2 | OK (published only transformed: simplified outlines, rounded areas) |
| The building in 3D, floor by floor (link to the Catastro Visor 3D) | Catastro legal notice: download and private use only; NOMAD links, copies nothing | OK |
| Conversion group, Annex 4 (Catastro CAT data) | Catastro download licence | OK (pending) |
| Zoning (MUC, January 2023) | Llicència oberta d'ús d'informació – Catalunya | OK |
| Housing rules (laws, regulations, circulars, guide) | art. 13; BOE / Generalitat conditions; the Ajuntament's guide linked, not reproduced | OK |
| Test shops and flats (Swiss Dwellings v3.0.0) | CC BY 4.0 | OK (experiments only) |
| Real plan scans (CubiCasa5K, test split) | CC BY-NC-SA 4.0 (the Zenodo record: Attribution, NonCommercial, ShareAlike) | OK for this academic project (CC BY-NC-SA 4.0, non-commercial) |
| Plan reader model (floorplan-to-3d) | MIT (trained on CubiCasa5K, NC) | OK (experiments only) |
| Daylight (Ladybug Tools + Radiance) | AGPL-3.0 / Radiance licence, as tools; results are ours | OK |
| Daylight method (EN 17037) | standard, method cited, not reproduced | OK |
| Weather file (Barcelona TMYx) | no licence stated, "All Rights Reserved" footer; cited as asked | OK for this academic project: we publish only derived thresholds, not the file |
| Rule cards Exp 3 (open-notebook, Gemini) | MIT; Google API terms | OK |
| Code help (Claude) | Anthropic terms | OK |
| Base map (MUC) | Generalitat open licence | OK |
| OCR (Tesseract) | Apache-2.0 | OK |
| Trees (Open Data BCN) | CC BY 4.0 | OK |
| Districts (Open Data BCN) | CC BY 4.0 | OK |
| three.js, PDF.js, jsPDF, fonts | MIT, Apache-2.0, MIT, SIL OFL 1.1 | OK |

## How the four open items were closed (10 Nov 2026)

1. **Catastro building files** (`catastro/b_*.json`, `warehouses.json`): made clearly transformed by
   `tools/transform_catastro.py` (see the rows above). The building panel and the 3D model look the same; the floor
   counts, and so the Annex 4 estimate, are unchanged.
2. **Ajuntament guide** (book part 25): the Ajuntament's reuse page says each document's "Condicions d'ús" decide; the
   guide (May 2023, on the Urbanisme website, not in BCNROC) states none. Not clear, so it is no longer reproduced:
   the book lists it with a link to the official PDF. The book went from 1,409 to 1,400 pages; no other page moved.
3. **TMYx**: OK for this academic project; we publish only derived thresholds, not the file.
4. **CubiCasa5K**: OK for this academic project. Its licence is CC BY-NC-SA 4.0 (non-commercial, share-alike), as the
   Zenodo record states.

## If NOMAD ever becomes commercial

- **CubiCasa5K** (CC BY-NC-SA 4.0): no commercial use. Drop the real-scan results of the plan-reading experiment and
  the plan reader model trained on it (floorplan-to-3d: its weights come from the dataset), or license the data from
  CubiCasa.
- **TMYx**: no licence is stated ("All Rights Reserved"). Ask climate.onebuilding.org for permission, or use a weather
  file with an open licence.
- **Student software licences**: tools used under academic or student licences (Rhino and Grasshopper on IAAC's
  educational licence, and any other educational seat) may not be used for a commercial product; buy commercial
  licences first.
- **Gemini and Claude**: review their terms for commercial use of outputs and for the API plan used.
- **Catastro, BOE, Generalitat, Open Data BCN**: their licences already allow commercial use (of transformed data, for
  the Catastro), so nothing changes beyond keeping the attribution.

## Data in `nomad/06_Results/shops_doors_facts/` (not on the site yet)

| Files | What they hold | Source and licence | Attribution if shown | Status |
| --- | --- | --- | --- | --- |
| `cut_shells.json` | each premises' shape cut to its true size (rules A and B, assumed) | NOMAD's own drawing from Catastro INSPIRE Buildings + the Catastro CAT file (units, accessed 2026-11-11) + census 2024 doors | "NOMAD's assumption based on data from the Dirección General del Catastro (accessed 11 Nov 2026)" | OK (transformed: outlines rounded to 0,5 m, areas to 10 m², no unit areas) |
| `doors.json` | building entrances and premises doors | Catastro INSPIRE Addresses (INSPIRE licence) + census 2024 (CC BY 4.0) | "Dirección General del Catastro"; "Ajuntament de Barcelona" | OK (transformed: points moved to local metres and rounded to 0,5 m) |
| `facts/f_*.json` | per building: census premises (status, offer, activity, flags), floors above / below ground, number of units by use | census 2024 (CC BY 4.0) + Catastro INSPIRE building parts + CAT file (unit counts) | "Ajuntament de Barcelona"; "Dirección General del Catastro (accessed 11 Nov 2026)" | OK (transformed: unit counts by use only, no areas, years or floor lists) |
