# Finch 3D, taken apart: every feature, how it works, and what NOMAD can use (29 Oct 2026)

Sources: finch3d.com (home, /product) and the Finch documentation at docs.finch3d.com (llms.txt index; pages read:
Finch Interface, Iterate with variants, Massing Studio, Generate Floor Plate Algorithms, Generating Unit Mix,
Generating Unit Plans, Algorithm Theory, Adaptive Plan Library, Tools & Commands, Export, Feature Bank, AI Agent Archie).
Several pages are only a video (Area Graph rules, Passage and room width rules, Corridor and unit-mix algorithm, PDF
export): for those we know the feature exists, not its exact fields.

## 1. What Finch is
An AI floor-plan authoring tool for architects (Sweden; enterprise customers). You bring a building mass from Rhino,
Revit, Forma or Archicad. Finch splits it into stories, cores, corridors and units, then fills each unit with a plan,
and exports BIM back. Its claim: "thousands of real-time design options and instant feedback".

## 2. The workflow, step by step

| Step | Finch | What happens |
|---|---|---|
| 1 Bring the building | Rhino / Revit / Forma plug-in, Grasshopper upload | Mass + context (neighbours, trees, terrain) go to a Finch "project"; each design option is a **variant** |
| 2 Massing Studio | Assign a **program** per story (retail, office, residential, circulation) | A **ring chart** updates live with % and GFA; **custom calculations** (e.g. budget per m² GFA, per program or per space type); **story heights** per program; **outer wall width** (default 350 mm) |
| 3 Floor plate | Three algorithms | *Around existing circulation* (retrofit: core already known), *Generate cores* (Finch picks number and place of cores), *Corridors and core* (from scratch: egress distance, core depth/width, orientation) |
| 4 Unit mix | Set % per unit size (e.g. 50 % 3-bed 95 m², 50 % 2-bed 75 m²), **minimum unit width**, party wall width, align walls with core | **Sliders = weights**: unit mix, size accuracy, grid lines, **daylight access**, squareness and adjacencies. Results: **Match score**, **Fit** (± m²), **Unique units** |
| 5 Unit plans | From your **plan library** or Finch-generated | Filter by bedrooms, baths, **region**; only plans scoring ≥ 75 % shown; Data drawer shows **Adaptivity** (how much each room stretched), **Daylight** (rooms that need light reach the façade) and **room-by-room scores in red** |
| 6 Edit | Plan editor: walls, space dividers, doors, objects, measure; mirror, smart rotate; linked copies | Copy a plan to matching units; edits update all linked units |
| 7 Compare | Variants list (left panel), **Key Figures**, **Parallel Axis Diagram** | Hover variants to compare figures; one camera saved for all variants so thumbnails match |
| 8 Deliver | BIM to Revit (a family per object), 2D/3D to Rhino layers, Grasshopper stream, CSV stats, PNG, PDF drawings | |

## 3. How the generator decides (Algorithm Theory)
- **Non-negotiables first:** every unit reaches the corridor, minimum unit width, number of stairwells.
- **Then a score** for each iteration on the target metrics, with user **weights**. Raising one (unit size) costs another
  (ratio, daylight); all weights at maximum = all equal.
- It tries to hit unit sizes and ratio across the building; typically one unit ends up too big or small, and the
  architect fixes it.
- **Graph rules** (Area / Passage and room width): user-defined minimums (bedroom size, bathroom size, passage width)
  that generated plans must meet. They are "regulation-aware"; Finch does not say which code is checked.
- **Adaptive plans:** a saved plan stretches to a new unit; walls can be **locked** (red) or **extendable only** (can grow,
  not shrink).

## 4. The interface pattern
- **Centre:** the 3D or plan view; top toolbar for view controls (wireframe); single click = context menu, double click =
  go one level deeper (site → massing → floor plate → unit plan).
- **Left:** Key Figures (ring chart, GFA / NIA / usable area) and the list of variants.
- **Right:** **Data drawers** that fold open: Programs, Space types, Unit mix, Story heights and outer walls; plus tabs
  Display (sun with date and time, camera, parallel-axis diagram) and Output (CSV, screenshot).
- **Feature bank:** version history ("time machine"), daylight and shadow, metric/imperial, saved camera, parallel axis.
- **Archie (AI agent):** plain-language requests. It answers questions ("what is the GFA?"), finds and counts rooms and doors,
  exports schedules (CSV/XLSX), edits room types, doors, windows and walls (with sub-agents for bulk door and window
  edits), and moves the view.
- **Marketing site:** white, a large serif headline, one claim and one looping product video per section, integration
  logos, one customer quote, "Book a demo".

## 5. Finch vs NOMAD

| | Finch | NOMAD |
|---|---|---|
| User | architects in firms | policy makers and owners (and architects) |
| Input | a building mass | an empty shop: address, Catastro outline, or plan drawing |
| Law | "regulation-aware" rules the user sets; code not named | real Barcelona law, each rule quoted from the official text, with its page in the rulebook |
| Answer | layouts + key figures | **YES / PARTLY / NO / avoid**, with the reason, then layouts |
| Daylight | a weight in the generator; "rooms reach the façade" | the same façade check + Bars's daylight model (DF and lit depth) |
| City scale | one project | all 6,149 empty shops on a map |
| Export | Revit BIM, Rhino, CSV, PDF | IFC, glTF, PDF report, Rhino file |

**So NOMAD's advantage is the law and the city.** Finch's advantage is the interface and the plan editing.

## 6. What NOMAD takes (in order)

| # | Finch feature | NOMAD version | Status |
|---|---|---|---|
| 1 | Three-panel workspace | "Design homes": plan/3D in the centre; left = verdict + key figures + layouts list; right = drawers (your flats, rule cards, laws of this project, value, report) | **built today** (see below) |
| 2 | Key Figures ring chart | Ring per layout: living / bedrooms / kitchen + bath / hall / not used, with m² | **built today** |
| 3 | Match score / Fit | "asked vs fitted" score per layout: homes asked, homes fitted, flats passing all rules | **built today** (in the key figures) |
| 4 | Variants compared, parallel axis | The three layouts and saved shops compared on homes, m² used, flats passing, façade used | saved-shop comparison exists; parallel axis next |
| 5 | Weights (sliders) | Already: unit sizes; next: a "daylight first ↔ most homes" weight on the generator | next |
| 6 | Data drawer "room-by-room red" | Rule cards per flat with the failing room in red on the plan | exists on the plan; link it to the drawer next |
| 7 | Double-click to go deeper | City → shop → layout → flat | next |
| 8 | Archie | "Why?" assistant: explains a failed rule in plain words and opens the rulebook page (needs a model call from the page) | later |
| 9 | Locked / extendable walls | Mark the walls that can't move (party walls, structure) in uploaded plans | later |
| 10 | Product page | Front page with 4 claims and short loops of NOMAD (needs screen recordings) | later |

**Not for NOMAD:** enterprise seats, SSO, organisation plan libraries, Revit families. NOMAD stays free, open data and plain language.
