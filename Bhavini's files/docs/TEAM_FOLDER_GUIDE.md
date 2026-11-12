# NOMAD — how we all keep our files (team guide)

For Alvaro, Bars and Bhavini. One layout for everyone, so any of us can open anyone's folder and find things at once.
Bhavini's folder already uses it: https://github.com/iaac-maai/nomad/tree/main/Bhavini's%20files

---

## 1. The idea in one picture

NOMAD is a recipe with 8 steps. Every step is a box with three drawers:

```
          ┌──────────────────── one step ────────────────────┐
 input ─► │  input/   what goes in (data, documents, photos)  │
          │  code/    the Python, Grasshopper, scripts        │ ─► output
          │  output/  what comes out (results, pictures)      │
          └───────────────────────────────────────────────────┘
```

You never wonder where something is: find the step, then open input, code or output.

---

## 2. The layout (the same for all three of us)

```
<Name>'s files/
├── 0_START_HERE.md          one page: what is in my folder
├── 0_shared_input/          data that more than one of MY steps uses (kept once)
├── 1_find_the_shops/        empty premises, zoning, warehouses
├── 2_building/              Catastro shapes, units, doors, halls, light wells, heights
├── 3_facade/                facade photo → drawing → approval
├── 4_laws_and_rules/        law texts, rulebook, rule cards, law book, Annex 4 rules
├── 5_daylight/              daylight simulations and the daylight model
├── 6_check_the_shop/        YES / PARTLY / NO, conversion group (Grup B / C / D)
├── 7_floor_plans/           plan library, layouts, furniture, 3D, IFC
├── 8_report_and_city/       prices, the whole-city run, results page
├── app/                     a website or viewer you made (if any)
├── lab_book/                your experiments: what you did, result, decision
├── docs/                    notes, checklists, licences, sources
├── rhino_grasshopper/       .3dm, .gh and their scripts
├── presentation/            slides, videos, talk notes
└── private/                 anything that must never be shared (stays on your PC)
```

Inside every step folder: `input/`, `code/`, `output/`.

**Only make the folders you need.** If you have nothing for facades, there is no `3_facade/`. But keep the
**numbers and names exactly as above**, so step 5 is step 5 in everyone's folder.

---

## 3. Where does my file go? (ask these questions in order)

1. **Must it never be shared?** (Catastro facade photos, Catastro Visor 3D plans, anything "private use only",
   passwords, personal data) → `private/`. It never goes on GitHub.
2. **Is it code?** (`.py`, `.gh`, `.ipynb`, scripts) → the step it belongs to → `code/`.
   Rhino / Grasshopper files that are the *main model* → `rhino_grasshopper/`.
3. **Did a program make it?** (results, CSVs, JSON, charts, renders) → that step → `output/`.
4. **Is it data or a document that goes INTO a step?** (downloads, datasets, PDFs of laws, photos)
   → that step → `input/`. If two of your steps need it → `0_shared_input/`.
5. **Is it about an experiment?** → `lab_book/`.  **A note or checklist?** → `docs/`.  **Slides?** → `presentation/`.

Not sure which step? Use the step where the file is **used first**.

---

## 4. The rules

1. **Every file lives in one place.** No copies. If two steps need it, it goes in `0_shared_input/` and both read it
   from there. Code that needs a file reads it where it is; it never copies it.
2. **Same names for everyone:** step folders exactly `1_find_the_shops` … `8_report_and_city`; drawers exactly
   `input`, `code`, `output`. Files: lowercase, words joined by `_`, no spaces (e.g. `daylight_threshold.py`).
3. **Code finds files from the folder, never from your PC's own path.** Write this at the top of each script:
   ```python
   from pathlib import Path
   ROOT = Path(__file__).resolve().parents[2]       # your "<Name>'s files" folder
   SHOPS = ROOT / "5_daylight/input/shops_bcn.csv"
   OUT = ROOT / "5_daylight/output"
   ```
   Never `C:\Users\...` or `/Users/...` inside code. Then the code runs on anyone's computer.
