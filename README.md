# Nomad — starter kit

Can an empty building in Barcelona, especially an old factory, become homes?
This repo holds our first two experiments (studio review, Thursday 29 Oct 2026).

| Folder | What |
| --- | --- |
| `exp2_rules/` | Experiment 2 — the AI drafts rule cards from Decret 141/2012; we score grounding, agreement and accuracy |
| `exp1_daylight/` | Exp 4 (folder exp1_daylight) — shop floors simulated with Ladybug/Radiance; the XGBoost predictor was dropped |
| `data/regulations/` | Regulation PDFs |
| `outputs/` | Results for the slides |
| `docs/AI_LOG.md` | AI use log (IAAC rule) |

## Website

Bhavini's NOMAD website: https://claude.ai/artifact/5Pu9capuBiKG5V4mYrYMY6 (private until Bhavini shares it).
The page is `Bhavini_NOMAD Files/04_Website/index.html`. Per-shop daylight will come from a grid simulation; until then
the site shows the 5 shops simulated in Radiance as validated examples. Rebuild that file from the repo root:

```bash
python tools/daylight_validated.py   # exp1_daylight/results_shops.csv -> Bhavini_NOMAD Files/04_Website/data/daylight_validated.json
```

## Setup (once)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Mac:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env   -> then paste your API key
python check_setup.py
```

## Experiment 2 — rule cards

```bash
python exp2_rules/draft_cards.py --only Q01   # first test, one question
python exp2_rules/draft_cards.py              # all 10 questions x 5 runs
# fill exp2_rules/gold_cards.csv by hand from the PDF
python exp2_rules/score_cards.py              # -> outputs/exp2_summary.md
```

## Exp 4 (folder exp1_daylight) — daylight simulations

```bash
python exp1_daylight/make_variants.py         # -> exp1_daylight/variants.csv (50 variants)
# Grasshopper: gh_read_variant.py -> Honeybee daylight factor -> gh_record_result.py
```

The XGBoost predictor (train_daylight.py, predict_shops.py) was tried and dropped; it stays in git history.

API keys live only in `.env`, which never goes to GitHub.
