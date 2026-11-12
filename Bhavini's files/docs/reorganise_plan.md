# NOMAD — new folder plan

**Done 12 Nov 2026.** The map of the result is `0_START_HERE.md`. The safety copy was checked against Rhino and the app, then sent to the Recycle Bin.

Scanned 12 Nov 2026: **5,036 files, 6.7 GB** (Python environments not counted).
**742 files are stored more than once — 373 MB of extra copies.**

## 1. The new layout

Steps follow `docs/pipeline.md`. Every step has the same three boxes:
**input** (what goes in), **code** (what does the work), **output** (what comes out).

```
nomad
├── 0_START_HERE.md          the map: what is where
├── 0_shared_input           data used by more than one step — stored ONCE here
├── 1_find_the_shops         census, zoning, the zoning gate, warehouses, AMB towns
├── 2_building               Catastro shapes, units, doors, halls, light wells, heights, 1:1000 map
├── 3_facade                 photo → drawing → approval
├── 4_laws_and_rules         law texts, rulebook, 16 rule cards, the law book
├── 5_daylight               the daylight model
├── 6_check_the_shop         YES / PARTLY / NO, conversion group
├── 7_floor_plans            plan library, AI, layouts, furniture, 3D, IFC
├── 8_report_and_city        prices, city run, results page
├── app                      the website (its data folder is the ONE place the website reads from)
├── lab_book                 your notebook
├── docs                     pipeline, licences, checklists, reviews
├── rhino_grasshopper        NOMAD.3dm, NOMAD.gh, Rhino scripts
├── presentation             deck, videos, talk notes
├── tools                    Python environments, plugins, OCR language files
├── private                  Catastro facade photos, Visor 3D plans: never shared
└── old                      replaced versions, backups, test leftovers (kept, not used)
```

Change from my first sketch: **zoning is inside step 1** (it is the same code, `zoning.py`), and the
facade is its own step 3, so there are 8 steps.

## 2. Where every folder goes

### Data (`data/`, 6.7 GB) → input boxes

| Now | Goes to | Why there |
|---|---|---|
| `data/barcelona/catastro/` (buildings, CAT file, addresses, units) | `0_shared_input/catastro/` | used by steps 1, 2, 3, 6 |
| `data/barcelona/census/` | `0_shared_input/census/` | used by steps 1, 2 |
| `data/barcelona/zoning/` | `0_shared_input/zoning/` | used by steps 1, 6 |
| `data/lidar/` | `0_shared_input/lidar/` | used by steps 2, 3 |
| `data/barcelona/catastro/facades/`, `floors/`, `units.jsonl` | `private/` | Catastro Sede: private use only |
| `data/amb/` | `1_find_the_shops/input/` | |
| `data/barcelona/topo1000/` | `2_building/input/` | |
| `data/national/`, `data/catalonia/`, `data/pgm/`, `data/rulebook.jsonl`, `data/barcelona/raw/`, `*chunks.jsonl` | `4_laws_and_rules/input/` | |
| `data/datasets/` (Swiss Dwellings, ResPlan, CubiCasa, test plans) | `7_floor_plans/input/` | |
| `inbox/` (your own plan examples) | `7_floor_plans/input/own_plans/` | |
| `data/barcelona/value/`, `costs/` | `8_report_and_city/input/` | |
| `data/barcelona/trees/` | `app/input/` | only the 3D city uses it |

### Code (`src/`) → code boxes

| Now | Goes to |
|---|---|
| `src/zoning/zoning.py`, `warehouses.py`, `amb.py`, `amb_base.py`, `src/check/avoid.py` | `1_find_the_shops/code/` |
| `src/building/*` | `2_building/code/` |
| `src/zoning/catastro_plans.py`, `catastro_site.py` (Visor) | `2_building/code/` (their data stays in `private/`) |
| `src/facade/facade.py` | `3_facade/code/` |
| `src/collect/*`, `src/rules/*`, `src/rulebook/*`, `src/eval/run_golden.py` | `4_laws_and_rules/code/` |
| `src/daylight/*` | `5_daylight/code/` |
| `src/check/flags.py`, `run_flags.py`, `eval_matrix.py`, `test_slicing.py` | `6_check_the_shop/code/` |
| `src/generate/*`, `src/library/*`, `src/learn/*`, `src/ai/*`, `src/model3d/*`, `src/sim/*`, `src/eval/check_*.py`, `analyse_swiss_dwellings.py` | `7_floor_plans/code/` |
| `src/check/city_runs.py`, `src/app/value.py`, `refresh_outcomes.py` | `8_report_and_city/code/` |
| `src/app/build_site.py`, `nomad_web.py`, `make_share.py`, `viewer.html`, `add_deck_slides.py` | `app/code/` |
| `src/rhino/*` | `rhino_grasshopper/code/` |
| `src/book/*` | `lab_book/code/` |
| `src/kb/`, `src/iterate/` (empty or unused) | `old/` |