4. **Old versions are not kept next to new ones.** No `_v2`, `_final`, `_old` side by side. Git keeps history;
   delete the old file (to the Recycle Bin) once the new one works.
5. **Big raw data stays off GitHub** (datasets, LiDAR, zips, `.3dm` over 50 MB). Write in your `0_START_HERE.md`
   where to download it.
6. **Licences:** every outside source gets one line in `docs/licences.md` (source, licence, how we may use it).
   Catastro Sede content (Visor 3D, facade photos, Consulta_DNPRC) = private use only → `private/`.
7. **On GitHub you only change your own folder.** Shared things (see section 7) are changed only after we agree.

---

## 5. How to move your files into the layout (step by step)

Do it once, slowly. About an hour.

1. **Pull** the team repo so you have the latest: `git pull`.
2. **Safety copy:** copy your whole folder somewhere else on your PC (not into the repo).
3. **Make the list first, move nothing yet:** for each file write `old place → new place` using section 3.
   Mark files that are copies of each other and files you no longer need.
4. **Make the folders** you need (section 2).
5. **Move** the files (`git mv old new` keeps their history).
6. **Fix the addresses in your code** (rule 3): search your code for every old folder name and change it to the
   new one.
7. **Test:** run each script once and open each `.gh` / `.3dm`. Fix what breaks.
8. **Remove copies and unused files** (to the Recycle Bin, so they can come back).
9. **Write your `0_START_HERE.md`** (template in section 8).
10. **Delete the safety copy** only after everything works.
11. **Push on your own branch and open a pull request** that touches only your folder. Another teammate looks,
    then we merge.

---

## 6. Ready-made maps for the files already in the team repo

### Bars — files in the team repo today → `Bars's files/`

