# grasshopper — ONE file: NOMAD.gh

Always open NOMAD with **`OPEN_NOMAD.cmd`** (in the nomad folder). It opens `rhino/NOMAD.3dm` (the one
Rhino file) with `grasshopper/NOMAD.gh` (the one Grasshopper file) loaded. Work and save in these two files only.
Older experiments are in `archive/`.

## Three ways to give NOMAD a shop (the first one that is set wins)

**1. A plan drawing (PNG, JPG or PDF)**
1. Right-click **Plan file** -> *Set one file path* -> pick the plan.
2. Set **known_facade_m** to the length of the longest street façade in metres (read it off the dimension lines).
3. Switch **read plan** on. After ~10 s the plan appears under the flats; the panel says what was found.

**2. Your own outline in Rhino** — a closed `Polyline` on layer *02 Shop outline*; right-click **Your shop outline** ->
*Set one curve*. Optional street line on layer *03 Street facade* -> **Street facade**.

**3. A real shop from the dataset** — move **shop_index** (0–179).

## Choose the flats
`n_studio`, `n_1bed`, `n_2bed`, `n_3bed`, **compact rooms**, `floor_height`.

## Stage 5 + 6: before and after, checked
The panel shows BEFORE (the shop as it is) and AFTER (the smallest change that houses more flats: light patios
+ a 1,20 m shared corridor + back flats), each with its verdict YES / PARTLY / NO and the rule lines (OK / FAIL, value, article).
The 3D shows AFTER: red = fails a rule, light blue = new patio, grey = shared corridor.

- **make sheet** (switch on, then off): adds a before / after sheet to NOMAD.3dm on its own layer
  **06 NOMAD experiments::<shop>_<date time>**, beside the earlier ones, and saves the picture to `results/sheets/`.
  Sheets are never overwritten: every one stays in the file until you delete its layer.
- **experiments in this file** (on by default): every experiment made outside your window (the lab-book runs, the inbox)
  is drawn into NOMAD.3dm the next time Grasshopper solves. **Save NOMAD.3dm** to keep them.
- **make demo (stages 5-7)** (switch on, then off): the full story for the current shop, added to NOMAD.3dm -
  Stage 5 flags on the shop as it is, Stage 6 three 2D iterations (1 as asked, 2 compact rooms, 3 most homes) with the
  number of homes, and Stage 7 a 3D model of each iteration right under its plan. Pictures + a presentation board
  (`results/sheets/<name>_board.png`).
- **run inbox**: every plan dropped in `nomad/inbox/` (+ optional `<name>.json`, see `inbox/README.md`) gets its own sheet.

Rebuild NOMAD.gh (keeps NOMAD.3dm):
`powershell -File src\rhino\run_in_rhino.ps1 -Script C:\Bhavini\AI\ADs\nomad\src\rhino\build_nomad.py -Done C:\Bhavini\AI\ADs\nomad\logs\rhino\build_nomad_log.txt`
(Rhino no longer obeys `/runscript` at start-up since a plug-in update; this helper types the command into a fresh Rhino.)

## The components (29 Oct 2026: split into small steps)
NOMAD.gh is now 10 small components, read left to right. Each does one thing and passes its result to the next:

| Component | Inputs | Gives |
|---|---|---|
| 1 Read plan | plan file, read plan, known façade m, floor height | the shop read from a drawing |
| 2 Shop | read shop, your outline, street façade, shop index, floor height | the shop (drawing > your curve > dataset) |
| 3 Zoning | shop, address | the shop with its zone (PGM art. 225.7) |
| 4 Flats asked | studios, 1-bed, 2-bed, 3-bed | the mix |
| 5 Flat sizes | m² per type, compact | room sizes |
| 6 Check + layouts | shop, mix, sizes | before / after, verdict, report |
| 7 Daylight | shop | Bars's daylight prediction (real Barcelona shops, by address) |
| 8 3D preview | shop, result, floor height | coloured room blocks in Rhino |
| 9 Make | shop, mix, sizes, result, make sheet, make demo | sheets and demos in NOMAD.3dm |
| 10 This file | run inbox, experiments in this file | inbox runs and recorded experiments |

The old one-component file is in `archive/NOMAD_one_component_*.gh`. Rebuild with `src/rhino/build_nomad_nodes.py`
(Rhino closed), check with `src/rhino/verify_nodes.py`.
