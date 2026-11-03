# NOMAD — start here

NOMAD checks whether a shop or warehouse in **Barcelona** can legally become housing,
shows the problems on the plan, and (later) suggests better plans and a 3D model.

## Where to look

| I want to… | Open |
|---|---|
| See all results at any time | **NOMAD Results** page: https://claude.ai/artifact/X6dBB65ZrzoSfFkBETmiU8 |
| **Read every experiment, with pictures** | **NOMAD Lab Book**: https://claude.ai/artifact/VKhGfPuyE3X5FdMKRUiQDa (source: `book/`) |
| **Tomorrow's demo** (stages 4-7, five shops) | Lab book entry E10, or the boards `results/sheets/D*_board.png`; in Rhino: layer *06 NOMAD experiments* in NOMAD.3dm |
| What is missing, wrong or was fixed | `docs/audit_2026-10-28.md` |
| See which GitHub code we checked and use | `docs/github_repos.csv` |
| Search the rulebook | Start the `nomad-rulebook` preview, open http://localhost:8765/src/app/viewer.html |
| **Work in Rhino (read a plan, choose flats, see 3D)** | Double-click **`OPEN_NOMAD.cmd`** → opens `rhino/NOMAD.3dm` + `grasshopper/NOMAD.gh` (the only files to use; how-to in `grasshopper/README.md`) |
| How well the plan reader works | `results/plan_reading/eval_summary.json` |
| Read the test results as text | `results/rule_tests/analysis.md` |
| Know where every law came from | `docs/sources.md` · licences in `docs/licences.md` |
| See how everything connects | `docs/workflow.md` |

## Folders

| Folder | What is in it |
|---|---|
| `data/` | **Inputs.** The laws (one folder per level) and the one rulebook `data/rulebook.jsonl`; test datasets in `data/datasets/` |
| `results/` | **Outputs.** Rule tests on real plans, plan-reading tests, the data behind the results page |
| `rhino/` | NOMAD.3dm — the one Rhino file |
| `grasshopper/` | NOMAD.gh — the one Grasshopper file (old ones in archive/) |
| `src/` | The code, one folder per stage (`collect` = rulebook, `sim` = rules, `eval` = tests, `rhino` = Grasshopper, `building` = read a plan, `app` = viewer) |
| `external/` | Projects copied from GitHub (not ours; read their licences) |
| `tools/` | Helper files: OCR language data, Rhino plug-in packages |
| `book/` | The lab book: `experiments.json` (one entry per experiment), `figures/`, and the built page in `site/` |
| `docs/` | Sources, licences, workflow, download checklist |
| `logs/` | Run logs (only for fixing problems) |
| `rules/`, `eval/` | Placeholders for Stage 3 rule cards and Stage 9 golden set |
| `CLAUDE.md` | The project plan and decisions, for Claude |
