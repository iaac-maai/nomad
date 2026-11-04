# Nomad — starter kit

Can an empty building in Barcelona, especially an old factory, become homes?
This repo holds our first two experiments (studio review, Thursday 29 Oct 2026).

| Folder | What |
| --- | --- |
| `exp2_rules/` | Experiment 2 — the AI drafts rule cards from Decret 141/2012; we score grounding, agreement and accuracy |
| `exp1_daylight/` | Exp 4 (folder exp1_daylight) — 50 factory floors simulated with Ladybug, XGBoost learns to predict daylight |
| `data/regulations/` | Regulation PDFs |
| `outputs/` | Results for the slides |
| `docs/AI_LOG.md` | AI use log (IAAC rule) |

## Website

Bhavini's NOMAD website: https://claude.ai/artifact/5Pu9capuBiKG5V4mYrYMY6 (private until Bhavini shares it).
The page is `Bhavini_NOMAD Files/04_Website/index.html`. Its daylight data (Exp 4, folder `exp1_daylight`) is
`Bhavini_NOMAD Files/04_Website/data/daylight.json`. Rebuild it after new daylight results, from the repo root:

```bash
conda activate ai-methods
python exp1_daylight/predict_shops.py                         # -> exp1_daylight/shops_bcn_pred.csv
python "Bhavini_NOMAD Files/02_Code/src/app/daylight_site.py"  # -> Bhavini_NOMAD Files/04_Website/data/daylight.json
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

## Exp 4 (folder exp1_daylight) — daylight predictor

```bash
python exp1_daylight/make_variants.py         # -> exp1_daylight/variants.csv (50 variants)
# Grasshopper: gh_read_variant.py -> Honeybee daylight factor -> gh_record_result.py
python exp1_daylight/train_daylight.py        # -> outputs/exp1_pred_vs_sim.png
```

Test the training script before Rhino is ready (fake numbers, never present them):

```bash
python exp1_daylight/fake_results.py
python exp1_daylight/train_daylight.py --results exp1_daylight/results_FAKE.csv
```

API keys live only in `.env`, which never goes to GitHub.
