# AGENTS.md — Nomad

Context for AI coding assistants (Claude Code, Copilot, Cursor) working in this repo.

## What Nomad is
Nomad answers one question for an empty building in Barcelona, starting with empty ground-floor shops (locals):
can it become homes, how many, and what is the smallest change (new windows, a courtyard,
a mezzanine) that makes it legal under Decret 141/2012, the CTE and Barcelona rules?

## Architecture (phase 1)
- **Law side (once per law version):** regulation PDFs -> LLM + RAG (open-notebook + Claude/Gemini)
  -> draft rule cards (JSON) -> trust layer (grounding checks, 5-run agreement, classifier)
  -> expert approves weak cards -> approved card library in git.
- **Building side (every address):** building data (OSM, Open Data BCN, ICAEN) -> Grasshopper
  via Rhino.Compute (light band, homes, option generators) -> daylight ML model + NSGA-II Pareto
  -> Python applies approved cards -> PASS / FAIL / MANUAL + modified 3D + one-page report.
- The building side never calls an LLM: the same building must always get the same answer.

## Folders
- `exp2_rules/` — experiment 2: draft rule cards with an LLM and score them against gold cards.
- `exp1_daylight/` — experiment 1: daylight-factor dataset from Ladybug/Honeybee + XGBoost.
- `data/regulations/` — regulation PDFs (public law texts).
- `outputs/` — results (CSV, PNG, Markdown summaries).
- `docs/AI_LOG.md` — every AI tool use (IAAC rule).

## Rule card format
```json
{"check": "fits_circle", "value": 2.8, "unit": "m", "quote": "...", "page": 12, "applies_to": "living-dining-kitchen"}
```
Allowed checks: min_area, fits_circle, fits_square, min_length, min_height, min_ratio, max_count, flag_is.
Ratios are decimals (1/8 -> 0.125). Quotes are copied word for word in the original language.

## Rules for agents
- Never put API keys in code, notebooks, .gh files or commits. Read them from `.env`.
- Never invent regulation values. A value without an exact quote is not a card.
- Keep scripts runnable from the repo root: `python exp2_rules/draft_cards.py`.
- Log AI-assisted work in `docs/AI_LOG.md`.

## How to run the experiments
1. `conda activate ai-methods`, then `python check_setup.py` (all lines OK).
2. Experiment 2 (rule cards):
   - `python exp2_rules/draft_cards.py --fresh` (keyword search, `RETRIEVAL=pdf` in `.env`)
   - `python exp2_rules/score_cards.py` (needs `exp2_rules/gold_cards.csv`)
   - Vector search: start open-notebook (`docker compose up -d` in its folder), set `RETRIEVAL=notebook`, open a new terminal, run the two commands again.
   - Results so far: keyword 23/50 drafts correct, vector 38/50 (`outputs/run_pdf`, `outputs/run_notebook`).
3. Experiment 1 (daylight):
   - `python exp1_daylight/make_variants.py` (50 shop variants)
   - Rhino 8 + `exp1_daylight/daylight_v0.3dm` + `daylight_v0.gh`, both toggles True, animate the slider 0-49
   - `python exp1_daylight/train_daylight.py` (XGBoost R2 0.80 vs rule 0.65)
- Shop conversions fall under Decret 141/2012 Annex 4, Group C (minimum ceiling height 2.40 m).