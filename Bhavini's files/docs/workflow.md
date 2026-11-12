# Nomad workflow (as built on 2026-10-28)

```
official sources ──► collect scripts ──► one rulebook ──► rules in code ──► Grasshopper (sliders, 3D)
                                             │                  │
                                             ▼                  ▼
                                    viewer (search)    test on 46,937 real plans ──► analysis
```

## 1. Rulebook (Stage 1)
| Step | Script | Output |
|---|---|---|
| National laws (BOE API) | `4_laws_and_rules/code/fetch_national.py` | `4_laws_and_rules/input/national/boe_chunks.jsonl` |
| CTE technical books (PDF) | `4_laws_and_rules/code/fetch_cte_db.py` (~10 min) | `4_laws_and_rules/input/national/cte_db_chunks.jsonl` |
| Catalonia (Portal Jurídic consolidated PDFs, circulars) | `4_laws_and_rules/code/fetch_catalonia.py` | `4_laws_and_rules/input/catalonia/catalonia_chunks.jsonl` |
| PGM scans → OCR | `4_laws_and_rules/code/ocr_pgm.py` (Tesseract cat+spa) | `4_laws_and_rules/input/pgm/raw/*.ocr.pdf`, `*.columns.txt` |
| PGM, OME, rehab ordinance | `4_laws_and_rules/code/fetch_pgm.py` | `4_laws_and_rules/input/pgm/pgm_chunks.jsonl` |
| Barcelona guide | `4_laws_and_rules/code/fetch_bcn_guide.py` | `4_laws_and_rules/input/barcelona_guide/bcn_guide_chunks.jsonl` |
| **Merge into one rulebook** | `4_laws_and_rules/code/build_rulebook.py` | `4_laws_and_rules/output/rulebook.jsonl`, `4_laws_and_rules/output/rulebook_summary.csv` |

See it: start the `nomad-rulebook` preview and open `http://localhost:8765/src/app/viewer.html`.

## 2. Rules in code (first rule cards, hand-made)
`7_floor_plans/code/unit_mix.py` — every number with its citation (Decret 141/2012 Annex 1 3.1, 3.5, 3.6.2, 3.8, 3.9.1;
art. 4; MPGM 2004 Barcelona DA1 and art. 318). Runs in Python 3 and in Grasshopper (IronPython 2.7).
Stage 3 will generate these rule cards automatically from the rulebook and check them against the quote.

## 3. Grasshopper (Rhino 7)
| File | What it does | Rebuild with |
|---|---|---|
| `rhino_grasshopper/nomad_unit_mix.gh` | Sliders: built area, floors, façade length, efficiency, floor height, share and area of studio/1/2/3-bed. Output: how many dwellings fit, the limiting rule, coloured 3D boxes (red = a rule fails), report with citations | `_-RunPythonScript C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code\build_gh.py` |
| `rhino_grasshopper/nomad_dataset_viewer.gh` | Slider 0–299 picks a real tested floor plan; rooms green/red, panel with the 9 rule results | `_-RunPythonScript C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code\build_gh_viewer.py` |

Check both files without opening them: `Rhino.exe /nosplash /runscript="_-RunPythonScript C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code\verify_gh.py"`
→ `rhino_grasshopper/verify_log.txt`.

Connection to Rhino: one-shot scripts run by Rhino itself (`/runscript`). A live socket bridge
(as in GitHub's rhino-mcp projects) was not installed: it would let any local program run code inside Rhino.

## 4. Test dataset
Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0): 46,937 apartments + 341 commercial units, 442,019 rooms,
walls, doors and windows in metres. `7_floor_plans/input/datasets/swiss_dwellings/`.

| Step | Script | Output |
|---|---|---|
| Check 9 rules per unit (geometry with shapely) | `7_floor_plans/code/check_swiss_dwellings.py` (~5 min) | `4_laws_and_rules/output/rule_tests/sd_units.csv`, `sd_rooms.csv`, `sd_summary.json`, `sd_sample.json` |
| Analysis | `7_floor_plans/code/analyse_swiss_dwellings.py` | `4_laws_and_rules/output/rule_tests/analysis.md` |

## 5. Next (not started)
- Stage 2 search (meaning-based) over `4_laws_and_rules/output/rulebook.jsonl`.
- Stage 3 rule cards generated from the rulebook (replace the hand-made numbers in `unit_mix.py`).
- Stage 4: read a real shop floor plan (image/PDF/DXF) into the same room format the dataset uses, then Stage 5–6.
