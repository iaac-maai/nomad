# Experiments (archived)

The experiments that are not part of the website were moved off `main` on 10 Nov 2026. Their code, data, figures and
documents are complete on the branch **`archive/experiments`** (`git switch archive/experiments`); the parked website
features are on `parked/before-cleanup` (see `PARKED.md`). One line each:

## Team experiments

- **Exp 2/3 — rule cards drafted by AI** (`exp2_rules/`, `outputs/`, `data/regulations/`): Gemini 3.5 Flash Lite drafted 10 rule cards × 5 runs from Decret 141/2012; with vector search (open-notebook) 38/50 drafts were right, with keyword search 23/50.
- **Exp 4 — daylight predictor (XGBoost)**: learned the daylight factor from Radiance runs (R² 0.80 vs 0.65 for the rule of thumb); dropped, replaced by grid simulation. The simulation set-up itself stays on main in `exp1_daylight/`; the model's plots are in `outputs/` on the archive branch.

## Bhavini's lab book (E01–E32, `Bhavini_NOMAD Files/05_Lab_book/`)

- **E01** Collecting the law into one rulebook: one file of legal text for every later step.
- **E02** Testing 9 rules on real flats: the rules work on real data.
- **E03** Cleaning the shop dataset: the clean set of shops every later test uses.
- **E04** Learning room sizes from flats that pass: room programmes for the generator.
- **E05** First plan generator, flats along the façade: needed patios, back flats and a corridor.
- **E06** Reading a plan drawing: the plan reader v1 in Grasshopper.
- **E07** GitHub scan and a plan-reader race: kept our own reader.
- **E08** Flags on the plan, drawn in Rhino: the rule check in NOMAD.gh.
- **E09** Before and after, the smallest change that houses more flats.
- **E10** The demo in Rhino, from a commercial plan to homes.
- **E11** From zoning to walls, doors and windows in Rhino.
- **E12** Zoning, can each empty shop become housing at all: the first gate (on the website).
- **E13** Rule cards and a golden set: three checks added, 2,40 m for conversions (on the website).
- **E14** The 3D model as IFC and glTF.
- **E15** The plan reader on 398 real scanned plans (CubiCasa5K, not for commercial use): a large drop from our own drawings.
- **E16** NOMAD on Barcelona's real empty shops: real shops became the main test set.
- **E17** The website: owner mode, plan upload, three languages, report.
- **E18** Fine-tuning the plan reader on real scans: kept the published weights.
- **E19** The rulebook as one book of the official PDFs (on the website).
- **E20** The daylight model on the real empty shops (dropped with Exp 4).
- **E21** "Avoid" as an answer: the 10 % street-life cut (on the website as "keep it a shop").
- **E22** NOMAD.gh split into small components.
- **E23** Iterations as circulation strategies (Finch-style).
- **E24** What makes a flat habitable: 13,444 real plans measured.
- **E25** Real flats stretched to fit: a plan library and door clearances.
- **E26** The building's own stair, ResPlan, door swings, plan gallery and weight sliders (parked).
- **E27** A street door for every street façade, and the 25 m rule.
- **E28** Furniture, own plans, generated plans and an assistant (parked).
- **E29** No more red flats: one inside-the-shop test, smaller flats where asked ones do not fit.
- **E30** Whole buildings: empty warehouses, commercial and office buildings (zoning answer on the website).
- **E31** A second street door for deep buildings; looking for vacancy and height data.
- **E32** The 29 October crits: real daylight, liveable zones, temporary homes, city view, metropolitan area, precedents.

## Also on the archive branch

- `Bhavini_NOMAD Files/02_Code/` (all scripts except the 17 that build the website's data), `03_Rhino_Grasshopper/` (NOMAD.3dm, NOMAD.gh), `06_Results/` (all results except the 19 files the website builder reads), `08_Docs_and_research/` (research notes, licences, precedents, presentation), `01_Project_plan/`.
