# NOMAD — Kickoff prompt for Claude Code

You are joining an existing project. Read this whole prompt first. Your FIRST action: save this entire prompt as `CLAUDE.md` in the repository root, so it is your project memory for every future session.

---

## 1. Who I am and how to work with me

- I am Bhavini, an architect (founder of AWE Studio) doing the Master in AI for Architecture at IAAC Barcelona. Teammates: Alvaro and Bars.
- I am learning Python (DataCamp + IAAC notebooks: pandas, requests, scikit-learn, XGBoost). Explain code in simple language, using those same terms.
- Work **one stage at a time, one small step at a time**. After each step: run it, show me the result (counts, a sample, a screenshot path), and STOP for my "go ahead" before the next step.
- Do not change the plan below. If something is technically impossible, say so in one line and propose the closest working option.
- Never invent legal numbers, article numbers, URLs or IDs. Every rule must come from a downloaded official text with its source link. If you cannot verify a URL, tell me and stop.
- Note the licence of every repo/dataset you use in `docs/licences.md`.

## 2. What Nomad is

Nomad is an AI tool that checks whether an existing non-residential space (first case: ground-floor commercial premises / "locales", also warehouses) in **Barcelona** can legally become housing, flags the problems on the 2D plan, generates 3–4 improved 2D plan iterations, and builds a 3D model of the chosen one.

Scope for this phase: **Barcelona only**.

Regulation levels (in this order):
1. National (Spain)
2. Catalonia (regional)
3. Metropolitan plan — PGM (Pla General Metropolità)
4. Barcelona city ordinances + district / special plans

Our differentiator: daylight and ventilation (window openings, façade, street) are checked properly — existing feasibility tools ignore them.

## 3. The full pipeline (stages)

| Stage | Name | Input | Output |
|---|---|---|---|
| 0 | Repo setup | — | folders, venv, requirements, CLAUDE.md |
| 1 | Collect regulations | official sources | `data/<level>/chunks.jsonl` (one line per article) |
| 2 | Knowledge base (RAG) | all chunks | searchable vector database with citations |
| 3 | Rule cards | retrieved articles | `rules/rules.json` (machine-checkable rules) |
| 4 | Building input | client documents, floor plan (PDF/image/DXF), address | `building.json` (rooms, areas, heights, walls, doors, windows, façade, street) |
| 5 | Compliance check + flags on plan | rules + building.json | pass/fail per room/rule with margin + citation; flagged 2D plan (SVG/PNG) |
| 6 | 2D iterations | flagged plan + rules | 3–4 alternative 2D plans, each re-checked, with pros/cons and a recommended one |
| 7 | 3D | chosen 2D plan | IFC file (IfcOpenShell) + glTF for a web viewer |
| 8 | Web app | everything | standalone web app: upload → report → flags → iterations → 3D |
| 9 | Evaluation | golden set | accuracy of answers and citations |

We start with **Stage 0 and Stage 1**. Do not start later stages until I say so.

## 4. Folder structure

```
nomad/
  CLAUDE.md
  requirements.txt
  data/
    national/   catalonia/   pgm/   barcelona/      # raw files + chunks.jsonl per level
  src/
    collect/    # stage 1 scripts (one per source)
    kb/         # stage 2
    rules/      # stage 3
    building/   # stage 4
    check/      # stage 5
    iterate/    # stage 6
    model3d/    # stage 7
    app/        # stage 8
  rules/rules.json
  eval/golden_set.csv
  docs/sources.md   docs/licences.md
```

## 5. Shared data format — every regulation chunk (all levels)

One JSON object per line in `chunks.jsonl`:

```json
{
  "norm_id": "BOE-A-2006-5515",
  "norm": "CTE",
  "level": "national | catalonia | pgm | barcelona",
  "block_id": "a12",
  "block_type": "precepto",
  "title": "Artículo 12",
  "in_force_from": "20191227",
  "source_url": "https://...",
  "text": "full article text"
}
```

Keep only the **current (in force) wording**. Keep tables as text rows (`cell | cell`).

## 6. Stage 1 — Collect regulations (detailed steps)

### Step 1a — National laws via the official BOE API (script below, already written and parser-tested)

- API: `https://www.boe.es/datosabiertos/api/legislacion-consolidada` — no key. `Accept: application/json` for metadata/index, `application/xml` for full text.
- Endpoints: `/id/{id}/metadatos`, `/id/{id}/texto`, `/id/{id}/texto/indice`, `/id/{id}/texto/bloque/{id_bloque}`.
- XML: `<bloque id tipo titulo>` → `<version fecha_vigencia>` → `<p>`, `<table>`. Last `<version>` = current wording.
- Laws (IDs verified on boe.es):

| Short | ID | What |
|---|---|---|
| CTE | BOE-A-2006-5515 | Technical Building Code (Part I) |
| LOE | BOE-A-1999-21567 | Building Act |
| TRLSRU | BOE-A-2015-11723 | Land and Urban Rehabilitation law |
| LDV | BOE-A-2023-12203 | Right to Housing law 2023 |
| LPH | BOE-A-1960-10906 | Horizontal Property (apartment owners) law |

Save the script as `src/collect/fetch_national.py`, run it, show me `data/national/summary.csv` and 3 sample chunks.

