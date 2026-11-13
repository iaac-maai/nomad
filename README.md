# NOMAD — empty shops into homes, Barcelona

NOMAD shows Barcelona's housing and planning teams which of the city's 6,149 empty ground-floor shops (census 2024) can legally and decently become homes, how many households that could serve, and which rule changes would open more. It is an academic, non-commercial IAAC MaAI project (2026-27) by Alvaro, Bars and Bhavini: a first check, not a licence.

## How the repo is organised
Each teammate keeps their work in their own folder with the same numbered steps (0_START_HERE.md, 1_find_the_shops … 8_report_and_city, app, lab_book, docs; each step has input/, code/, output/). At the end of the project the folders are merged step by step into one NOMAD folder. See Bhavini's files/docs/TEAM_FOLDER_GUIDE.md.

| Folder | What it holds |
| --- | --- |
| Bhavini's files/ | The team website (app/), zoning, buildings, floor-plan scenarios, city report |
| Bars's files/ | Rule cards and law texts, Annex 4 conversion groups, daylight, energy; the earlier version of the site (app/) |
| (Alvaro's folder, coming) | Facade analysis from street photos |
| docs/ | Shared: LICENCES.md (every source and its licence), AI_LOG.md (every use of AI), DATA_INVENTORY.md |
| nomad/ | Older shared scripts and local data (raw data is never in git) |

## Open the website
Python 3.10+, then in this folder:
```
python serve.py                 # the team website
python serve.py --site bars     # the earlier version
```
The team website needs its data in Bhavini's files/app/data/ (being added to the repo).

## How we work
- Start from the latest main; work on your own branch, in your own folder.
- Every change goes through a pull request that another teammate approves.
- Every new data source goes into docs/LICENCES.md before use; private or licence-restricted data (Catastro CAT file, Visor, facade photos) stays on our computers.
- Every use of AI goes into docs/AI_LOG.md (IAAC rule).
- The website is published only from main, after a merged pull request.
- API keys only in .env, never in git. The repo is private.

## Branches
main = the current work · archive/experiments = past experiments · parked/before-cleanup and parked/bhavini-v43 = earlier versions, kept untouched.