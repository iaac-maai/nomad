# What makes a flat habitable: rules learned from 13,444 real flats (2026-11-01)

Source: Swiss Dwellings v3.0.0 (CC BY 4.0), the 13,444 flats (0-3 bedrooms) that pass every NOMAD rule.
Code: src/learn/habitability.py -> results/habitability/units.csv, rooms.csv; src/learn/habitability_summary.py -> summary.json.
Numbers: median (10th-90th percentile). These are design targets from real plans, not law.

## 1. Use the whole floor
- Useful floor split (2-bed): living 33 %, bedrooms 35 %, kitchen 10 %, bath 7 %, circulation 12 %.
- Circulation: 12 % of the flat (6-18 %); about 9 m² per flat (3.7-15). Studios 7 %, 3-beds 12 %.
- Leftover scraps (rooms under 2 m² that are not a bath or a store): 0.03 per flat. Real plans have almost none.

## 2. The entrance
- The front door opens into a hall or corridor in 85 % of flats (into the living room 6 %).
- It comes from a common stair (42 %) or common corridor (44 %). Straight from outside only 4 % (ground floor: 11 %).

## 3. Circulation that serves, not splits
- Every room is reached from the hall: bedrooms 78 %, baths 81 %, living 82 %.
- Bedrooms through the living room: 10 %. A bath through a bedroom: 4 %. A bedroom through another bedroom: 1 %.
- Hall clear width 1.75 m (1.21-2.51); never narrower than about 1.2 m.

## 4. Light
- Living rooms and bedrooms sit on the façade (95 %). Kitchens 77 %. Baths and stores are inside (on façade 45 % / 33 %).
- Window per room (median): living 3.1 m, bedroom 2.0 m, kitchen 1.65 m.
- The flat reaches 6.0 m from its windows (4.5-8.0).

## 5. Room shapes (clear width = widest circle that fits)
| room | area m² | clear width m | long / short |
|---|---|---|---|
| living | 27.8 (18.5-38.3) | 4.0 (3.5-4.7) | 1.4 |
| bedroom | 14.0 (10.3-17.6) | 3.2 (2.5-3.8) | 1.4 |
| kitchen | 7.7 (5.6-12.0) | 2.3 (1.8-2.8) | 1.5 |
| bath | 3.8 (1.8-5.5) | 1.6 (1.1-1.9) | 1.4 |
Rooms are near-rectangles (fill 0.9-1.0 of their bounding rectangle) and never long strips.

## 6. Services
- The kitchen opens off the living room in 35 % of flats, off the hall in 56 %.
- Kitchen and bath share a wall (one wet core) in 47 %. Doors 7 per flat, 0.84 m wide.

## NOMAD's plans against these (5 demo shops, 24 flats)
| | real flats | NOMAD now |
|---|---|---|
| circulation share | 12 % | 16 % |
| hall clear width | 1.75 m (never < 1.2) | 1.10 m |
| kitchen clear width | 2.3 m (>= 1.8) | 1.6 m |
| 2nd bedroom clear width | 3.2 m (>= 2.5) | 2.2 m |
| shop floor left unused | almost none | 34 % |
| front door | into a hall, from a common stair or corridor | from the street, straight into the flat |