```python
"""Nomad - Step 1a: download Spain's national laws from the BOE open-data API
and split them into article chunks for RAG."""
import json, os, time
import xml.etree.ElementTree as ET
import requests
import pandas as pd

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
OUT = "data/national"

NORMS = [
    {"id": "BOE-A-2006-5515",  "short": "CTE",    "why": "Technical building code (Part I)"},
    {"id": "BOE-A-1999-21567", "short": "LOE",    "why": "Building Act"},
    {"id": "BOE-A-2015-11723", "short": "TRLSRU", "why": "Land & urban rehabilitation law"},
    {"id": "BOE-A-2023-12203", "short": "LDV",    "why": "Right to Housing law 2023"},
    {"id": "BOE-A-1960-10906", "short": "LPH",    "why": "Horizontal Property law"},
]

def get_json(url):
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()

def get_xml(url):
    r = requests.get(url, headers={"Accept": "application/xml"}, timeout=120)
    r.raise_for_status()
    return r.text

def xml_to_chunks(xml_text, norm):
    root = ET.fromstring(xml_text)
    chunks = []
    for b in root.iter("bloque"):
        versions = b.findall("version")
        if not versions:
            continue
        v = versions[-1]
        parts = []
        for el in v:
            if el.tag == "p":
                parts.append("".join(el.itertext()).strip())
            elif el.tag == "table":
                for tr in el.iter("tr"):
                    cells = [" ".join(td.itertext()).strip() for td in tr]
                    parts.append(" | ".join(cells))
        text = "\n".join(p for p in parts if p)
        if not text:
            continue
        chunks.append({
            "norm_id": norm["id"], "norm": norm["short"], "level": "national",
            "block_id": b.get("id"), "block_type": b.get("tipo"), "title": b.get("titulo"),
            "in_force_from": v.get("fecha_vigencia"),
            "source_url": f"https://www.boe.es/buscar/act.php?id={norm['id']}#{b.get('id')}",
            "text": text,
        })
    return chunks

def main():
    os.makedirs(OUT, exist_ok=True)
    all_chunks, rows = [], []
    for n in NORMS:
        print("Downloading", n["short"], n["id"])
        meta = get_json(f"{API}/id/{n['id']}/metadatos")["data"]
        meta = meta[0] if isinstance(meta, list) else meta
        xml_text = get_xml(f"{API}/id/{n['id']}/texto")
        with open(f"{OUT}/{n['id']}.xml", "w", encoding="utf-8") as f:
            f.write(xml_text)
        chunks = xml_to_chunks(xml_text, n)
        all_chunks += chunks
        rows.append({"id": n["id"], "short": n["short"], "title": meta.get("titulo"),
                     "last_update": meta.get("fecha_actualizacion"),
                     "articles": len(chunks), "why": n["why"]})
        time.sleep(1)
    with open(f"{OUT}/chunks.jsonl", "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/summary.csv", index=False)
    print(df[["short", "articles", "last_update"]])
    print("Total chunks:", len(all_chunks))

if __name__ == "__main__":
    main()
```

### Step 1b — CTE technical documents (the actual numbers)
- Source: https://www.codigotecnico.org/DocumentosCTE/DocumentosCTE.html (official). Download only the latest PDFs of: **DB-HS** (health — HS3 indoor air quality/ventilation), **DB-SUA** (safety of use & accessibility), **DB-SI** (fire safety), **DB-HR** (noise), **DB-HE** (energy). Find the exact PDF links on that page; do not guess them.
- Extract text with PyMuPDF (`fitz`) or pdfplumber; split by section number (e.g. "3.1.1"); keep tables. Same chunk format, `level: "national"`, `norm: "CTE-DB-HS"` etc.

