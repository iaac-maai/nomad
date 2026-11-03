# Bhavini — NOMAD files

Bhavini's part of NOMAD (IAAC MaAI 2026, team Bhavini · Alvaro · Bars): the tool that checks whether an empty shop,
warehouse or office building in Barcelona can legally become decent homes, draws the homes that fit with real plans,
and builds them in 3D. Snapshot of 3 Nov 2026 (lab book up to E32).

## Live pages
- Website (check an address, design homes, the city view): https://claude.ai/artifact/5Pu9capuBiKG5V4mYrYMY6
- Lab book (every experiment, E01–E32): https://claude.ai/artifact/VKhGfPuyE3X5FdMKRUiQDa
- Results page: https://claude.ai/artifact/X6dBB65ZrzoSfFkBETmiU8
- Presentation: https://claude.ai/artifact/Mst5mggJ5Hzk8ws2NX3ieb
These are private until Bhavini shares them.

## Folders
| Folder | What is in it |
|---|---|
| `01_Project_plan` | `CLAUDE.md`: the project plan and the log of every decision (read this first), `README.md`, `START_HERE.md` |
| `02_Code` | `src/`, by step: `collect` (laws), `rulebook`, `rules`, `zoning`, `building` (plan reader, Catastro), `check` (rule cards, avoid, city runs), `daylight` (Bars's model on our shops), `library` (real plans), `learn`, `generate` (plan generator, furniture, whole buildings, shared homes), `ai` (plan AI, in training), `model3d` (IFC, glTF), `rhino` (Rhino + Grasshopper), `app` (website builder), `book`, `eval`; `examples/` (a DXF to add your own plan); `requirements.txt` |
| `03_Rhino_Grasshopper` | `NOMAD.3dm` (all experiments and demos D0–D6) and `NOMAD.gh` (10 small components); `OPEN_NOMAD.cmd` opens both |
| `04_Website` | the website page and its Python engine (the same code as Rhino, run in the browser) |
| `05_Lab_book` | `experiments.json` (E01–E32), all figures, the built page |
| `06_Results` | results of every step: zoning, real shops, daylight, avoid, library, generation, warehouses, city, 3D models, demo boards |
| `07_Rules_and_evaluation` | the 16 rule cards (each quote checked in the law) and the golden set |
| `08_Docs_and_research` | licences, sources, reviews and crits, precedents, habitability rules, proposals, datasets, past decks |

## What is not here
Downloaded datasets (Swiss Dwellings, ResPlan, CubiCasa5K, Catastro, census, zoning), the official law PDFs and the
compiled rulebook (public, but large: re-downloaded by `02_Code/src/collect`), other people's repositories, and files
over 3 MB except the Rhino model. Paths inside the code point to the project folder `C:\Bhavini\AI\ADs\nomad`.

## Licences
See `08_Docs_and_research/licences.md`. Datasets: Swiss Dwellings and ResPlan (CC BY 4.0), Open Data BCN (CC BY 4.0),
Catastro (reuse with attribution), MUC zoning (Generalitat). Bars's daylight results are used with his agreement.
