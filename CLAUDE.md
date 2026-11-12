# CLAUDE.md — NOMAD, state of the project and how to continue

Claude Code loads this file at the start of every session in this folder. It says where everything is, what has
happened up to **12 Nov 2026**, and what comes next. The project's own rules are in AGENTS.md, imported here:

@AGENTS.md

When this file and the code disagree, the code and git history win; update this file in the same PR.

---

## 1. Where things are

| What | Where |
| --- | --- |
| The repo on this PC | `C:\Users\Usuario\nomad` (Windows 11, PowerShell 5.1; Git Bash also available) |
| GitHub (private) | https://github.com/iaac-maai/nomad (`gh` CLI is logged in) |
| The published website | https://claude.ai/artifact/MBLnc4q9R1XusSQQyjkvYX: publish only from `main`, only after a PR is merged |
| The website's source | `nomad/04_Website/index.html` + `nomad/04_Website/data/` |
| Open it locally | `python serve.py` → http://localhost:8000 |
| Map of every folder | README.md ("Map of the repo") |

**Who's who.** IAAC MaAI 2026-27 master's project, academic and non-commercial. Team: **Alvaro** (git user
`alvaromin-e`, the person working on this PC), **Bars** (`barsbabila`: wrote most of `main`: cleanup, Annex 4,
licences, daylight in Radiance), **Bhavini** (`bhavinimanot`: the original pipeline, site v41–v43, shop data, the
facade method). Every person is "they" in docs unless they say otherwise.

**State of this PC (12 Nov 2026)**

- `.venv` has Python 3.12.4 and only `numpy`. Before running anything: `.venv\Scripts\python -m pip install -r requirements.txt`.
- GPU: NVIDIA GeForce RTX 5080 Laptop, 16 GB. It is a Blackwell card: PyTorch needs a CUDA 12.8+ build
  (older torch wheels fail with "no kernel image"). Check before installing a GPU stack.
- **Not on this PC:** the raw data (`nomad/02_Code/data/` does not exist), the Catastro CAT file, the built law book
  pages (`nomad/04_Website/rulebook/pages` is missing: the first `python serve.py` downloads 23 PDFs, about 190 MB),
  Rhino files, and every input of the facade method (section 5).
- Untracked: `docs/REPOSITORY_ANALYSIS.md` and `outputs/repository_file_inventory.md`, an AI review from 3 Nov, before
  the cleanup. Out of date (it describes `exp2_rules/` and other folders that left `main`). Do not commit them; do not
  trust them over README.md.

---

## 2. What NOMAD is (one paragraph)

For an empty ground-floor shop (local) in Barcelona, NOMAD answers: does the zone allow homes, how risky is it, and
which laws decide it. For each of the **6,149 empty premises** of the city's 2024 census it gives a **category**:
*candidate* (zone YES, no "avoid" flag), *risky* (zone CHECK, or "keep it a shop": the 10 % with the fewest shops
within 100 m), or *zoning doesn't allow* (NO). Every rule it uses is a **rule card** with the exact sentence of the law.
A first check, not a licence. Laws: Decret 141/2012 (habitability; conversions = **Annex 4**), CTE, PGM (MPGM 1999
art. 225), MPGM 2004, Ajuntament guide on change of use (2025).

### What the site shows (on `main`)

| Section | What |
| --- | --- |
| City in 3D (top) | Every building from Catastro footprints, **heights estimated 5 m ground + 3 m per upper floor** (context only), MUC ground layers, 222,918 Open Data BCN trees (layer off by default), sun and shadows. Click a building → Find your shop. Façades: only a Street View link (textures are not open data). |
| Find your shop | Address → zone answer, why, category, street life, the building in 2D/3D, Annex 4 group, link to the Catastro 3D viewer, conversion rules. |
| The map | Every empty shop, by zone or category; empty warehouses and commercial buildings. |
| Saved + PDF report | Saved shops side by side; one-page report with the zoning answer and sources (jsPDF). |
| For the city | Category counts per official district, and the list. No home counts. |
| The laws | 22 official documents in one book (PDF.js), rules bookmarked, "Law texts as of <date>". |
| Research | 16 rule cards, Annex 4 note, Experiments (daylight: 5 shops simulated in Radiance), Workflow, Precedents, Sources. |

