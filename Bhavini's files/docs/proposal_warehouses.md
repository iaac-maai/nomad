# Proposal: NOMAD for empty warehouses and commercial buildings (approved 2026-11-02, built: lab book E30)

Today NOMAD converts one ground-floor shop. This adds whole buildings: empty warehouses (naus), workshops, and
commercial or office buildings that nobody uses.

## What we already have
- Catastro buildings (data/barcelona/catastro/buildings.json.gz): every building's use, footprint and storeys.
  Without any homes: 1,741 industrial, 1,989 retail, 1,093 office.
- PGM zoning gate (src/zoning/zoning.py): zones 12, 13, 14b, 15 allow housing; 22@, 18, 20 = check the zone's own plan;
  22a industrial = no.
- Engine: real-plan library, furniture, patios (the warehouse demo already cuts a patio), 3D, IFC, Rhino.

## Candidates (Catastro use x zoning x 2024 commercial census)
| Use | Zone allows housing | Zone plan decides (22@, 18, 20) | Zone says no (22a) |
|---|---|---|---|
| Industrial, no active business or an empty premises | 259 buildings, 165k m² | 200 buildings, 342k m² | 568 buildings |
| Retail, same | 483 buildings, 404k m² | 95 buildings | 217 buildings |
| Office, same | 151 buildings, 620k m² | 108 buildings | 165 buildings |
"No active business" is only a hint: the census lists ground-floor premises, so an office or a warehouse may still be in
use. We need a vacancy source (see question 2).

## The law that changes (all in the rulebook already)
Decret 141/2012 Annex 4, apartat 2:
- A shop is Group C: change of use of up to 50 % of a building. The building rules (Annex 1 section 2) are waived,
  except 2.2.1.
- A whole warehouse or commercial building is Group B: total change of use. Annex 1 applies with a 10 % reduction on
  patio sizes (2.5.1) and a 2,40 m minimum height. So these building rules come in:
  - 2.1 an accessible route to every home;
  - 2.2 access through a common space, with a 1,50 m circle in front of the lift;
  - 2.3 stairs (CTE DB-SI, DB-SUA);
  - 2.4.1 / 2.4.2 a lift, and a second lift by number of homes and storeys;
  - 2.5.1 patio sizes (3 m circle and 9 m² for bedrooms, minus 10 %);
  - 2.6 a community room from 8 homes.
- PGM zoning gate as today, applied to the whole building.

## What NOMAD would do
1. **Find them**: a "warehouses and commercial buildings" layer on the city map, listing the candidates above with
   their zoning answer. Click one: footprint, storeys and area from Catastro, as for shops today.
2. **Single-storey warehouse (nau)**: cut patios into the roof so a deep hall gets light. Where the clear height allows
   two storeys of 2,40 m plus a floor (about 5,2 m or more), offer a mezzanine: duplexes, or a second floor of flats.
3. **Multi-storey building**: one shared core (stair and lift, placed by the 25 m rule and Annex 1 2.2/2.4), and real
   plans on every floor, the same plan stacked where it fits.
4. **Checks**: new rule cards for Annex 1 section 2 (Group B), each with its exact article from the rulebook.
5. **Website, Rhino and IFC**: a choice at step 1 (shop / warehouse / commercial building); storeys stacked in 3D.
6. Lab book and results page after each step, as usual.

## Order
- Step 1: candidates map.
- Step 2: Group B rule cards.
- Step 3: single-storey warehouses (patios and mezzanine).
- Step 4: multi-storey buildings (core and stacked floors).
- Step 5: website, Rhino, IFC.
Each step stops for your OK.

## Questions for you
1. Which first: single-storey warehouses (simplest, closest to what NOMAD does now) or office and commercial
   buildings?
2. Vacancy: use the census hint plus a list you give us? Or should I look for an official register of empty buildings
   (I would show you the link before downloading)?
3. 22@ buildings: include them as "check the 22@ plan", like shops today?
4. Storey heights: Catastro gives the number of storeys but not their height. Take 3,0 m per storey for office
   buildings and ask the user for a warehouse's clear height?
