# AGENTS.md — Nomad

Context for AI coding assistants (Claude Code, Copilot, Cursor) working in this repo.

## What Nomad is
Nomad answers one question for an empty building in Barcelona, starting with empty ground-floor shops (locals):
can its zone take homes, how risky is it, and which laws decide it (Decret 141/2012, the CTE, the PGM and Barcelona's
rules)? The website is the product: `python serve.py` opens it. README.md has the map of every folder.

## What is on main and what is not
- `main`: the website (`Bhavini_NOMAD Files/04_Website`), the scripts that build its data, the rule cards, the
  daylight simulations (`exp1_daylight/`), and the tools in `tools/`.
- `parked/before-cleanup`: the parked website features (layout engine, weights, plan upload, Ask NOMAD). See PARKED.md.
- `archive/experiments`: every experiment not used by the site (Exp 2/3 rule-card drafting, Bhavini's lab book E01–E32,
  Rhino/Grasshopper, results). See experiments/README.md.
- `parked/bhavini-v43`: Bhavini's site versions v41–v43, untouched.

## Rule card format
Rule cards live in `Bhavini_NOMAD Files/07_Rules_and_evaluation/rules/rules.json` (the site reads a copy in
`04_Website/data/nomad.json`). Each card has a value, the article, and the exact sentence of the law (`quote`) in its
original language, plus how that sentence was checked (`checked`). `python tools/check_quotes.py` checks them again.

## Rules for agents
- Never put API keys in code, notebooks, .gh files or commits. Read them from `.env` (never committed).
- Never invent regulation values. A value without an exact quote from the official text is not a card.
- Never use OCR text as a quote without checking it against the official page.
- Do not commit the law PDFs, the built rulebook pages or `data/ESP_CT_Barcelona.081800_TMYx/` (see .gitignore).
- Keep scripts runnable from the repo root.
- Log AI-assisted work in `docs/AI_LOG.md`.
- Shop conversions fall under Decret 141/2012 Annex 4, Group C (minimum ceiling height 2,40 m).
