# src — code, one folder per stage

| Folder | Stage | What |
|---|---|---|
| collect/ | 1 Rulebook | download and cut every law into pieces; build_rulebook.py merges them |
| sim/ | 3 Rules | unit_mix.py: the rules with citations + the unit-mix calculator (used by Grasshopper) |
| eval/ | 5/9 Tests | run the rules on Swiss Dwellings and ResPlan |
| generate/ | 6 New plans | clean_dataset.py (shops), learn_room_programs.py (sizes), layout.py (the generator, also used by Grasshopper), run_generation.py (test on 180 shops), draw_samples.py |
| building/ | 4 Read a plan | read_plan.py (image/PDF -> outline, façade, scale), render_test_plans.py + eval_read_plan.py (test on 180 plans with known answers), read_plan_image.py (first test) |
| rhino/ | 7 3D | build_nomad.py (makes NOMAD.gh/NOMAD.3dm), open_nomad.py, verify_gh.py, install_plugins.py, check_licence.py; old builders in archive/ |
| app/ | 8 App | viewer.html: rulebook search |
| zoning/ | 3 Zoning | zoning.py: every empty ground-floor premises of Barcelona (census 2024) -> its MUC zone -> housing admitted? (PGM art. 225.7) |
| rules/ | 3 Rule cards | build_rules.py: the 16 rules NOMAD checks as cards (rules/rules.json), each quote checked word for word in the rulebook |
| check/ | 5 Flags | flags.py: rule cards on the plan + verdict YES / PARTLY / NO (used by Grasshopper); run_flags.py on every shop |
| model3d/ | 7 Export | export_ifc.py: each layout's walls model as IFC (IfcOpenShell) and glTF (trimesh), same geometry as Rhino |
| eval/ (also) | 9 Evaluation | run_golden.py: NOMAD scored on eval/golden_set.csv (16 questions) + keyword search of the rulebook |
| kb/ iterate/ | 2, 6 | empty: rulebook search is the team's Exp 2 (open-notebook) + src/app/viewer.html; Stage 6 lives in generate/ |
