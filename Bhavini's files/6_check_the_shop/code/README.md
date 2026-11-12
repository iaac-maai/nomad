# 6_check_the_shop/code — Stage 5: flags on the plan

`flags.py` (plain Python; runs in Grasshopper and Python 3): rule cards (OK / FAIL, value, limit, article, point on the
plan), the verdict YES / PARTLY / NO, the "flats inside the shop" geometry check, and daylight bands
(lit ≤ 5,5 m from a window = design assumption, not a law; service +2,2 m; dark beyond).
Drawn in Rhino by `rhino_grasshopper/code/nomad_sheet.py`; used by NOMAD.gh through `rhino_grasshopper/code/nomad_core.py`.
