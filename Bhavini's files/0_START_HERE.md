# NOMAD — start here

> **On GitHub (12 Nov 2026):** the same folders as on Bhavini's computer, with the code, rules, docs, lab book and
> presentation. `tools/` holds only `requirements.txt`. Left out because of their licences, size or privacy: every
> `input/` and `output/` data folder, `app/data/`, `private/` (Catastro facade photos, Visor 3D plans), the installed
> tools, `NOMAD.3dm`, the videos, `CLAUDE.md` (Claude's working notes), and the facade drawings made from the
> Catastro photo (lab book E47, E48).

NOMAD checks whether an empty shop or warehouse in **Barcelona** can legally become homes.

## The map: what is where

The work goes in steps, in order. **Every step folder has the same three boxes:**

- **input** — what goes in
- **code** — the Python that does the work
- **output** — what comes out

| Folder | What it does |
|---|---|
| `0_shared_input/` | Data that several steps use, kept **once**: Catastro (buildings, CAT file, addresses), city census 2024, zoning map, LiDAR |
| `1_find_the_shops/` | Finds every empty premises and whether its zone allows homes (zoning gate, warehouses, AMB towns) |
| `2_building/` | Reads each building: shop shapes, units, doors, halls and stairs, light wells, heights, the 1:1000 map |
| `3_facade/` | Facade photo → drawing → your approval → the app. Its input is the Catastro photos, kept in `private/` |
| `4_laws_and_rules/` | The official law texts → the rulebook → 16 rule cards → the law book |
| `5_daylight/` | The daylight model: how deep the light reaches in each shop |
| `6_check_the_shop/` | YES / PARTLY / NO for each shop, with the rule that decides it |
| `7_floor_plans/` | Fits the homes: plan library, plan AI, layouts, furniture, 3D, IFC |
| `8_report_and_city/` | Prices, the whole-city run, the results page |
| `app/` | The website. Its `data/` folder is the one place the website reads its data from |
| `lab_book/` | Your notebook: `experiments.json`, `figures/`, and the page in `site/` |
| `docs/` | Pipeline (`pipeline.md`), facade method, checklists, licences, sources |
| `rhino_grasshopper/` | `NOMAD.3dm` and `NOMAD.gh` (the only Rhino and Grasshopper files) and their scripts |
| `presentation/` | Decks, videos, talk notes |
| `tools/` | Installed programs: Python environments, plug-ins, other people's code (`borrowed_code/`), `requirements.txt` |
| `private/` | Catastro facade photos, Visor 3D plans, the old unit list: **never shared** |

**The rule:** each file lives in one place. If two steps need it, it goes in `0_shared_input/`. If the website
needs it, the step writes it straight into `app/data/`. Nothing is copied by hand.

## How to open things

| I want to… | Do this |
|---|---|
| Open the app | Start the `nomad-site` preview, open http://localhost:8766/app/index.html |
| Open the lab book | Start the `nomad-site` preview, open http://localhost:8766/lab_book/site/index.html |
| Work in Rhino | Double-click **`rhino_grasshopper/OPEN_NOMAD.cmd`** (opens `NOMAD.3dm` with `NOMAD.gh`) |
| Make a copy that is safe to share | `.venv/Scripts/python app/code/make_share.py` → `share_copy/` (open `/app/index.html` there) |
| Run a step again | `.venv/Scripts/python <step>/code/<script>.py` — the order is in `docs/pipeline.md` |
| See every source and licence | `docs/pipeline.md`, `docs/licences.md`, `docs/sources.md` |
| Read the project rules and decisions | `CLAUDE.md` (it stays at the top: Claude reads it from there) |
| Install the Python packages | `.venv/Scripts/pip install -r tools/requirements.txt` |
