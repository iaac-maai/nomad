
## Stage 6 v2 — better.py (before / after)
`better.improve(...)` tries the shop as it is, then adds light patios (square, or a cross patio across narrow deep shops)
with a 1,20 m shared corridor and back flats, one at a time, keeping a change only when more flats pass.
Rules: patio = Decret 141/2012 Annex 1 2.5.1 (3 m circle, ≥ 9 m²); corridor = CTE DB-SUA Anejo A (≥ 1,20 m).
`run_better.py` compares the first generator with Stage 6 on all 180 shops → `results/generation/stage6_*.{csv,json}`.