### Results (`results/`) → output boxes

| Now | Goes to |
|---|---|
| `results/zoning/`, `warehouses/`, `avoid/` | `1_find_the_shops/output/` |
| `results/real_shops/`, `heights/`, `plan_reading/` | `2_building/output/` |
| `results/facade/` | `3_facade/output/` (the photos inside go to `private/`) |
| `results/rulebook/`, `rule_tests/`, `eval/` | `4_laws_and_rules/output/` |
| `results/daylight/` | `5_daylight/output/` |
| `results/flags/` | `6_check_the_shop/output/` |
| `results/library/`, `generation/`, `habitability/`, `ai/`, `model3d/`, `space/`, `figures/`, `sheets/` | `7_floor_plans/output/` |
| `results/city/`, `value/`, `dashboard/` | `8_report_and_city/output/` |
| `logs/*.log` | the step's `output/logs/` (by name: `city_runs.log` → step 8, `lidar.log` → step 2…) |

### Everything else

| Now | Goes to |
|---|---|
| `site/` | `app/` |
| `site_share/` | not stored any more: made by `make_share.py` only when you share |
| `book/` | `lab_book/` |
| `rhino/`, `grasshopper/` | `rhino_grasshopper/` (backups → `old/`) |
| `presentation/`, `docs/presentation/`, `video/` | `presentation/` |
| `external/` (other people's code: mitunet, floorplan-to-3d, ResPlan, hypercadaster) | `tools/borrowed_code/` |
| `external/bars-nomad/` (an old copy of the team repo) | `old/` (the team repo is pulled fresh anyway) |
| `tools/` | `tools/` |
| `rules/`, `eval/` | `4_laws_and_rules/output/` |
| `README.md`, `START_HERE.md`, `CLAUDE.md`, `requirements.txt`, `OPEN_NOMAD.cmd` | stay at the top |
| `prof.out` (a speed-test leftover) | `old/` |

## 3. Files stored more than once (373 MB) — the fix

| What is doubled | Size | Fix: keep ONE |
|---|---|---|
| CubiCasa test plans: `data/datasets/test_plans_cubicasa` is a copy of part of `cubicasa5k` | 139 MB | keep `cubicasa5k`; the test list becomes a list of names, not copies |
| The law book pages: `results/rulebook/parts`, `site/rulebook/parts`, `site_share/rulebook/parts` | 108 MB | keep it once in `app/rulebook/` |
| Whole app twice: `site/` and `site_share/` (city tiles, Pyodide, data) | ~117 MB | share copy made only when needed, then removed |
| Rhino: `NOMAD.3dmbak` = a backup in `rhino/backups/` | 52 MB | one backup set, in `old/` |
| Lab book pictures in 2-4 places (`book/figures`, `book/site/figures`, `results/generation`, `docs/presentation`) | ~15 MB | one `lab_book/figures/`; the book page and the deck point to it |
| Code copied into the app: `src/generate/*.py` ↔ `site/py/src/*.txt`, `library_street.json` ×3 | ~3 MB | the app reads the step 7 code directly when it is built — no hand copies |
| Old versions of code in `results/space/` (`plan3_before.py`, `library_fit_v48.py`…) | small | `old/` |
| City run "before" files in `results/city/` (`homes_before_E34.csv`…) | small | `old/` |
| 1:1000 map: the zip (`TOPO1000_GPKG.zip`) and its unzipped files both kept; plus an older `Topografic_1-1000.gpkg` | 439 MB + 111 MB | keep the unzipped files; zip and older file to `old/` (or Recycle Bin on your OK) |

Not touched: `rhino/NOMAD_embedded_files/` — Rhino makes those itself.

**The rule from now on:** a file lives in one place. If two steps need it, it goes in `0_shared_input`.
If the website needs it, the step writes it straight into `app/data/`. No copying by hand.

## 4. How it will be done (after you approve this list)

1. A safety copy of the whole folder first.
2. One step at a time: move its files → update the addresses in the code → run that step and the app → check.
3. Then the doubles (to `old/` or the Recycle Bin — never deleted for good).
4. Update `0_START_HERE.md`, the pipeline doc and the lab book with the new addresses.
5. Then on GitHub: remove the old "Bhavini's files" folder and upload the new layout (only the shareable parts:
   no `private/`, `tools/`, `old/`, raw data).

Rhino must be closed while `rhino_grasshopper/` is moved.
