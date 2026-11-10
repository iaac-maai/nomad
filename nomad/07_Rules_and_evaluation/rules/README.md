# rules — Stage 3 rule cards

`rules.json`: the 16 rules NOMAD checks, each with its value, unit, article, link and the exact sentence of the official text (`quote`).
Built by `src/rules/build_rules.py`, which checks that every quote is word for word in `data/rulebook.jsonl` and that the number is in the quote.
`review.json`: cards that failed a check (today: the CTE corridor width, whose PDF table was garbled) — a person checks them against the PDF.
