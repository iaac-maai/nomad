# Parked features

These features were taken off the website after the midterm (9 Nov 2026). Nothing was deleted from history:
the whole site as it was, with every file named below, is on the branch **`parked/before-cleanup`**.
To look at one, check out that branch (`git switch parked/before-cleanup`) and open the file.

Line numbers refer to `Bhavini_NOMAD Files/04_Website/index.html` on `parked/before-cleanup`.

Bhavini's later versions of the site (v41–v43: Five layouts, layout scores, space optimisation) are on a
separate branch, **`parked/bhavini-v43`**, untouched.

---

## 1. Weight sliders ("What matters most")

Four sliders that share 100 % between "the flats I asked for", "as many homes as fit", "floor used by homes"
and "how well the real plans fit". NOMAD ranked its layouts with them.

| Where | What |
| --- | --- |
| `index.html` lines 804–810 | the sliders (`#wts`) |
| `index.html` lines 2668–2680 | `setShare`, `WK`, `engineW` (the shares, and the engine's scale ×0.16) |
| `index.html` line 1853 | the weights sent with every layout request |
| `Bhavini_NOMAD Files/02_Code/src/app/nomad_web.py`, `02_Code/src/generate/plan3.py` | where the engine uses them |

**Before it comes back:** the layout engine (2) is back first; the page says the scores are NOMAD's own choice,
not law; a test shows that moving a slider changes which layout wins, and the reason is shown to the user.

## 2. The "Your homes" layout engine

Step 2 of the app: from the shop's footprint, NOMAD drew flats, checked every rule, counted homes and built them in 3D.
It also produced the home counts in "Results" and "For the city", which were removed from the site with it.

| Where | What |
| --- | --- |
| `index.html` lines 781–840 | the "Your homes" section (`#design`) |
| `index.html` lines 1774–2089, 2170–2185, 2836–2859 | the design flow, gallery, key figures, plain answer |
| `index.html` lines 1383–1464 | the five demo shops (D0–D4), already unused before the cleanup |
| `04_Website/py/worker.js`, `04_Website/py/src/*.txt`, `py/src/library_street.json` | NOMAD's Python, run in the browser |
| `data/shells.json`, `data/room_programs.json`, `data/demo_shops.json`, `data/city_homes.json`, `img/D*.png`, `models/*.gltf.json` | its data (only in the published artifact, never in git) |
| `Bhavini_NOMAD Files/02_Code/src/generate/`, `02_Code/src/library/`, `02_Code/src/app/nomad_web.py`, `02_Code/src/check/flags.py`, `02_Code/src/check/city_runs.py`, `02_Code/src/rhino/nomad_core.py`, `02_Code/src/rhino/nomad_model.py`, `02_Code/src/model3d/prisms.py` | the engine itself (the same code runs in Rhino) |
| Pyodide 0.26.4 | Python in the browser |

**Before it comes back:**
- Pyodide is not committed: load the pinned version from the CDN (`https://cdn.jsdelivr.net/pyodide/v0.26.4/full/`).
- Home counts are checked by an architect on a sample of real shops, and the city counts are rerun with one
  engine version (on 5 Nov the city counts still came from an older engine than the site).
- The shared-housing rule (section 5) has an official source.
- Every number the engine checks matches a rule card and its source sentence.

## 3. Plan upload (`readPlanImage`, DXF)

The user could upload a picture of the shop's plan (read in the browser from its dark lines) or add their own flat
plans as DXF / JSON.

| Where | What |
| --- | --- |
| `index.html` lines 790–795 | the picture upload (`#upbox`) |
| `index.html` lines 2860–2966 | `readPlanImage`, `dilate`, `erode`, `traceLargest`, `rdp`, `upView`, `startDraw`, `useUploaded` |
| `index.html` lines 811–815, 1867–1892 | own plans: `#ownp`, `addOwnPlans`, `saveOwn`, `drawOwn` |
| `04_Website/py/src/own_plans.txt` = `02_Code/src/library/own_plans.py` | reading DXF / JSON plans |
| `Bhavini_NOMAD Files/02_Code/src/building/read_plan*.py`, `eval_read_plan.py`, `finetune_scans.py` | the plan readers and their tests (Exp 1) |

**Before it comes back:** the layout engine (2) is back; the reader is tested on real scans (Exp 1 showed a large
drop from our own drawings to CubiCasa5K scans) and the user can always correct the outline; CubiCasa5K is
used for research only (not for commercial use).

## 4. "Ask NOMAD"

A chat assistant that changed the layout request in plain words ("make it all 2-bedroom flats").

| Where | What |
| --- | --- |
| `index.html` lines 821–827 | the panel (`#agent`) |
| `index.html` lines 1996–2089 | `agentState`, `askAgent`, `startAgent` (uses the artifact runtime's `sample` capability: the viewer's own Claude account) |

**Before it comes back:** the layout engine (2) is back; the assistant can only change the request, never a rule
value; no API key is in the code; its use is logged in `docs/AI_LOG.md`.

## 5. Shared housing (Llei 18/2007 art. 18 bis)

The "shared-space homes" option lived inside "Your homes" (`index.html` lines 800–803) and is parked with it.
The old text said both "small private homes (24 m² and up)" and "each home needs 40 m² of private space".

Catalonia: 24 m² private + at least 6 m² common, at least 36 m² in total (Decret llei 50/2020, transitional
provision 10). No official source found for 40 m²; don't use it until one is found.
