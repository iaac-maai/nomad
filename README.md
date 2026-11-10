# NOMAD — can an empty shop in Barcelona become homes?

NOMAD checks an empty ground-floor shop in Barcelona against the city's zoning and shows the laws behind the answer.
For every one of the 6,149 empty premises in the city's 2024 census it says whether the zone allows homes, sorts the
city into **candidate / risky / zoning doesn't allow**, and keeps every law it uses in one book of the official texts.
It is a master's research prototype (IAAC MaAI 2026-27, Bhavini, Alvaro, Bars): a first check, not a licence.

## Open the website on your computer

You need Python 3.10 or newer ([python.org](https://www.python.org/downloads/)). Then, in a terminal, in this folder:

```bash
pip install pymupdf pillow      # once, for the book of laws (the rest of the site needs nothing)
python serve.py                 # opens http://localhost:8000 in your browser; Ctrl+C stops it
```

The first `python serve.py` downloads the 23 law PDFs from their official websites and builds the book's pages
(about 190 MB, a few minutes). Without `pymupdf` the site still opens; only the pages of "The laws" are missing.
`python check_setup.py` tells you what is ready.

## What is on the website, and where it comes from

| Part of the site | What you see | Built from (file in this repo) | Data source · licence |
| --- | --- | --- | --- |
| **Find your shop** | Type an address: does the zone allow homes, why, NOMAD's category, street life, the building in 2D and 3D | `04_Website/data/premises.json`, `data/catastro/b_*.json`, `data/basemap.json` | Census of ground-floor premises 2024, Ajuntament de Barcelona (Open Data BCN, CC BY 4.0); zoning: Mapa Urbanístic de Catalunya, Generalitat (open data, attribution); buildings: Catastro (reuse with attribution) |
| **The map** | Every empty shop, coloured by zone or by category; empty warehouses and commercial buildings | `data/premises.json`, `data/warehouses.json`, `data/basemap.json` | same as above; warehouses: Catastro buildings with no homes |
| **Saved** and **the PDF report** | Your saved shops side by side; a one-page report with the zoning answer and its sources | made in the page from the shop you checked | same as above |
| **For the city** | Candidate / risky / zoning doesn't allow, counted by district, and the list | `data/premises.json`, `data/warehouses.json` | same as above |
| **City in 3D** | Every building raised from its floor count (estimated heights, for context only), streets, parks, trees, sun and shadows | `data/city/` (index, layers and 1 km tiles) | Catastro INSPIRE buildings; MUC ground layers; Open Data BCN trees (CC BY 4.0) |
| **The laws** | 23 official documents in one book, with the rules NOMAD checks bookmarked | `rulebook/index.json`, `rulebook/anchors.json`; pages downloaded by `tools/get_rulebook.py` | BOE, codigotecnico.org, Portal Jurídic de Catalunya, Agència de l'Habitatge, RPUC, AMB, Ajuntament: official texts, cited by article |
| **Rule cards** (Research) | The 16 rules NOMAD checks, each with the sentence of the law it comes from | `data/nomad.json` (copied from `07_Rules_and_evaluation/rules/rules.json`) | the official texts above; every sentence checked against the official PDF (`docs/LAW_TEXT_CHECK.md`) |
| **Experiments, Workflow, Precedents, Sources** (Research) | What the team tested and learned; daylight: 5 shops simulated in Radiance | `data/nomad.json`, `data/daylight_validated.json`, and the page itself | Radiance simulations by Bars (`exp1_daylight/`); sources table on the page and in `docs/AI_LOG.md` |

All paths in the table start with `nomad/04_Website/` unless they start with a folder of the repo root.

## Map of the repo

| Folder or file | What it is | Feeds |
| --- | --- | --- |
| `serve.py` | Opens the website on your computer (one command). | the whole site |
| `nomad/04_Website/` | **The website.** `index.html` is the page; `data/` its data (27 MB, all in git); `rulebook/` the index of the book of laws; `img/city_still.jpg` the picture shown when a browser has no 3D. | everything you see |
| `nomad/02_Code/src/` | The 17 scripts that **rebuild the website's data** from the raw data (census, Catastro, MUC zoning, law PDFs). The raw data is large and not in git: it lives in `02_Code/data/` on the computer that rebuilds the data. `app/build_site.py` writes `nomad.json`, `premises.json`, `basemap.json` and the 3D city; `zoning/zoning.py` gives each premises its zone; `zoning/warehouses.py` the empty buildings; `zoning/catastro_site.py` the building of each shop; `check/avoid.py` the street life; `rules/build_rules.py` the rule cards; `rulebook/compile_rulebook.py` the book of laws; `collect/` downloads and reads the laws. | `04_Website/data/` |
| `nomad/06_Results/` | The 19 result files `build_site.py` reads for the parts the site still shows (zoning summary, street life, golden set, Exp 1 plan-reading scores). | Find your shop, Rule cards, Experiments |
| `nomad/07_Rules_and_evaluation/` | `rules/rules.json`: the 16 rule cards (value, article, exact sentence). `eval/golden_set.csv`: 16 questions with their answers checked in the law. | Rule cards |
| `exp1_daylight/` | **Daylight simulations** in Grasshopper + Ladybug/Honeybee (Radiance): the Rhino and Grasshopper files, the shop variants and their results, and the 5 real shops simulated (`results_shops.csv`). The per-shop grid simulation will build on it. `daylight_thresholds.json`: the EN 17037 targets for Barcelona from the TMYx weather file (climate.onebuilding.org; no licence stated, not redistributed). | Experiments (Exp 4), daylight of 2 shops in Find your shop |
| `tools/` | `get_rulebook.py` downloads the law PDFs and builds the book's pages · `check_quotes.py` checks the rule cards' sentences against the official PDFs · `daylight_validated.py` makes the validated daylight examples · `import_site_data.py` brought the site's data from the published site into git · `fix_rule_quotes.py` the 9 Nov fix of the rule cards' sentences. | The laws, Rule cards, Experiments |
| `docs/AI_LOG.md` | Every use of AI in the project (IAAC rule), and the table of sources and licences. | Sources |
| `docs/DATA_INVENTORY.md` | Every file of the published site (321): type, size, origin, where the site uses it. | — |
| `docs/LAW_TEXT_CHECK.md` | The rule cards' sentences compared with the official PDFs, and what was corrected. | Rule cards |
| `PARKED.md` | Features taken off the site for now (the "Your homes" layout engine, weights, plan upload, Ask NOMAD), their files, and what must be true before they come back. | — |
| `experiments/README.md` | One line for each experiment that is not on the site; they are complete on the branch `archive/experiments`. | — |
| `CLEANUP.md` | What the 9–10 Nov 2026 cleanup removed, parked and fixed, why, and how it was tested. | — |
| `AGENTS.md` | Notes for AI coding assistants working in this repo. | — |
| `check_setup.py`, `requirements.txt` | Check your computer; the Python packages. | — |
| `.env.example`, `.gitignore` | API keys go only in `.env`, never in git (only the archived Exp 2 uses them). The law PDFs, the built book and the weather file are never committed. | — |

## Branches

| Branch | What is on it |
| --- | --- |
| `main` | the website and what builds it (this map) |
| `archive/experiments` | every experiment the site does not use: Exp 2/3 rule-card drafting, Bhavini's lab book E01–E32, Rhino/Grasshopper, the layout engine's code and results, research documents |
| `parked/before-cleanup` | the site as it was before the cleanup, with the parked features and their data |
| `parked/bhavini-v43` | Bhavini's site versions v41–v43 (5 Nov), untouched |

## Rebuilding the data (for the team)

The website's data is in git, so nobody needs to rebuild it to open the site. To rebuild it you need the raw data in
`nomad/02_Code/data/` and `pip install -r requirements.txt`; then run the scripts in
`nomad/02_Code/src/` (each one says how at its top) and copy their output into `04_Website/data/`.
After new Radiance runs of real shops: `python tools/daylight_validated.py`.

API keys live only in `.env`, which never goes to GitHub. The repo is private.
