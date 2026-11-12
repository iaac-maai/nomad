# Facade reading: handoff note for Bars (prepared 10 Nov 2026, NOT sent)

Bhavini stops the facade work here. If Bars takes it forward, he gets exactly what this note lists, nothing else
(no access to the app, the lab book, the laws handbook or the rest of the code). Bhavini decides what is sent and when.

## What exists
- One building read end to end: Av. Diagonal 413 (9331705DF2893A). Result format below.
- The method: `docs/facade_workflow.md` (can be shared as is).

## What is left (for whoever takes it)
1. Corner (chamfered) buildings: two facade planes in one photo; straighten each plane separately.
2. Speed: about 2 minutes per building now (RTX 3060); target under 1 minute (one detector question per tile, model kept loaded).
3. On demand: read a facade when a building is clicked, save the result, show it next time instantly (backend needed: a local server first, a cloud GPU later).
4. More test buildings to check the rules (symmetry test, ground floor + equal floors) on other styles.

## Result format (one file per building, what the app reads)
```
{ "<ref14>": { "address", "w": street front m, "h": facade height m (LiDAR, at the front wall),
  "lines": [floor lines m, ground = 0], "rule": {"ground_m", "upper_m", "cornice_band_m", "measured_minus_fit_m"},
  "axis": mirror axis m or null, "street_z": pavement height m,
  "ops": [[floor, kind, x0, x1, sill, head, inferred 0/1], ...]   kinds: window, balcony door, door, shopfront, balcony
  "hidden": [[x0, z0, x1, z1], ...]  areas hidden by trees,
  "source": text } }
```

## Data and licences he would need
- Catastro facade photo service (free, no sign-in); photos must not be published (Catastro licence; only the drawings).
- Catastro INSPIRE buildings (footprints, floors); ICGC LiDAR v3.1 (CC BY 4.0).
- Grounding DINO base (Apache-2.0), OpenCV (Apache-2.0).
