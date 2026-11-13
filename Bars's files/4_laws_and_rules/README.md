# 4 · Laws and rules

- **Input:** official law PDFs kept locally under ignored `nomad/02_Code/data/`; pinned versions are recorded in `input/rulebook/sources.lock.json`.
- **Code:** scripts in `code/` build and verify the rule cards.
- **Output:** checked `rules.json` and `annex4.json` in `output/rules/`; `annex4_cards.py` also refreshes `app/data/nomad.json`.
- **Used by:** Bars's previous site. Run `python "Bars's files/4_laws_and_rules/code/check_quotes.py"` from repo root to verify quotes.
