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
| National laws (BOE API) | `src/collect/fetch_national.py` | `data/national/boe_chunks.jsonl` |
| CTE technical books (PDF) | `src/collect/fetch_cte_db.py` (~10 min) | `data/national/cte_db_chunks.jsonl` |
| Catalonia (Portal Jurídic consolidated PDFs, circulars) | `src/collect/fetch_catalonia.py` | `data/catalonia/catalonia_chunks.jsonl` |
| PGM scans → OCR | `src/collect/ocr_pgm.py` (Tesseract cat+spa) | `data/pgm/raw/*.ocr.pdf`, `*.columns.txt` |
| PGM, OME, rehab ordinance | `src/collect/fetch_pgm.py` | `data/pgm/pgm_chunks.jsonl` |
| Barcelona guide | `src/collect/fetch_bcn_guide.py` | `data/barcelona/bcn_guide_chunks.jsonl` |
| **Merge into one rulebook** | `src/collect/build_rulebook.py` | `data/rulebook.jsonl`, `data/rulebook_summary.csv` |

See it: start the `nomad-rulebook` preview and open `http://localhost:8765/src/app/viewer.html`.

## 2. Rules in code (first rule cards, hand-made)
`src/sim/unit_mix.py` — every number with its citation (Decret 141/2012 Annex 1 3.1, 3.5, 3.6.2, 3.8, 3.9.1;
art. 4; MPGM 2004 Barcelona DA1 and art. 318). Runs in Python 3 and in Grasshopper (IronPython 2.7).
Stage 3 will generate these rule cards automatically from the rulebook and check them against the quote.

## 3. Grasshopper (Rhino 7)
| File | What it does | Rebuild with |
|---|---|---|
| `grasshopper/nomad_unit_mix.gh` | Sliders: built area, floors, façade length, efficiency, floor height, share and area of studio/1/2/3-bed. Output: how many dwellings fit, the limiting rule, coloured 3D boxes (red = a rule fails), report with citations | `_-RunPythonScript C:\Bhavini\AI\ADs\nomad\src\rhino\build_gh.py` |
| `grasshopper/nomad_dataset_viewer.gh` | Slider 0–299 picks a real tested floor plan; rooms green/red, panel with the 9 rule results | `_-RunPythonScript C:\Bhavini\AI\ADs\nomad\src\rhino\build_gh_viewer.py` |

Check both files without opening them: `Rhino.exe /nosplash /runscript="_-RunPythonScript C:\Bhavini\AI\ADs\nomad\src\rhino\verify_gh.py"`
→ `grasshopper/verify_log.txt`.

Connection to Rhino: one-shot scripts run by Rhino itself (`/runscript`). A live socket bridge
(as in GitHub's rhino-mcp projects) was not installed: it would let any local program run code inside Rhino.

## 4. Test dataset
Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0): 46,937 apartments + 341 commercial units, 442,019 rooms,
walls, doors and windows in metres. `data/datasets/swiss_dwellings/`.

| Step | Script | Output |
|---|---|---|
| Check 9 rules per unit (geometry with shapely) | `src/eval/check_swiss_dwellings.py` (~5 min) | `results/rule_tests/sd_units.csv`, `sd_rooms.csv`, `sd_summary.json`, `sd_sample.json` |
| Analysis | `src/eval/analyse_swiss_dwellings.py` | `results/rule_tests/analysis.md` |

## 5. Next (not started)
- Stage 2 search (meaning-based) over `data/rulebook.jsonl`.
- Stage 3 rule cards generated from the rulebook (replace the hand-made numbers in `unit_mix.py`).
- Stage 4: read a real shop floor plan (image/PDF/DXF) into the same room format the dataset uses, then Stage 5–6.
