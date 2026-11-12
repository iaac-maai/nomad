# NOMAD facade workflow: windows, doors, balconies and floor heights from one photo

Agreed with the user on 10 Nov 2026 on Av. Diagonal 413 (9331705DF2893A). Use this for every facade.
Order matters: **always correct the image first**, then measure, then detect, then apply the architectural rules.

## Inputs

| What | Source | Licence / note |
|---|---|---|
| Facade photo, 1 per property | Catastro `OVCFotoFachada.svc/RecuperarFotoFachadaGet?ReferenciaCatastral=<ref14>` | Stays on this computer. Only what we make from it (counts, sizes, drawings) is shown, with "Source: Dirección General del Catastro, accessed <date>". Never on the site, GitHub or to the team. |
| Street front length, floors above ground | Catastro INSPIRE buildings (`data/barcelona/catastro/buildings.json.gz`) | |
| Street level and facade height | ICGC LiDAR v3.1 grids (`data/lidar/grid`) | CC BY 4.0 |
| Detector | Grounding DINO base (Apache-2.0), in `tools/train-venv` | |
| Backup photo | Mapillary (CC BY-SA, account needed) | Only when the Catastro photo is bad. |

Not used: Google Street View (terms), OpenStreetMap (181 buildings in the city have any facade tag), airborne LiDAR for openings (sees roofs, not walls).

## Steps (scripts in `src/facade/`)

1. **Straighten the photo** (`facade.py (step 1) <ref>`)
   - Lens bend: choose the correction that makes the vertical lines meet in one point.
   - Vertical and horizontal vanishing points give the camera turn and focal length; turn the photo to face the facade.
   - Out: `results/facade/<ref>/straight.jpg`.
2. **Heights from LiDAR, measured at the facade** (`heights.py`)
   - Street level = LiDAR ground on the pavement strip 1-4 m in front of the facade line (not a wide window around the plot).
   - Facade height = median LiDAR top in the strip 0,5-2,5 m behind the facade line = top of the front wall (cornice). Rooftop huts, tanks, pediments and lower back parts are not the facade height.
3. **Edges and scale** (`facade.py (step 3) <ref>`)
   - Up: the LiDAR facade height sets metres per pixel.
   - Across: of the long vertical lines either side of the centre, take the pair that makes the width equal the Catastro street front at that same scale (outer side of corner pilasters).
   - Check: across and up scales must agree within 3 %. If not: "check on site".
   - Which footprint side is the street front: the one whose length fits the photo.
4. **Detect openings** (`facade.py (step 3)`)
   - Grounding DINO on the facade between the strongest edge lines (keep this crop fixed: the same picture gives the same boxes), whole and in enlarged tiles; then the ground floor alone; then **bay by bay** (each floor x column cell, enlarged) for balconies ("balcony, stone balustrade, curved balcony, balcony railing") and windows.
   - Trees: ask for "tree, palm tree, leaves"; that area is **hidden**, not "no window".
   - Position rules: a balcony stands in the lowest third of its floor; belongs to the floor line nearest its bottom; no balcony search on the top floor (attic); a box that also holds the stone arch under a balcony is still a balcony (only its bottom is used).
5. **Floor lines**
   - Measured from the facade's horizontal lines, set on the balcony bottoms (+0,15 m slab).
   - A floor line must sit above the heads of the floor below + 0,30 m lintel, and not above its own sills.
   - **RULE: the ground floor has its own height; every floor above has one same height.** Fit `line k = g + (k-1)·s` (least squares). What is left up to the LiDAR facade height is the cornice / parapet band.
   - Report the fit and the measured-minus-fit per floor; a residual over 0,5 m is flagged.
6. **Architectural rules on the drawing** (`facade.py (step 4)`)
   - **Template:** on the typical floors every opening has one width and one height (medians of the openings really seen, not inferred); columns line up floor to floor. A box over two doors is split into one per column.
   - **Ground floor:** openings in one rhythm (shopfronts and the entrance under the same arches) share one width and one head; a wide exception (garage door) keeps its own size.
   - **Symmetry is a test, not a rule:** find the mirror axis; the facade counts as symmetrical only if at least 60 % of the openings seen have a partner within 0,8 m of their mirrored place. Then pair openings by order from the outside in (robust to bay windows that stand out), centre the middle one, and rebuild hidden ones from their mirror. If the test fails: column grid only.
   - **Repetition (stamp):** on a typical floor where at least 60 % of openings have a balcony, an opening without one gets the floor's template balcony.
   - **Balconies:** sized from the doors they serve plus the side margin of the middle balcony (least perspective), because parts that stand out of the wall stay in perspective after straightening.
   - Ground floor, first floor (bay windows) and top floor (attic) keep their own pattern.
   - Everything rebuilt from rules or mirrors is **marked inferred** (light grey-blue / hatched).
