# AGENTS.md — Nomad

Context for AI coding assistants (Claude Code, Copilot, Cursor) working in this repo.

## What Nomad is
Nomad answers one question for an empty building in Barcelona, especially an old factory:
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