### Step 1c — Catalonia
- **Decret 141/2012** (habitability conditions of dwellings — minimum areas, heights, lighting, ventilation). Get the consolidated official text (Portal Jurídic de Catalunya / DOGC). Annex 1 holds the numbers. Note: dwellings created by change of use must meet the NEW-dwelling level (Art. 1).
- Also check for Catalan circulars that interpret it (e.g. Agència de l'Habitatge circulars on lighting/ventilation, such as Circular 10-2025 on direct light).
- Add other Catalan laws only if they contain rules for change of use to housing; list candidates for me before downloading.

### Step 1d — PGM (Metropolitan plan)
- PGM normes urbanístiques (AMB). Mostly PDFs → download, extract, chunk by article. Find official links via AMB / Ajuntament de Barcelona urbanism pages; show me the links first.

### Step 1e — Barcelona ordinances + district/special plans
- Identify Barcelona municipal ordinances that apply to building / change of use of "locales" to housing. Show me the list with official links before downloading.
- Barcelona urban information per address: https://ajuntament.barcelona.cat/informaciourbanistica/cerca/en — investigate whether it has an API or downloadable data giving the zoning/qualification of a given address. Report back; do not scrape it blindly.

### Scraping rule
- Prefer official APIs and official PDFs. Use **Crawl4AI** (Apache 2.0, `pip install -U crawl4ai`, `crawl4ai-setup`) only for HTML pages without an API, on an explicit list of URLs (no whole-site crawling). Respect robots.txt, add delays, store the date of download.

## 7. Later stages (do NOT start yet — for context)

**Stage 2 — Knowledge base:** embed chunks (multilingual model; texts are Spanish and Catalan), store in Chroma (or use our Open Notebook fork — lfnovo/open-notebook — via its REST API). Search filtered by `level`. Every answer must quote `norm` + `title` + `source_url`.

**Stage 3 — Rule cards:** LLM turns articles into JSON rules:
```json
{"rule_id": "CAT-141-2012-light-01", "level": "catalonia", "applies_to": "bedroom",
 "parameter": "window_area / floor_area", "operator": ">=", "value": null, "unit": "ratio",
 "source": {"norm": "Decret 141/2012", "article": "Annex 1 ...", "url": "..."},
 "quote": "exact sentence from the text", "confidence": 0.0}
```
Automatic self-checks: (1) JSON schema valid (pydantic), (2) the number in `value` appears in `quote` and `quote` appears in the source chunk, (3) run extraction 5 times → agreement rate = confidence, (4) accuracy on `eval/golden_set.csv`. Rules with confidence < 0.8 go to a review list.

**Stage 4 — Building input:**
- Floor plan image → walls / doors / windows: **Yytsi/floorplan-to-3d** (MIT; UNet-ResNet34 trained on CubiCasa5K; weights on Hugging Face `Yytsi/floorplan-to-3d-walls`; runs on CPU).
- Floor plan image → room polygons with labels: **Cornell-VAILab/Raster2Seq** (MIT; weights `haopt/Raster2Seq`).
- CAD-style drawings / symbols: **FloorPlanCAD** dataset (check licence: card says CC BY-NC 4.0).
- Building/parcel data from address when needed: **BeeGroup-cimne/hypercadaster_ES** (EUPL-1.2; Spanish cadastre + census + OSM + Barcelona commercial premises data).
- Output `building.json`: rooms (polygon, area, height, use), walls, doors, windows (width, height, sill, façade side), façade length, street width.

**Stage 5 — Check + flags:** run rules.json on building.json with shapely geometry; for each room/rule: pass/fail, margin = actual ÷ required, citation. Draw flags on the 2D plan (SVG): red = fail, amber = margin < 1.1, green = pass, with the reason text.

**Stage 6 — 2D iterations:** generate 3–4 alternative layouts inside the existing shell that fix the flags. Approach: constraint optimisation with Google OR-Tools CP-SAT (see github.com/poolpet/floorplan6 — AGPL-3.0, use as reference only, do not copy code). Reference for learned generation: HanHan55/Graph2plan, m-agour/ResPlan (CC BY 4.0). Each iteration is re-checked by Stage 5; output a comparison table (units, compliance, daylight margin, pros/cons) and a recommended option.

**Stage 7 — 3D:** extrude the chosen plan (walls, openings) to IFC with IfcOpenShell and to glTF for a Three.js viewer.

**Stage 8 — Web app:** standalone (FastAPI backend + simple web frontend). Flow: upload documents + plan + address → regulations found → flagged plan → iterations → 3D.

**Stage 9 — Evaluation:** `eval/golden_set.csv` (question, building context, correct answer, source article). Report answer accuracy and citation accuracy.

## 8a. Decisions log

**2026-10-28**
- One rulebook: each collect script writes `data/<level>/<source>_chunks.jsonl`; `src/collect/build_rulebook.py` merges them into `data/<level>/chunks.jsonl` + `data/rulebook.jsonl`, splits pieces > 4000 chars into `/pN` parts, and adds `"note": "check_pdf ..."` to pieces with formulas drawn in 2D. Optional chunk fields: `part`, `note`.
- Viewer: `src/app/viewer.html` (search the rulebook, open the official source). Run the `nomad-rulebook` preview (python http.server on 127.0.0.1:8765) and open `/src/app/viewer.html`.
- Stage 8 is NOT a deployed web app: it runs on localhost for now. Presentations / PDF exports come later.
- Rhino + Grasshopper is the 3D/design front end: sliders (unit mix 1/2/3 BHK, unit areas, plot area) drive the layout live; the rulebook and the rule checks are a Python service Grasshopper calls. Plan this in Stages 5–7.
- robots.txt: portaljuridic.gencat.cat, habitatge.gencat.cat, dogc.gencat.cat and amb.cat/documents disallow all bots. Do not script downloads there; the user downloads those files by hand into `data/<level>/raw/`, or approves specific files.
- Key Barcelona source: Ajuntament guide "Informació bàsica general per a consultes sobre canvi d'ús de locals a habitatge" (2025-03) lists the rules the city checks (PGM 225.7, 236.1, 285 ter; OME 176/178/180; TRLU 108.4; Decret 141/2012; 2004 MPGM: 40 m² useful, 3 m façade).

- Catalonia: `src/collect/fetch_catalonia.py` reads consolidated PDFs from data/catalonia/raw (downloaded on the user's request from portaldogc; Python's SSL fails there, Windows curl works). Article numbers come only from PDF bold headings.
- PGM: RPUC (planejamenturbanisme.territori.gencat.cat) documents are scans → `src/collect/ocr_pgm.py` (Tesseract cat+spa, left 9% cropped for binding holes; two-column pages OCR'd per column) → `src/collect/fetch_pgm.py`. OCR cleanup must never delete letters/digits (a dropped "no" flips a rule). AMB docs server refused automated download: OME + rehab ordinances must be saved by hand.
- MPGM B1600 (2018): TSJC 6/7/2021 annulled its Disposició final segona.

- Rhino 7.1 (not 8) is installed: IronPython 2.7 in Grasshopper (no f-strings in GH code). Connection = one-shot `/runscript` scripts in `src/rhino/` (a live code-running socket was refused as unsafe). Grasshopper files in `grasshopper/`. Full workflow: `docs/workflow.md`.
- OME art. 180 (AMB compilation) says 100 m² per dwelling; Barcelona uses 80 m² (MPGM 2004 art. 318). Use 80 for Barcelona.
- Test dataset: Swiss Dwellings v3.0.0 (CC BY 4.0) in data/datasets/; window elevation there is from the building base, not the floor.

- Folders (2026-10-28): `data/` inputs, `results/` outputs (rule_tests, plan_reading, dashboard), `logs/`, `external/` cloned repos, `tools/`. Start at `START_HERE.md`. Results page: https://claude.ai/artifact/X6dBB65ZrzoSfFkBETmiU8 (update its CSVs in results/dashboard/dashboard_data when results change).
- Rhino plug-ins: install through `src/rhino/install_plugins.py` (run by Rhino; the sandboxed shell cannot write %APPDATA%). Human UI 0.8.8 loads; Magnetizing FPG 3.2.0 needs a newer Rhino 7 than 7.1.
- Decision 2026-10-28: STAY ON RHINO 7.1 (no update, no paid software). Licence: validated, does not expire, type label blank. Stage 6 floor-plan generation = our own Python generator (OR-Tools CP-SAT), shown in Grasshopper.

- Stage 6 v1 (2026-10-28): `src/generate/` — clean_dataset.py (180 of 341 Swiss commercial units kept as shells), learn_room_programs.py (room sizes from 13,444 rule-passing flats), layout.py (pure-Python generator: flats as strips along every windowed façade, light rooms front ≤5,5 m, kitchen/bath/hall behind; checks with citations), run_generation.py (best fit works in 136/180 shops, 350 flats). Grasshopper: `grasshopper/nomad_plan_generator.gh` (shop slider OR own outline curve + façade curve, unit-mix sliders, compact toggle). Known limits: deep interiors unused (median 103 m²), no patios, street entry assumed, room proportions fixed.

- ONE RHINO FILE RULE (user, 2026-10-28): the user works only in `rhino/NOMAD.3dm` + `grasshopper/NOMAD.gh`, opened with `OPEN_NOMAD.cmd`. Never create new .gh/.3dm files for the user; update NOMAD.gh with `src/rhino/build_nomad.py` (it never overwrites NOMAD.3dm). Background Rhino runs (build/verify) must close themselves; close stray Untitled Rhino windows after. Old .gh files are in grasshopper/archive.
- Stage 4 v1 (2026-10-28): `src/building/read_plan.py` (floorplan-to-3d model + dark-line walls, deskew, flood-fill outline with gap/shopfront bridging, façade = outline edges with openings, scale from known façade length). Graded on 180 rendered Swiss shop plans (`render_test_plans.py`, `eval_read_plan.py`): with scale given median IoU 0.93, area within 10% on 77%; scale estimated alone is unreliable (~54% error) → always ask for one dimension. NOMAD.gh calls it via subprocess (external/floorplan-to-3d/.venv).

- THREE STANDING RULES (user, 2026-10-28):
  1. GITHUB FIRST. Before building any stage or part, search GitHub (use `gh api search/repositories`; the GitHub MCP token is broken) for code that already does it, compare licence / last update / fit in `docs/github_repos.csv`, test the best ones on our test plans, and copy what is open source (MIT/BSD/Apache/LGPL-as-library). GPL/AGPL/no-licence repos = reference only. CC BY-NC weights are OK for the master but not a product: say so.
  2. LAB BOOK. After every experiment add an entry to `book/experiments.json` (question, what we did, result with {metric} placeholders, learned, decision, figures), run `src/book/make_figures.py` + `src/book/build_book.py`, and republish `book/site/index.html` with its figures: https://claude.ai/artifact/VKhGfPuyE3X5FdMKRUiQDa. Lots of images: charts from result files, plan pictures, 3D views.
  3. RESULTS PAGE ALWAYS CURRENT. After every outcome run `src/app/refresh_outcomes.py`, upload the changed CSVs from results/dashboard/dashboard_data to the NOMAD Results page and update the dataset docs (page source: results/dashboard/dashboard_page.html).
- GitHub scan + plan-reader race (2026-10-28): 31 repos in docs/github_repos.csv. MitUNet (external/mitunet, weights CC BY-NC, loaded with torch weights_only=True) raced vs ours on 60 clean + 60 messy plans (`make_messy_plans.py`, `eval_read_plan.py --plans --walls`): ours kept (messy: area within 10% 83% vs MitUNet 63%); dark lines alone 87% because test plans draw walls black → need real scans (CubiCasa5K) for a fair AI test. Picks: Stage 5 shapely maximum_inscribed_circle + IfcOpenShell/IfcTester; Stage 6 OR-Tools CP-SAT + Autodesk floorplate-generator method (MIT, unit mix + corridor); Stage 7 IfcOpenShell + trimesh (+ Rhino 7 glTF export, check on 7.1). Background Rhino /runscript now hangs at start (no log): Rhino book pictures not taken; 3D views drawn with matplotlib instead.

- USER RULES (2026-10-28, later): (a) GITHUB ONLY WHEN IT IS BETTER: copy code from GitHub only if it does a part better than what we have or saves us real work; take only the needed piece, never redo what we already built. (b) RHINO + GRASSHOPPER ONLY: every experiment runs in Rhino/Grasshopper (NOMAD.gh), and lab-book pictures come from Rhino (results/sheets). No Streamlit/web framework. (c) Bars owns the daylight analysis: do not refine the daylight gradient; keep it as shown. (d) Sheets: plain paper, no grid; keep gradient, labels, "How it was checked" and "Result".
- Stage 5 v1 (2026-10-28): src/check/flags.py (rule cards + verdict YES/PARTLY/NO, "flats inside the shop" geometry check, daylight bands with lit depth 5,5 m = design assumption), src/rhino/nomad_core.py (shared shop sources + run + inbox), src/rhino/nomad_sheet.py (sheet drawn on layer "05 NOMAD sheet" + PNG). NOMAD.gh has "make sheet" and "run inbox" toggles and a "verdict" output. Background Rhino: src/rhino/run_in_rhino.ps1 (types RunPythonScript into a fresh Rhino; /runscript is ignored since the D5 LiveSync plug-in). Sheets for the book: src/rhino/make_sheets.py.

- ALL RHINO EXPERIMENTS IN NOMAD.3dm (user, 2026-10-28): every sheet/experiment must end up in rhino/NOMAD.3dm (layer "06 NOMAD experiments::<name>") and stay until the user deletes it. Background runs save recipes (results/sheets/recipes/*.json); NOMAD.gh ("experiments in this file", on) draws any recipe not yet in the file. Never write NOMAD.3dm from outside while the user has it open; test on a copy (src/rhino/verify_experiments.py).
- Sheet style (user): white, no grid, no boxes around text, clean Arial text, before | after plans side by side, gradient on the plan, verdict YES/PARTLY/NO large and translucent over each plan, "How it was checked" + "Result" as plain text. Old Stage 5 sheets kept in results/sheets/stage5_v1/.
- Stage 6 v2 (2026-10-28): src/generate/better.py (as it is -> patios: square or cross patio, Decret 141/2012 Annex 1 2.5.1 = 3 m circle & >= 9 m²; shared corridor 1,20 m CTE DB-SUA Anejo A, gallery behind a cross patio; back flats; greedy, keep only if more passing flats; also tries small-flats-first). layout.generate has blocked / extra_fronts / small_first. run_better.py: 2x1+1x2 works 40 -> 43, passing flats 242 -> 257; 5x1+2x2 297 -> 337. Binding limit = street façade length (only 21/180 shops >= ~18 m deep). Next lever: new windows in blind street walls (needs cadastre wall data, hypercadaster_ES).

- Stage 7 v1 + demo (2026-10-28): src/rhino/nomad_model.py (3D of each iteration under its plan, walls cut at 1,20 m; draw_demo = story sheet + models + 3D pictures + board), nomad_core.run_story (Stage 5 flags + Stage 6 iterations: 1 as asked, 2 compact rooms, 3 most homes via better.most_homes), make_demo.py (5 shops D0-D4), run_iterations.py (180 shops: homes 257 / 292 / 455). NOMAD.gh: "make demo" toggle. Audit + fixes in docs/audit_2026-10-28.md. LESSON: the user's open Grasshopper can save its old NOMAD.gh over a rebuild - rebuild only when Rhino is closed, and check the GH script compiles (build_nomad.py now refuses to save otherwise).

- 2026-10-28 (late): COLOUR SCHEME = lab book E01 (charts: blue 2C5D8F / ochre C98A2B / green 3F8F5A / red C4473A) + E05 (rooms: living F09F26, bedrooms 8078DE/B0A8ED, kitchen FAC775, bath 85B8EB, hall CCCCCC, fails E34A4A, street facade = thick blue 2C5D8F). Defined once in src/check/flags.py (ROOM_RGB, VERDICT_RGB, band_colour = very light gradient: pale yellow -> white -> soft blue-grey, NO orange). Verdict is always written in caption text, never on a plan. Plans/3D for slides + book: src/book/draw_cases.py (from saved recipes, nothing recomputed). NOMAD.3dm records every experiment: src/rhino/record_experiments.py (layers "07 NOMAD lab book::E0x", "06 NOMAD experiments::<case>"; backup in rhino/backups). Presentation: 4 slides (9-12) by stage, built by src/app/add_deck_slides.py on the framed EXPERIMENTS V0 layout; GH screenshot by src/rhino/capture_gh.py.

- Stage 7 in two steps (user, 2026-10-28): 7.1 zoning = room blocks (nomad_model.build); 7.2 walls, doors, windows = nomad_model.build_walls (shell 30 cm, partitions 10 cm in the 20 cm gap between rooms, 2,70 m, no roof; street windows 60% x 1,5 m; 0,80 m door room->hall, 0,90 m street entry per flat; floors in E05 colours). draw_demo draws both (layers "...::3d iteration k" and "...::walls iteration k"), walls captured with a steep view (capture steep=True). Lab book E11; slide 12 fig 2 shows zoning -> walls.

- DECK IN WORKFLOW ORDER (user, 2026-10-28): slide 2 = 8 steps (1 find shops, 2 read building, 3 zoning [planned], 4 rules, 5 daylight, 6 check the shop YES/PARTLY/NO, 7 fit the homes 2D -> 3D, 8 report). Experiments numbered by step: Exp 1 plan reader (step 2, slide 3), Exp 2 rules (step 4, slides 4-6), Exp 3 daylight (step 5, slides 7-10, team), Exp 4 check + homes + 3D (steps 6-8, slides 11-12). First slide of each experiment names its step. All done by src/app/add_deck_slides.py from the team deck (update_pipeline_slide, retitle, order list).

- SPACE CLEAN-UP (user, 2026-10-29): keep only what NOMAD runs on. Deleted: swiss-dwellings zip (unpacked), ResPlan.zip, external .git folders, 3 unused MitUNet weights, Raster2Seq + Graph2plan clones, rhino/NOMAD.3dmbak, and data/pgm/raw/*.ocr.pdf (1.4 GB; their page texts are in <name>.ocr.json, which fetch_pgm.py reads instead - checked identical). Do not keep downloaded zips after unpacking; keep only the dataset split we use.

- 2026-10-29 (all stages): STEP 3 ZONING = src/zoning/zoning.py (census 2024 empty premises, Open Data BCN CC BY 4.0 + MUC "Qualificació" polygons, Generalitat, via gissrv.diba.cat ArcGIS; door points in a street polygon take the building's zone within 8 m). Gate = PGM art. 225.7 (MPGM 1999): YES zones 12/13a/13b/14b/15, CHECK 18/20/22@/14 remodelling, NO industry + systems. 5,026 of 6,149 (82 %) YES. NOMAD.gh input "address or cadastral ref" -> nomad_core.add_zoning -> Zoning card first; NO zone forces NO, CHECK caps at PARTLY. IronPython csv cannot read accents: NOMAD reads results/zoning/lookup.json.
- STAGE 3 rule cards: rules/rules.json (src/rules/build_rules.py), 16 cards, quote checked word for word in the rulebook; review list rules/review.json. STAGE 9: eval/golden_set.csv (16 Q, answers verified in source) + src/eval/run_golden.py. RULE FIXES it found: shop conversion = Decret 141/2012 Annex 4 group C -> clear height 2,40 m (flags.MIN_HEIGHT, layout, clean_dataset: 180 -> 188 shops); new checks living-on-façade >= 2,20 m, wet rooms >= 2,20 m, hall >= 1 m; density cites art. 318 (zone 12) / 323 (zone 13). Annex 1 3.7.1 (20 m² LDK) is "No vigent". Demo shops picked by shell id (nomad_core.shop_by_id).
- STAGE 7 export: src/model3d/export_ifc.py runs the Rhino walls code outside Rhino -> results/model3d/*.ifc (IfcOpenShell, schema-valid) + *.glb (trimesh). Window slivers < 0,30 m dropped (nomad_model._openings).
- EXP 1 on real scans: CubiCasa5K test split only (400, never seen by floorplan-to-3d), data/datasets/test_plans_cubicasa (make_cubicasa_test.py: answer = indoor rooms + walls, shrunk by one wall thickness, outdoor spaces left out). Run long jobs from PowerShell, not Git Bash (bash "fork: resource unavailable" killed two runs).
- DECK numbering in step order: Exp 1 plan reader (2), Exp 2 zoning (3), Exp 3 rules (4), Exp 4 daylight (5, team), Exp 5 check + layouts + 3D (6-8). Bhavini's part is now 5 slides (zoning added).

- 2026-10-29 (review): BARS'S DAYLIGHT = src/daylight/bars_daylight.py (his exp1 XGBoost + results.csv from external/bars-nomad, his assumptions; NOMAD shells give the geometry) -> results/daylight/. Daylight is a liveability signal, not a legal fail. AVOID answers = src/check/avoid.py (not allowed / not liveable / keep it a shop [lowest 10 % retail within 100 m, design choice] / candidate / not modelled) -> website map mode. RULEBOOK BOOK = src/rulebook/compile_rulebook.py (23 official PDFs, 1,408 pages, index, page numbers, anchors) -> website flipbook with project bookmarks. NOMAD.gh = 10 small components (src/rhino/build_nomad_nodes.py, verify_nodes.py). Website: 3D starts with three.js and falls back to pictures only if it fails (never a pre-check). Reviews: docs/review_2026-10-29.md, docs/precedents_2026-10-29.md, docs/finch_analysis.md, docs/presentation/talk_structure_v2.md.

- 2026-10-30/11-01 (E23): STAGE 6 ITERATIONS = CIRCULATION STRATEGIES (Finch-style, user asked) in src/generate/plan2.py: "as it is" = street flats; then flats on both façades (back to back, half depth each), corridor to the block interior (back flats > 25 m from the street door dropped, CTE DB-SI SI 3), small flats filling the shop. Each searched over corridor width / position / flat order, one WEIGHTS set; shown only if it changes the plan; fallback "street flats only" with the reason. Proposals show only passing flats (failing ones go to "unplaced" with the room that fails). THROUGH FLATS WITH A PATIO DROPPED: Decret 141/2012 Annex 1 3.6.1 (patio is not the flat's façade) + 3.6.2 (façade >= S/9) cap useful depth at ~9-10 m; never passes at 5-13 m width. _CACHE.clear() in iterations() (cache keyed by id(programs) went stale in the browser worker). Old vs new: src/generate/compare_v2.py -> results/generation/compare_v2.json (fewer homes, all legal; old plans had 59 + 19 patio-only flats). Website engine: site/py/src/plan2.txt; website https://claude.ai/artifact/5Pu9capuBiKG5V4mYrYMY6. The results page is a Dashboard artifact: its page is the store doc files/index.html (= results/dashboard/dashboard_page.html), datasets are CSV assets + datasets/<id> docs. Demo stories regenerated in Rhino 2026-11-01 (make_demo.py -> draw_cases.py -> export_ifc.py -> build_site.py); demo titles in build_site.DEMOS take their numbers from the recipes; the website's step 7 / Exp 5 text and numbers come from compare_v2.json.

- 2026-11-01 (E24-E25): HABITABILITY = src/learn/habitability.py on the 13,444 rule-passing Swiss flats -> docs/habitability_rules.md (circulation 12 %, hall 1,75 m, entrance into a hall from a common stair/corridor, lit rooms on the façade). PLAN LIBRARY (Finch's method, user asked): src/library/build_library.py squares the flats into plan graphs (rooms, door edges with widths, entrance, lit sides) -> results/library/library.json; src/library/street_library.py keeps the ones NOMAD can use (one-sided, door behind; through flats, door at the side) -> src/generate/library_street.json. src/generate/library_fit.py: stretch solver (walls locked, wet rooms stiff, legal minimum widths), plan-graph checks, door/turning rules from Decret 141/2012 Annex 1 3.4 (doors 0,80/0,70, circulation 1 m, 1,20 m circles; doors widened when narrower), living 2,80 (3.7.2), kitchen 1,60 (3.7.3), fit score >= 75, rooms cover >= 82 % of the flat (no dead corners). src/generate/plan3.py = the generator now (nomad_core.generator()): street lobby 1,50 m (DB-SUA Anejo A) + shared hall behind the flats, flats along every façade the hall reaches within 25 m, through flats off a passage, side-entered flats for shallow shops. Website engine loads plan3, library_fit and library_street.json. STEP 3 BUILDING PANEL: src/zoning/catastro_plans.py (Catastro Visor 3D per-floor units, 600 of 5,376 parcels) + catastro_site.py (site/data/catastro/b_XX.json bundles) -> plans by floor, units, 3D, the shop's own unit; NO links out of NOMAD (user). src/building/catastro_shops.py models shops sharing a ground floor from their own unit -> avoid.py.

- 2026-11-01 (E26, Grok's Finch PDF items 1-5): EXISTING CIRCULATION = src/building/existing_core.py adds the Catastro ground-floor "Local COMUN" polygons (portal, stair) to results/real_shops/shells.json ("existing"); plan3 never builds over them and uses the street portal as the flats' entrance (nomad_core.iterate passes shop["existing"], shop["weights"]). RESPLAN = src/library/build_resplan.py (scaled by doors: median inner door 0,80 m - an assumption) merged by street_library.py. DOOR SWINGS = library_fit.swings + clear_zones (3.4.1.d/e: 1,20 m circles clear of door sweeps; in the hall at practicable doors); checked only on the best candidates (speed). GALLERY = each unit keeps "options" (top 3 distinct real plans) + "room_scores"; website drawer "Real plans for each flat" swaps them. WEIGHTS = website sliders -> request.weights -> plan3.iterations(weights). Street library 761 flats. E27: every street façade gets street doors (plan3._street_block, one lobby per SEG = 40 m) and every flat is checked for the 25 m route to its street door (CTE DB-SI SI 3).
- 2026-11-02 (E28, Finch list items 6-9): FURNITURE = src/generate/furnish.py: legal items from Decret 141/2012 Annex 1 (wardrobe 3.10.1, bedroom square free of swings + wardrobe 3.8, worktop + 1,00 m 3.15.c/3.7.3, WC/basin/shower 3.15.b/3.11.1, washing machine 3.15.d, 1,20 m circle free of fixed equipment 3.4.1.e) are hard checks; bed/sofa/table sizes are TYPICAL (assumption, not law; bed is a hard habitability check, sofa/table advice). Practicable bath door may open outward when that frees the circle. street_library keeps only furnishable flats (690). plan3.fits furnishes each candidate; units carry "furniture" (website, PNG, Rhino walls model, IFC IfcFurnishingElement). OWN PLANS = src/library/own_plans.py (DXF layers by use EN/CA/ES or JSON; CLI saves results/library/library_own.json, merged by street_library; website keeps them in localStorage and sends request.own -> plan3.set_own). Example: inbox/own_plan_example.dxf. GENERATED = library_fit.best_fits(generate=True): a real plan re-proportioned to GEN_STRETCH 0,65-1,60, score >= 55, marked lib.generated, only when no real plan fits a row (plan3._row fallback, fits gen). No Graph2Plan/HouseDiffusion. ASSISTANT = website "Ask NOMAD" (artifact capability sample, tools set_request / make_layouts / select_layout / swap_plans; quick tier). SPEED: galleries built only for kept layouts (plan3._options), layout.depth_at cached.
- 2026-11-02 (E29): plan3 runs the Stage 5 inside test (every room corner inside the outline within 15 cm, plan3._in_shop) so no red flats; 'most homes' rows also try 1bed/studio where asked types do not fit; shops under 6,5 m deep also try D = 5 m. 40 shops: 57 homes in 28. Empty shops = street front < 6 m (lobby 1,50 + narrowest real flat 4,7 m) or < 6 m deep. src/rhino/redraw_demos.py redraws demos already in NOMAD.3dm (backup rhino/NOMAD_before_redraw.3dm; only when Rhino is closed).
- 2026-11-02 (E30, approved: docs/proposal_warehouses.md, 'do it all together'): WHOLE BUILDINGS. src/zoning/warehouses.py -> results/warehouses/{candidates.csv, shells.json}, site/data/warehouses.json (Catastro industrial/retail/office with no dwellings; zone answer; census hint 'empty premises'/'no active business'/'active business' - a hint, not proof). src/generate/building.py = Decret 141/2012 Annex 4 Group B: Annex 1 sec. 2 checks; warehouse mezzanine when clear height >= 2*2,40 + slab 0,30 (slab: assumption); patios 3 m cut through deep floors (kept only if the part behind gets homes; parts' evac budget = 25 m - offset - passage); core per street door when > 1 level (plan3.LOBBY = 2,20; stair 2 x 1,00 m SUA1 T4.1; going 0,28 / riser 0,175 SUA1 4.2.1; lift cabin 1,00x1,25 SUA Anejo A; shaft 1,60x1,70 assumption), no passage strategies and no 5 m depths on multi-level. nomad_core.run_building; nomad_web routes shop.kind in (warehouse, commercial, office); nomad_model.build_walls stacks levels (ZOFF) + cores; prisms kind 'core'. Rhino demos D5/D6. Limit: no second exit (halls > 25 m from the street door stay empty).
- 2026-11-02 (E31): building.split gives a part behind a patio its own street door when it touches another street (building._street_in; CTE DB-SI SI 3: one exit 25 m, more than one 50 m / 35 m where people sleep). No official vacancy register or building-height download found (Open Data BCN, ICGC searches): census hint + user list; heights from the user in step 2.
- 2026-11-02 (E32, the 29 Oct crits, docs/review_2026-10-29.md): DAYLIGHT = plan3.LIT / _lit_share: living + bedrooms need >= 50 % of floor within the lit depth (Bars's prediction per shop via shop.lit_depth, else 5,5 m assumed; NOMAD liveability, not law); nomad_web returns daylight bands (_daylight), site draws them in the first tile. SHARED = src/generate/shared.py (Llei 18/2007 18 bis, DT 10a, Circular 8: private >= 24, share >= 6/home, 2,45 m circle, lit; Barcelona private+share >= 40 as stricter reading; MPGM 2004 DA2 density -> check); plan3.USEFUL_MIN, plan3.SMALL; site radio 'Kind of homes'; 'allotjament temporal de protecció' only on public facility land (TRLU 34.5 quater) - not offered. CITY = src/check/city_runs.py -> results/city/homes.csv, site/data/city_homes.json; site section #policy. AMB = src/zoning/amb.py -> data/amb/{towns,candidates}.csv, site/data/amb.json (zoning.gate falls back to MUC codes: A1/A2/N = NO, R = CHECK). PRECEDENTS = site section #precedents (from docs/precedents_2026-10-29.md).
- 2026-11-03 WEBSITE LOOK (user's reference image, a fluorescent exhibition floor plan): site interface = grey paper #C9CBC6, ink #111211, one neon #E5FF00 (fills/strokes only), Inter Tight 800 headlines, JetBrains Mono uppercase labels, Inter body, neon wall + halftone fade over each section, circled step numbers, neon buttons; verdict pills YES neon / PARTLY neon ring / NO ink. The MAP, GENERATED LAYOUTS, their 3D and data figures KEEP THEIR OWN COLOURS (E05 rooms, map green/amber/red via the --m-* tokens, blue façade) - user said NO to recolouring them. Backups: scratchpad index_before_neon.html.
- 2026-11-03 RULEBOOK = a flipbook on its own, after the user's Heyzine reference (29 Oct screen recording): no frame, cover alone then spreads, page-stack edges, curling corners, the rules panel (project bookmarks, search, index) sits beside the book on the left as before; floating icons top right (download, full screen), curved arrows at the bottom corners, page number below; sized to fit the window.
- 2026-11-03 LAYOUT = after SimiStar, in the neon look: black background by default on every device; one content edge (1240 px, 24 px gutter, 16 on phones); header = logo | pill tabs (Check, Design, Saved, The city ▾, Rules ▾, How it works ▾; the section on screen is lit neon) | language + simple view; section tabs in a tray (five shops, map colouring); one button family (32 px controls, 40 px main action, 6 px corners; panels 8 px); 8 pt spacing; caps labels 11 px, controls 12 px.
- 2026-11-03 PAGE ORDER = the 8-step workflow: Workflow (h1, step cards link to their section) > Check an address (steps 1,2,3,5) > City in 3D (1) > The rules + Rulebook (4) > Design homes + Five shops (6-7) > Saved, Real shops, For the city (8) > Evidence (Experiments, Precedents, Sources). Header tabs carry the step numbers. Picking a shop anywhere also fills Design homes step 1.
- 2026-11-03 SIMPLE VERSION (now the main site, v34) = App | Research tabs at the top. App: two doors (I have a shop / I work for the city) > 1 Your shop (verdict in plain words, details on request) > 2 Your homes (tabs: Checks, Other plans, Compare) > 3 Saved > For the city (Where to start, City in 3D) > The laws (rulebook). Research: Workflow, Results (real shops), Rule cards + golden set, Experiments, Precedents, Sources. Removed as repeats: Five shops section (its test shops are in step 2), "Laws for this project" tab (the rulebook lists them), the separate rule-card tab in the app. Buttons in sentence case, brighter greys, 16 px text. Built by scratchpad make_simple.py from the v33 page.
- 2026-11-03 (E33): PLAN AI = src/ai/ (plan_data.py -> results/ai/plan_set.npz from the plan library; train_plan.py U-Net, 40 epochs on the RTX 3060 with tools/train-venv, weights results/ai/plan_unet.pt; generate_plans.py: clean + straight walls (_straighten) + doors + NOMAD checks, also kitchen + bath present and <= 8 corners per room -> results/library/library_ai.json, merged by street_library.py as source 'NOMAD AI'; --no-ai leaves them out). plan3._flat_ok drops plans that would fail useful / daylight / window share before ranking. 40 shops: 57 homes in 28 (was 48 in 22). Datasets: docs/plan_datasets_2026-11-03.md.
- 2026-11-05 VIDEOS = nomad/video: NOMAD_showcase.mp4 (66 s, Piper offline voice en_US-lessac-high) + deck_*.mp4 (silent) in the deck on slides 2, 9, 14 via data-video. Demo shop Arago 212 (3 of 3 homes, YES). Room clips are 3D illustrations, not photos. Sources (recorder, room scene, compose script) are in the session scratchpad only.
- 2026-11-05 APP ORDER: two doors > City in 3D (first map, opens at 12:30 daylight) > 1 Your shop > 2 Your homes > 3 Saved > For the city > The laws. Header: City in 3D first; For the city is a single tab. site/index.html has no doctype: publish a copy wrapped in the html skeleton.
- 2026-11-05 3D CLICK: any building clicked in City in 3D also answers in Find your shop, marks the 2D map and fills Your homes: empty shop = show (nearest to the click), unused building = showWh, any other building = showOther (Catastro facts only, no verdict, grey ring). The page then scrolls down to Find your shop.
- 2026-11-05 TEAM REPO: pushed to iaac-maai/nomad main (13f4ace). Bars changed the site in the repo after v35 (data/daylight.json, rescored map answers and city counts, 5 m + 3 m heights, 3D colours, Sources). Merged 3 ways into site/index.html and published as v39 with data/daylight.json, so repo, local and live match. City now: 13 places for 1,000 homes, 6,156 legal homes in usable places (deck slide 14 and the city video still show 6,442). site/index.html has no doctype: publish a copy wrapped in the html skeleton.
- 2026-11-05 (v40): The laws section and tab sit right after 2 Your homes. Every check that cites a law opens it in the rulebook (site CARD_ANCHORS + openLaw = same as the list beside the book; src/rulebook/add_anchors.py added 7 pages found from their headings); the 5 NOMAD-only checks have no link. 3D city: cityMark shows the selected building in neon with an ink outline, from 3D clicks and from every other way of picking a shop; the jump to Find your shop waits 0,9 s.
- 2026-11-05 (v41): 3D selection = see-through neon (opacity 0,40) with a neon outline, the building keeps its colour. Rules list: bk-item with the open law lit (lawOn) and a + dropdown with the rule text (anchors.json "text" = the highlighted official lines; 4 scanned pages have none, and get a frame round the page instead of line highlights). Saved and Where can the city start closed with + / − on the heading line (collSet); a link or door to them opens them. Metro map base = src/zoning/amb_base.py -> site/data/amb_base.json (MUC zones by CODI_INE, town outlines, 14 labels; run with tools/train-venv). Sources table extended. Pushed to iaac-maai/nomad main as 594c46b, so repo, local and live match at v41.
- 2026-11-05 (E34, v42): SPACE OPTIMISATION. src/generate/eval_space.py (efficiency = passing flats / floor within 9 m of a street facade, 3.6.2 S/9). src/library/placed_plans.py = room placer + connections.json (374 plans, source NOMAD placed, kitchen <= 3 m and hall <= 2,6 m deep, storage behind). plan3.build_doors + strategy homes with their own street door (MODES door, DOOR_DEPTHS), plan3.GAPS. 40 shops: 52 -> 70 homes, 61 -> 70 % of reachable, 27 -> 32 % of floor. Website key figure efficiency (reachArea). City counts still from the old engine.
- 2026-11-05 (v43): Selected and the tabs end with the 3D box and scroll inside (.ws-left contain: size; visible scroll bars). User: never write "Bars's model" on the site; the name stays only in the team credit. Say "the daylight model".

## 8. Your first task now

1. Save this prompt as `CLAUDE.md`.
2. Stage 0: create the folder structure, a Python virtual environment, `requirements.txt` (requests, pandas, pymupdf, pdfplumber, pydantic). Show me the tree. STOP.
3. After my go-ahead: Step 1a — save and run `fetch_national.py`, show results. STOP.
4. Then Steps 1b → 1e, one at a time, showing me sources before downloading.
