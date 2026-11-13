# NOMAD — can an empty shop in Barcelona become homes?

## Current team folders

Bhavini's official site is in `Bhavini's files/app/`. Bars's work is in `Bars's files/`, using the same numbered
team layout; see [`Bars's files/0_START_HERE.md`](Bars's%20files/0_START_HERE.md). Start the official site with
`python serve.py --site bhavini` (also the default), or preview Bars's previous site with `python serve.py --site bars`.
Some historical sections below refer to the pre-reorganization paths.

> **Scope: NOMAD is an academic, non-commercial IAAC project, for now.** Every data source and licence is read for
> that use in `docs/LICENCES.md`, which also lists what would have to change if NOMAD ever became commercial.

NOMAD checks an empty ground-floor shop in Barcelona against the city's zoning and shows the laws behind the answer.
For every one of the 6,149 empty premises in the city's 2024 census it says whether the zone allows homes, sorts the
city into **candidate / risky / zoning doesn't allow**, and keeps every law it uses in one book of the official texts.
It is a master's research prototype (IAAC MaAI 2026-27, Bhavini, Alvaro, Bars): a first check, not a licence.

## Open the website on your computer

You need Python 3.10 or newer ([python.org](https://www.python.org/downloads/)). Then, in a terminal, in this folder:

```bash
pip install pymupdf pillow      # once, if you need Bars's law book pages
python serve.py                 # official Bhavini site; Ctrl+C stops it
python serve.py --site bars     # Bars's previous site
```

The official site starts with `python serve.py` or `python serve.py --site bhavini`. `serve.py --site bars` selects
Bars's previous version. The Bars site can download official law PDFs and build its own rulebook pages when needed.
`python check_setup.py` tells you what is ready.

## What is on the website, and where it comes from

| Part of the site | What you see | Built from (file in this repo) | Data source · licence |
| --- | --- | --- | --- |
| **Find your shop** | Type an address: does the zone allow homes, why, NOMAD's category, street life, the building in 2D and 3D | `Bars's files/app/data/premises.json`, `data/catastro/b_*.json`, `data/basemap.json` | Census of ground-floor premises 2024, Ajuntament de Barcelona (Open Data BCN, CC BY 4.0); zoning: Mapa Urbanístic de Catalunya, Generalitat (open data, attribution); buildings: Catastro (reuse with attribution) |
| **The map** | Every empty shop, coloured by zone or by category; empty warehouses and commercial buildings | `data/premises.json`, `data/warehouses.json`, `data/basemap.json` | same as above; warehouses: Catastro buildings with no homes |
| **Saved** and **the PDF report** | Your saved shops side by side; a one-page report with the zoning answer and its sources | made in the page from the shop you checked | same as above |
| **For the city** | Candidate / risky / zoning doesn't allow, counted by district, and the list | `data/premises.json`, `data/warehouses.json` | same as above |
| **City in 3D** | Every building raised from its floor count (estimated heights, for context only), streets, parks, trees, sun and shadows | `data/city/` (index, layers and 1 km tiles) | Catastro INSPIRE buildings; MUC ground layers; Open Data BCN trees (CC BY 4.0) |
| **The laws** | 22 official documents in one book (the Ajuntament's guide is linked, not reproduced: its reuse terms are not stated), with the rules NOMAD checks bookmarked | `rulebook/index.json`, `rulebook/anchors.json`, `rulebook/sources.lock.json` (the pinned version of each law); pages downloaded by `Bars's files/4_laws_and_rules/code/get_rulebook.py` | BOE, codigotecnico.org, Portal Jurídic de Catalunya, Agència de l'Habitatge, RPUC, AMB, Ajuntament: official texts, cited by article |
| **Rule cards** (Research) | The 16 rules NOMAD checks, each with the sentence of the law it comes from | `data/nomad.json` (copied from `Bars's files/4_laws_and_rules/output/rules/rules.json`) | the official texts above; every sentence checked against the official PDF (`Bars's files/docs/LAW_TEXT_CHECK.md`) |
| **Experiments, Workflow, Precedents, Sources** (Research) | What the team tested and learned; daylight: 5 shops simulated in Radiance | `data/nomad.json`, `data/daylight_validated.json`, and the page itself | Radiance simulations by Bars (`Bars's files/5_daylight/`); sources table on the page and in `docs/AI_LOG.md` |

Bars's former site files are in `Bars's files/app/`; the official site is in `Bhavini's files/app/`.

## Map of the repo

| Folder or file | What it is | Feeds |
| --- | --- | --- |
| `serve.py` | Opens the website on your computer (one command). | the whole site |
| `Bhavini's files/app/` | **The official website.** | Official preview: `python serve.py --site bhavini` |
| `Bars's files/app/` | Bars's previous, self-contained site and its data. | Previous version: `python serve.py --site bars` |
| `nomad/02_Code/src/` | The 17 scripts that **rebuild the website's data** from the raw data (census, Catastro, MUC zoning, law PDFs). The raw data is large and not in git: it lives in `02_Code/data/` on the computer that rebuilds the data. `app/build_site.py` writes `nomad.json`, `premises.json`, `basemap.json` and the 3D city; `zoning/zoning.py` gives each premises its zone; `zoning/warehouses.py` the empty buildings; `zoning/catastro_site.py` the building of each shop; `check/avoid.py` the street life; `rules/build_rules.py` the rule cards; `rulebook/compile_rulebook.py` the book of laws; `collect/` downloads and reads the laws. | `Bars's files/app/data/` |
| `nomad/06_Results/` | The 19 result files `build_site.py` reads for the parts the site still shows (zoning summary, street life, golden set, Exp 1 plan-reading scores). | Find your shop, Rule cards, Experiments |
| `Bars's files/4_laws_and_rules/output/rules/` | Bars's checked `rules.json` and `annex4.json`; Bhavini's separate copies are left untouched. | Bars's previous site |
| `Bars's files/5_daylight/` | **Daylight simulations** in Grasshopper + Ladybug/Honeybee (Radiance): the Rhino and Grasshopper files, the shop variants and their results, and the 5 real shops simulated (`results_shops.csv`). The per-shop grid simulation will build on it. `daylight_thresholds.json`: the EN 17037 targets for Barcelona from the TMYx weather file (climate.onebuilding.org; no licence stated, not redistributed). | Experiments (Exp 4), daylight of 2 shops in Find your shop |
| `Bars's files/*/code/` | Bars's step scripts are grouped with their work; see each step README for commands. `Bars's files/tools/import_site_data.py` is a one-time setup utility. | Bars's steps and previous site |
| `docs/AI_LOG.md` | Every use of AI in the project (IAAC rule), and the table of sources and licences. | Sources |
| `docs/DATA_INVENTORY.md` | Every file of the published site (321): type, size, origin, where the site uses it. | — |
| `Bars's files/docs/LAW_TEXT_CHECK.md` | The rule cards' sentences compared with the official PDFs, and what was corrected. | Rule cards |
| `Bars's files/docs/ANNEX4.md` | Conversions (Decret 141/2012 Annex 4): which card applies when, how Grup C or D is computed for each shop, how to run it, and the Catastro CAT licence. | Rule cards, Find your shop |
| `docs/LICENCES.md` | The licence of every published file and every source, the attribution the site shows, and what is still to check. | Sources |
| `Bars's files/docs/OPEN_QUESTIONS.md` | Legal and data questions NOMAD cannot settle by itself, and who could answer them. | — |
| `Bars's files/docs/PARKED.md` | Features taken off the site for now (the "Your homes" layout engine, weights, plan upload, Ask NOMAD), their files, and what must be true before they come back. | — |
| `Bars's files/lab_book/README.md` | One line for each experiment that is not on the site; they are complete on the branch `archive/experiments`. | — |
| `Bars's files/docs/CLEANUP.md` | What the 9–10 Nov 2026 cleanup removed, parked and fixed, why, and how it was tested. | — |
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
`nomad/02_Code/src/` (each one says how at its top) and copy their output into `Bars's files/app/data/`.
After new Radiance runs of real shops: `python "Bars's files/5_daylight/code/daylight_validated.py"`.

Grup C or D for each shop (Decret 141 Annex 4), after downloading the Catastro CAT file (needs a login; see
`Bars's files/docs/ANNEX4.md`): `python "Bars's files/6_check_the_shop/code/annex4_grup.py" --cat <file>.CAT.gz --accessed YYYY-MM-DD`.

## Law versions

Every law in Bars's previous site is pinned in `Bars's files/4_laws_and_rules/input/rulebook/sources.lock.json`: the URL of the version used, its
official version date (and what that date is based on), the download date and two fingerprints (the file and its text).
The site shows "Law texts as of <date>" and a version next to each document. To see whether an official text changed:

```bash
python "Bars's files/4_laws_and_rules/code/get_rulebook.py" --check     # lists the changed articles; changes nothing
python "Bars's files/4_laws_and_rules/code/get_rulebook.py" --accept    # after review, updates the lock and rebuilds the Bars book
```

## Publishing (standing rule)

The website is published only from `main`, and only after a pull request has been merged. Never from another branch,
never before the merge, and never to anyone else's artifact. The published site is
https://claude.ai/artifact/MBLnc4q9R1XusSQQyjkvYX.

API keys live only in `.env`, which never goes to GitHub. The repo is private.
