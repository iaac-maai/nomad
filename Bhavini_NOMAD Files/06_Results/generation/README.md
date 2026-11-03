# results/generation — the floor-plan generator

- room_programs.json: room sizes learned from 13,444 Swiss flats that pass all 9 rules (median = typical, 25th percentile = compact)
- proposals.csv: every shop x unit mix x room size: placed, passing, works, why not
- summary.json: totals per unit mix
- sample_plans.json / sample_plans.png: generated plans (top view: grey = shop, colours = rooms, blue = façade)
Made by src/generate/learn_room_programs.py, run_generation.py, draw_samples.py
