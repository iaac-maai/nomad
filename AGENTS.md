# AGENTS.md — Nomad

## Current team layout
The personal team folders are `Bhavini's files/` (official website at `Bhavini's files/app/`) and `Bars's files/`.
Do not edit Bhavini's folder when working on Bars's branch. Bars's checked rule cards are in
`Bars's files/4_laws_and_rules/output/rules/`; his former site is in `Bars's files/app/`. Run the official site with
`python serve.py --site bhavini` (the default), or Bars's previous site with `python serve.py --site bars`.
Use each step's README for its current input, code, and output paths; older path references below describe the prior layout.

Context for AI coding assistants (Claude Code, Copilot, Cursor) working in this repo.

## What Nomad is
Nomad answers one question for an empty building in Barcelona, starting with empty ground-floor shops (locals):
can its zone take homes, how risky is it, and which laws decide it (Decret 141/2012, the CTE, the PGM and Barcelona's
rules)? The website is the product: `python serve.py` opens it. README.md has the map of every folder.

## What is on main and what is not
- `main`: shared pipeline files and both team folders. The personal files use `Bhavini's files/` and `Bars's files/`;
  see the current team layout above. Older path references in this file describe the pre-reorganization layout.
- `parked/before-cleanup`: the parked website features (layout engine, weights, plan upload, Ask NOMAD). See Bars's files/docs/PARKED.md.
- `archive/experiments`: every experiment not used by the site (Exp 2/3 rule-card drafting, Bhavini's lab book E01–E32,
  Rhino/Grasshopper, results). See Bars's files/lab_book/README.md.
- `parked/bhavini-v43`: Bhavini's site versions v41–v43, untouched.

## Rule card format
Rule cards live in `Bars's files/4_laws_and_rules/output/rules/rules.json` (the site reads a copy in
`Bars's files/app/data/nomad.json`). Each card has a value, the article, and the exact sentence of the law (`quote`) in its
original language, plus how that sentence was checked (`checked`). Run
`python "Bars's files/4_laws_and_rules/code/check_quotes.py"` to check Bars's cards.

## Rules for agents
- Never put API keys in code, notebooks, .gh files or commits. Read them from `.env` (never committed).
- Never invent regulation values. A value without an exact quote from the official text is not a card.
- Never use OCR text as a quote without checking it against the official page.
- Do not commit the law PDFs, the built rulebook pages or `data/ESP_CT_Barcelona.081800_TMYx/` (see .gitignore).
- Keep scripts runnable from the repo root.
- Log AI-assisted work in `docs/AI_LOG.md`.
- Shop conversions fall under Decret 141/2012 Annex 4, Group C (minimum ceiling height 2,40 m).
- Bars's law versions are pinned in `Bars's files/4_laws_and_rules/input/rulebook/sources.lock.json`. Never edit it by hand; run
  `python "Bars's files/4_laws_and_rules/code/get_rulebook.py" --check`, show the person the changed articles, and run `--accept` only when they agree.
- **Standing rule: publish the website only from `main`, only after a PR is merged**, and only to
  https://claude.ai/artifact/MBLnc4q9R1XusSQQyjkvYX (never to Bhavini's or anyone else's artifact).