| Now | Goes to |
|---|---|
| `exp1_daylight/shops_bcn.csv`, `shops_validation.csv`, `variants.csv`, `variants_v2.csv` | `5_daylight/input/` |
| `exp1_daylight/*.py` (`make_variants.py`, `daylight_threshold.py`, `gh_read_variant.py`, `gh_record_result.py`, `shops_from_catastro.py`, `make_variants_v2.py`) | `5_daylight/code/` |
| `exp1_daylight/*.gh`, `daylight_v0.3dm` | `5_daylight/code/` (they belong to this experiment) |
| `exp1_daylight/results.csv`, `results_shops.csv`, `daylight_thresholds.json` | `5_daylight/output/` |
| `tools/daylight_validated.py` | `5_daylight/code/` |
| `tools/annex4_grup.py`, `annex4_cards.py`, `test_annex4_grup.py` | `6_check_the_shop/code/` |
| `tools/get_rulebook.py`, `check_quotes.py`, `fix_rule_quotes.py` | `4_laws_and_rules/code/` |
| `tools/transform_catastro.py` | `2_building/code/` |
| `tools/districts.py`, `add_trees.py`, `import_site_data.py` | `app/code/` (they build the team website's data) |
| `tools/shop_data.py` | remove: the original is `Bhavini's files/2_building/code/shop_data.py` (one copy only) |
| `docs/ANNEX4.md`, `LAW_TEXT_CHECK.md`, `law_check_scans/`, `DATA_INVENTORY.md`, `OPEN_QUESTIONS.md`, `AI_LOG.md`, `LICENCES.md`, `screenshots/` | `docs/` |
| `experiments/README.md` | `lab_book/README.md` |

Bars's daylight results are also used by Bhavini's step 5 (`Bhavini's files/5_daylight/input/bars_exp1_daylight/`).
Once Bars's folder is in place, that copy goes and Bhavini's code reads `Bars's files/5_daylight/output/results.csv`
directly (one copy only).

### Alvaro — no files in the team repo yet

Start with `Alvaro's files/` and only the folders you need, using section 3. If your work is on facades, it goes in
`3_facade/`; on floor plans, `7_floor_plans/`; on rules, `4_laws_and_rules/`. Same three drawers inside.

---

## 7. The team repo as a whole

```
iaac-maai/nomad
├── README.md            what NOMAD is + this map
├── TEAM_FOLDER_GUIDE.md this guide
├── Alvaro's files/      the layout above
├── Bars's files/        the layout above
├── Bhavini's files/     the layout above
└── team_website/        the shared website everyone sees (today: nomad/04_Website, run with serve.py)
```

- **One copy of shared things.** The team website and the data it shows live once, in `team_website/`. Personal
  folders never hold a second copy of it.
- **Today `nomad/02_Code/src/` is an older copy of Bhavini's code** and `nomad/06_Results/` copies results from our
  folders. When everyone's folder is in place, those copies go: the website reads from the person's `output/`.
- Root files (`AGENTS.md`, `CLEANUP.md`, `PARKED.md`, `check_setup.py`, `serve.py`, `requirements.txt`) stay at the top
  until we decide together.

---

## 8. Template for your `0_START_HERE.md`

```markdown
# <Name>'s files — start here

What I work on: <one line>.

| Folder | What is in it |
|---|---|
| `5_daylight/` | <what this step does in my work> |
| `docs/` | <notes> |

Not on GitHub (too big or private): <list, and where to download each one>.
How to run my work: `python 5_daylight/code/<script>.py` (in this order: …).
```

---

## 9. The workflow: how the steps feed each other

```
 FOLDER               INPUT (what goes in)              CODE (what does the work)     OUTPUT → WHERE IT SHOWS
 ══════════════════════════════════════════════════════════════════════════════════════════════════════

 0_shared_input       Catastro (buildings, CAT file, addresses), census 2024, zoning map, LiDAR
        │             used by several steps, stored once
        ▼
 1_find_the_shops     census + zoning                   find empty premises,          which shops, which zone
                                                        zoning gate                   → map, "Find your shop"
        ▼
 2_building           Catastro + LiDAR + 1:1000 map     shapes, units, doors,         each shop's building
                                                        halls, light wells, heights   → "The building"
        ▼
 3_facade             facade photo (private) + LiDAR    straighten, read, analyse,    approved facade drawing
                                                        draw → YOU APPROVE            → 3D, plans
        ▼
 4_laws_and_rules     official law texts (BOE, DOGC,    collect, rulebook,            rule cards, law book
                      CTE, PGM, Barcelona)              rule cards, golden set        → every check's citation
        ▼
 5_daylight           shop geometry, weather file       Radiance runs,                how deep light reaches
                                                        the daylight model            → daylight bands
        ▼
 6_check_the_shop     rule cards + building + daylight  checks, Annex 4 group         YES / PARTLY / NO
                                                                                      → verdict, Grup B/C/D
        ▼
 7_floor_plans        Swiss Dwellings, ResPlan,         plan library, fitting,        5 layouts, furniture,
                      your own plans                    furniture, 3D, IFC            3D, IFC → "Your homes"
        ▼
 8_report_and_city    prices (idealista18) + all above  city run, report              city numbers, PDF
                                                                                      → "For the city"

 app                  the steps' outputs                build the website             the website
 lab_book             what we tried                     build the notebook page       the lab book
```

Who works where today: **Bhavini** — steps 1–4, 6–8, app, lab book. **Bars** — step 5 (daylight), step 6
(Annex 4 groups), parts of 4 (law text checks) and the team website. **Alvaro** — to fill in.

---

## 10. Checklist before you push

- [ ] Every file is in `input/`, `code/` or `output/` of the right step (or `docs/`, `lab_book/`, `presentation/`).
- [ ] No file exists twice. No `_old` / `_v2` files next to new ones.
- [ ] No `C:\Users\...` paths inside code; every script runs from the folder.
- [ ] Nothing from `private/` and no Catastro Sede content in the commit.
- [ ] Big data not committed; `0_START_HERE.md` says where to get it.
- [ ] The pull request changes only your own folder.