---

## 3. History, in order

| Date (2026) | What happened |
| --- | --- |
| 26 Oct–3 Nov | Experiments: Exp 1 daylight (Grasshopper/Honeybee/Radiance, `exp1_daylight/`), Exp 2/3 rule cards drafted with Gemini and scored against gold cards, Bhavini's pipeline and lab book E01–E32. |
| 4 Nov | Bars's site with the daylight update: the version that was published for the midterm. |
| 5 Nov | Bhavini's site v34–v43 (plan AI, layout engine, space optimisation). **Reverted on 9 Nov** with `git revert`, kept on `parked/bhavini-v43`. |
| 9–10 Nov | **Post-midterm cleanup (PR #1, see CLEANUP.md).** Removed: the XGBoost daylight model, home counts from footprints, Catastro Visor 3D units (licence), idealista prices, the golden-set score. Parked: layout engine, weight sliders, plan upload, Ask NOMAD (PARKED.md). Site data (235 files, 27 MB) moved into git. The 16 rule-card quotes checked against the official PDFs (7 corrected, no value changed; `docs/LAW_TEXT_CHECK.md`). |
| 10 Nov | PR #2 folder renamed to `nomad/` · PR #3 law versions pinned (`sources.lock.json`, `--check`/`--accept`) and the standing publish rule · PR #4 3D city on top · PR #5 Annex 4: which card applies to new buildings vs conversions, Grup C/D tool and tests, `docs/ANNEX4.md`, `docs/OPEN_QUESTIONS.md` · PR #6 page layout · PR #7 Bhavini's 3D features restored · PR #8 trees layer. |
| 11 Nov | PR #9 Catastro 3D viewer link · PR #10–#11 licence audit (`docs/LICENCES.md`, signatures blacked out in the law book; scope academic, non-commercial) · **PR #12 Annex 4 v2** run on the real CAT file: **B 60, C 5,094, D 151, unknown 767** · PR #13 Bhavini's shop data (building entrances, premises doors, census facts, cut shop shapes rebuilt from the CAT file, `tools/shop_data.py`) · PR #14 docs. |
| 12 Nov | Bhavini opened **PR #16** with all their files, and pushed branch `docs-pipeline-2026-11-12` (no PR yet). This file was written. |

### Branches and PRs right now

| Branch | State |
| --- | --- |
| `main` | Last merge: PR #14 (`09fd924`). |
| `bhavini-all-files-2026-11-12` → **PR #16, open, not reviewed** | One commit, 100 files, all inside a new folder **`Bhavini's files/`** (`code/src/…`, `docs/`, `grasshopper/`, `lab_book/`, `CLAUDE.md`, `START_HERE.md`). Note: the PR description talks about `nomad/02_Code/…` and `nomad/08_Docs/…`, but the branch actually puts everything under `Bhavini's files/`. Raise this in the review. **The facade code is only here.** |
| `docs-pipeline-2026-11-12` | Bhavini, 12 Nov: adds `docs/PIPELINE.md` (381 lines: the whole pipeline with sources, licences, scripts) + one AI_LOG row. No PR opened. |
| `parked/before-cleanup`, `parked/bhavini-v43`, `archive/experiments` | Kept on purpose; do not merge or delete (README "Branches"). |
| `site-daylight-update` and the merged feature branches | Already in `main`; nothing left on them. |

---

## 4. Rules that matter every session (in addition to AGENTS.md)

- **Branch → PR → merge.** Never commit to `main`. One branch per task, named `<topic>-YYYY-MM-DD`. Fill
  `.github/pull_request_template.md`. Small commits, each saying what changed and why.
- **Publish** the site only from `main`, after the PR is merged, only to the artifact above. Never to Bhavini's
  artifacts (e.g. their results page `X6dBB65ZrzoSfFkBETmiU8`) or anyone else's.
- **AI log:** add a row to `docs/AI_LOG.md` for every piece of AI-assisted work (date, who, tool, what for, what we kept).
- **Law values:** no value without an exact quote from the official text; never OCR text as a quote unless checked on
  the page; `python tools/check_quotes.py` after touching rule cards. Mark our own numbers as "our assumption, not law".
- **Law versions:** never hand-edit `sources.lock.json`. `python tools/get_rulebook.py --check`, show the changed
  articles, `--accept` only when the person agrees.
- **Licences** (`docs/LICENCES.md`): Catastro Sede content (facade photos, Visor 3D, Consulta_DNPRC) is **private use
  only**: never on the site, GitHub, or in a commit. The original CAT file is never published; only transformed
  results (group, percentage, rounded shapes) with "Dirección General del Catastro, accessed <date>".
- **Never commit:** law PDFs, built rulebook pages, `data/ESP_CT_Barcelona.081800_TMYx/`, `.env`, raw data, photos.
- **Scripts run from the repo root** (`python tools/x.py`, not `cd tools`).
- **Windows:** read and write text as UTF-8 (PowerShell 5.1 shows `Ã©` for `é` unless you use Python or
  `-Encoding utf8`). Law texts are Catalan/Spanish with decimal commas ("2,40 m"): keep quotes as written.
- Shop conversions = Decret 141/2012 **Annex 4**. Grup C is the usual case (minimum ceiling height 2,40 m); Grup B =
  whole building (shop ≥ 90 % of the building and no housing: NOMAD's threshold); Grup D = larger share of the
  building. Details and the open readings: `docs/ANNEX4.md`, `docs/OPEN_QUESTIONS.md`.

---

## 5. Current task: the facade

Alvaro is taking over the **facade work** next. Here is what exists, what is missing on this PC, and the decisions
still open. **Ask Alvaro before choosing an approach; do not start the port without agreement.**

### 5.1 What exists (Bhavini's work, only on PR #16's branch)

Method: `Bhavini's files/docs/facade_workflow.md` (read it in full first). Read one Catastro facade photo per building
and turn it into a measured elevation: windows, doors, shopfronts, balconies, floor lines, in metres.

| Step | What | Code |
| --- | --- | --- |
| 1 Straighten | Lens correction, vertical/horizontal vanishing points, turn to face the facade | `code/src/facade/facade.py <ref> straighten` (OpenCV) |
| 2 Heights | Street level from LiDAR ground 1–4 m in front of the facade line; facade height = median LiDAR top 0,5–2,5 m behind it (cornice) | helpers in `facade.py`; grids from `code/src/building/lidar_heights.py` |
| 3 Read | Scale: up from the LiDAR height, across from the Catastro street front (must agree within 3 %). Openings with **Grounding DINO base** (whole, tiles, ground floor, then bay by bay); trees = "hidden", not "no window" | `facade.py <ref> read` (GPU) |
| 3b Analyse | Level the facade, cut upper floors into bands, correlate (≥ 0,55 = same floor type), blend a typical floor, vote | `facade.py <ref> analyse` → `inventory.json` |
| 4 Draw | Architectural rules: one opening size per floor type, symmetry as a *test* (60 % / 0,8 m), balcony stamp, ground-floor rhythm; inferred items marked | `facade.py <ref> draw` → `openings.json`, `elevation.png` |
| Approve | A person checks `elevation.png`, then `facade.py <ref> approve` freezes a copy; only approved facades reach the app | `results/facade/approved/<ref>/` |
| 5 Export | Approved facades → `site/data/facades.json` for the app (drawing, floors at measured heights, openings on the 3D) | `facade.py <ref> export` |
| Rhino | Draw into the single Rhino file `rhino/NOMAD.3dm` (Rhino 7.1, IronPython 2.7) | `code/src/rhino/record_facade.py`, `capture_facade.py`, `run_in_rhino.ps1` |

**Floor-height rule** (agreed with the user, 12 Nov): ground floor has its own height, every upper floor one same
height, fitted on a 5 cm grid, top floor ending ≤ 0,5 m above the LiDAR facade top.

**Results so far (on Bhavini's computer, not in git):**
- Av. Diagonal 413 (`9331705DF2893A`): **approved** (10 Nov version). Ground 5,75 m, upper 3,80 m, top floor ends
  28,55 m, cornice band about 1,9 m to the LiDAR top 30,47 m. The 3D city's 5 m + 3 m estimate gives 23,0 m: 7,5 m too low.
- Pl. Sortidor 4: **waiting for approval**. Ground 4,30 m, upper 3,15 m, top 20,05 m; LiDAR 19,78 m, city model 20,0 m.
  Known limit: real floors here get lower going up (3,25 / 3,45 / 3,15 / 3,04 m); the rule keeps them equal.

**Known limits / to do** (from `docs/handoff_bars_facade.md` and the workflow):
1. Corner (chamfered) buildings: two facade planes in one photo; not solved.
2. Speed: about 2 min per building on an RTX 3060; target under 1 min (model kept loaded, one detector query per tile).
3. On demand: read a facade when a building is clicked, cache the result; needs a backend (local server first).
4. More test buildings in other styles, to test the symmetry and equal-floors rules.
5. Next step in Bhavini's plan: the shop's real openings in the plans.

**Law limits:** Decret 141/2012 conversions: clear height ≥ 2,40 m (already a card). MPGM 1999 art. 225: mezzanine
≥ 2,50 m below and above. The PGM's floor heights for *planta baixa / plantes pis* are **not in the rulebook**: no
number until the article is found and quoted. Slab 0,30, lintel 0,30, balcony slab 0,15 and all tolerances are
**our assumptions, not law**.

### 5.2 What blocks running it on this PC

- **Paths.** `facade.py` sets `ROOT = Path(__file__).parents[2]` and expects Bhavini's own layout:
  `data/barcelona/catastro/facades/<ref>.jpg`, `data/barcelona/catastro/buildings.json.gz`, `data/lidar/grid/*.npz`,
  `results/heights/heights.csv`, `results/facade/…`, `site/data/premises.json`, and a separate GPU venv
  `tools/train-venv`. None of that exists in this repo. In this repo the matching pieces are
  `nomad/04_Website/data/premises.json`, `nomad/06_Results/shops_doors_facts/`, and raw data would go in
  `nomad/02_Code/data/` (git-ignored).
- **Inputs to get (all local, never committed):**
  - Facade photo per building: Catastro `OVCFotoFachada.svc/RecuperarFotoFachadaGet?ReferenciaCatastral=<ref14>`
    (free, no sign-in, **private use only**).
  - Catastro INSPIRE buildings (footprints, floors, street front).
  - ICGC Territorial LiDAR v3.1 (2021–2023, CC BY 4.0): 1 km LAZ tiles reduced to 1 m `top`/`gnd` grids by
    `lidar_heights.py grids`. Download only the tiles of the test buildings, not the whole city. `lidar_heights.py`
    also reads `results/real_shops/shells.json` and `results/warehouses/shells.json`, which are not in this repo.
  - Grounding DINO base (IDEA-Research, Apache-2.0) via a PyTorch/transformers venv that works on the RTX 5080.
- **Rhino:** check whether Rhino 7 is installed here before planning any Rhino step. The Rhino file is not in git.
- **Licence:** photos, `*_PRIVATE.jpg` check pictures and anything only a person can see on the photo stay on this
  PC. What may be published: NOMAD's own measurements and drawings with the Catastro attribution and access date.
  Bhavini's own note goes further ("the results made from it stay on this computer"), so agree with the team, and
  record it in `docs/LICENCES.md`, before any facade result goes on the site.

### 5.3 Decisions to make with Alvaro (and the team) first

1. How the facade code comes to `main`: review and merge PR #16 as it is (the `Bhavini's files/` folder), or move
   only the facade files into the repo layout (e.g. `nomad/02_Code/src/facade/` + a tool in `tools/`) on a new branch.
2. Where local inputs and outputs live (suggestion: `nomad/02_Code/data/…` and a git-ignored results folder) and
   whether `facade.py` gets a configurable root instead of `parents[2]`.
3. The first test: reproduce Av. Diagonal 413 (ground 5,75 / upper 3,80 m) on this PC before changing any rule.
4. Whether the 3D city should take approved facade heights instead of 5 m + 3 m, and how the site labels which
   buildings are measured vs estimated.
5. What the site may show from a facade (licence, see 5.2) and the approval step (who approves).

---

## 6. Other open work (not the current task)

- **Daylight per shop:** "per-shop grid simulation, coming". The XGBoost model was dropped; only the 5 Radiance-simulated
  shops are shown (`tools/daylight_validated.py`). Builds on `exp1_daylight/`.
- **Open legal questions** (`docs/OPEN_QUESTIONS.md`): Annex 4 "sobre o sota rasant" (one total or two tests: 181 of
  6,072 shops would change group); lift rule for Grups B/D; patio 10 % reduction; building vs parcel; which unit is the
  shop; the Grup B 90 % threshold; whether MPGM 2004 area-01 (40 m²) and facade-01 (3 m façade) are still in force
  after the OME; whether CAT-derived results count as "transformed".
- **Parked features** (`PARKED.md`): layout engine, weights, plan upload, Ask NOMAD, each with conditions before it
  can come back. Shared housing: 24 m² private + 6 m² common, 36 m² total (Decret llei 50/2020); never 40 m².
- **Review** `docs-pipeline-2026-11-12` (Bhavini's `docs/PIPELINE.md`) and open a PR for it if the team wants it.

---

## 7. Commands

```powershell
.venv\Scripts\python -m pip install -r requirements.txt   # once on this PC
python check_setup.py                                     # what is ready
python serve.py                                           # the site on http://localhost:8000 (Ctrl+C stops)
python tools/check_quotes.py                              # rule-card quotes against the official PDFs
python tools/get_rulebook.py --check                      # did any law change? (changes nothing)
python tools/annex4_grup.py --cat <file>.CAT.gz --accessed YYYY-MM-DD   # Annex 4 groups (CAT file needs a login)
python tools/test_annex4_grup.py                          # Annex 4 tests (10/10 on 11 Nov)
git fetch origin; git switch -c <topic>-YYYY-MM-DD        # start a task
gh pr create --fill                                       # then fill the template
git show "origin/bhavini-all-files-2026-11-12:Bhavini's files/docs/facade_workflow.md"   # read PR #16 files without checking out
```

## 8. Read these when the task touches them

| Topic | File |
| --- | --- |
| Every folder | README.md |
| Agent rules | AGENTS.md |
| What was removed and why | CLEANUP.md |
| Parked features | PARKED.md |
| Annex 4 method and CAT licence | docs/ANNEX4.md |
| Licences of every source and file | docs/LICENCES.md |
| Rule-card quote corrections | docs/LAW_TEXT_CHECK.md, docs/law_check_scans/CHECK.md |
| Every published data file | docs/DATA_INVENTORY.md |
| Open questions | docs/OPEN_QUESTIONS.md |
| AI use | docs/AI_LOG.md |
| Experiments not on the site | experiments/README.md (branch `archive/experiments`) |
| Facade method | PR #16: `Bhavini's files/docs/facade_workflow.md`, `docs/handoff_bars_facade.md`, `code/src/facade/facade.py` |
