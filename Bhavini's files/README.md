# Bhavini's files

Everything from Bhavini's NOMAD folder (12 Nov 2026). Nothing outside this folder was changed.

| Folder | What |
|---|---|
| `code/src/` | All Python scripts, by step (zoning, building, facade, generate, library, ai, check, model3d, rhino, collect, rules, eval, book). Start with `code/src/README.md`. |
| `code/requirements.txt` | Python packages. |
| `app_site/` | The app page (`index.html`) and its Python engine for the browser (`py/src/*.txt`, `py/worker.js`). Pyodide itself and the data are not included. |
| `grasshopper/` | `NOMAD.gh` and its README. |
| `rules_and_evaluation/` | Rule cards (`rules/rules.json`, `review.json`) and the golden set (`eval/golden_set.csv`). |
| `docs/` | Pipeline (`pipeline.md`), facade method, floor-plan checklist, licences, sources, workflow, reviews, presentation, the app's README (`README_app.md`). |
| `lab_book/` | Lab book: `experiments.json`, figures, and the built book (`site/index.html`). |
| `START_HERE.md`, `CLAUDE.md` | How the project is run and the decisions made. |

Not included, because of their licences or size:

- Catastro Sede content: facade photos and the drawings made from them (E47, E48 figures), Visor 3D plans, Consulta_DNPRC units (private use only).
- The original CAT file (licence clauses 5 and 8), all raw data (`data/`) and results (`results/`).
- `rhino/NOMAD.3dm`, Python environments, and the Pyodide runtime.