7. **Draw in the one Rhino file** (`src/rhino/record_facade.py`, run with `run_in_rhino.ps1` while Rhino is closed)
   - `rhino/NOMAD.3dm`, layer `06 NOMAD experiments::facade <address>`: 1 photo straightened (private), 2 facade drawing with floor heights and mirror axis. Backup first; redraw in place. 3D only when the user asks (`ONLY_2D`).
   - Pictures: `src/rhino/capture_facade.py`.

## Outputs per building (`results/facade/<ref>/`)

`facade.json` (detections in metres, floor lines measured and fitted, LiDAR front heights, checks), `openings.json` (the drawing: floor, kind, x0, x1, sill, head, inferred), `elevation.png`. Photos and `*_PRIVATE.jpg` stay local.

## Numbers that are ours (assumptions, not law)

Slab 0,30 m; lintel 0,30 m; balcony slab 0,15 m; tolerances 3 % (scales), 0,8 m (mirror), 60 % (symmetry, repetition), 0,5 m (fit residual).

## Law used with the heights

- Decret 141/2012 (converted premises): clear height >= 2,40 m (already in NOMAD's checks).
- MPGM 1999 art. 225: mezzanine (entresolat) clear height >= 2,50 m below and above.
- The PGM's floor heights for planta baixa / plantes pis are **not in our rulebook**; do not use a number until the article is found.

## Known limits

Corner (chamfered) buildings have two facades in one photo: not solved. About 2 minutes per building on the RTX 3060. Read facades on demand (when a building is clicked), not citywide.

## Approval checkpoint (user, 12 Nov 2026)
A facade drawing reaches the app, its 3D and the plans ONLY after the user has looked at its elevation and approved it:
`.venv/Scripts/python src/facade/facade.py <ref> approve`. Approval freezes a copy (results/facade/approved/<ref>/);
the app reads only those copies (site/data/facades.json), so later code changes never alter an approved facade until
it is approved again. Approved: Av. Diagonal 413 (10 Nov version). Waiting: Pl. Sortidor 4.
In the app an approved facade gives: the facade drawing in The building, the floors at their measured heights, and the
street face's windows, doors, shopfronts and balconies on the building's 3D. Next: the shop's real openings in the plans.

## Analyse before drawing (user, 12 Nov 2026) — step 3b, `facade.py <ref> analyse`
1. Level: measure the leftover tilt of the horizontals against height on the straightened facade and take it out.
2. Repeat: cut each upper floor into a band (one typical floor high, on its floor line), slide each band up to 0,8 m to
   line it up with a middle floor, and compare the bands (grey-image correlation >= 0,55 = same floor type).
3. Typical floor: blend the bands of a type (pixel median), so trees, blinds and one-off errors fade.
4. Vote: read every floor of a type and keep what most floors agree on, at the median size; then read it as an
   architect: a "window" that is a balcony railing goes; a wide window with a bright pier is two windows; every balcony
   has a door behind it (read above the balcony, or copied from the matching balcony, else centred and inferred).
5. Inventory (inventory.json + analysis_PRIVATE.jpg) for the user to check; THEN draw every floor from its type
   (a lower floor keeps the openings, scaled to fit). Ground floor: shopfronts and doors (a glazed opening under 1,3 m
   wide is a door).
Pl. Sortidor 4: floors 1-5 = one type (balcony + door | pair of narrow windows | balcony + door); ground = shop window,
entrance door, restaurant door. Known limit: real floors here get lower upwards (3,25 / 3,45 / 3,15 / 3,04 m between
balcony bottoms); the drawing keeps the rule "ground floor + equal upper floors".

## Floor heights: ground + one upper height, in 5 cm steps (user, 12 Nov 2026)
Upper floors share one height; only the ground floor differs. Measured on the photo (analysed facades: each floor found
by sliding the typical floor up the levelled facade; others: the reader's balcony-bottom lines), then the best ground
height g and upper height s on a 5 cm grid, with the top floor ending no more than 0,5 m above the LiDAR facade top
(facade.py uniform / floors_uniform, used by every drawing). The 3D city model is NOT a measurement: it sets 5 m + 3 m a
floor from the land registry's floor count, so it is a check only.
- Pl. Sortidor 4: ground 4,30 m, upper 3,15 m; top floor ends at 20,05 m. LiDAR facade top 19,78 m (roof 20,1-20,3),
  city model 20,0 m: all agree within 0,3 m.
- Av. Diagonal 413: ground 5,75 m, upper 3,80 m; top floor ends at 28,55 m, cornice band to the LiDAR top 30,47 m about
  1,9 m (the big cornice). City model 23,0 m is 7,5 m too low: its 3 m a floor does not fit this building's 3,80 m floors.
