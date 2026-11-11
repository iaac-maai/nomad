# Shop shapes, doors and facts per building (Bhavini, 11 Nov 2026)

Made by `tools/shop_data.py` (step 0 units from the CAT file, step 1 doors, step 2 shapes, step 3 facts, step 4 this licence-safe copy). Every
file is keyed by the 14-character cadastral reference (`ref14`) used in `04_Website/data/premises.json`.
Coordinates are local metres from the building's origin (`o` in `doors.json`, ETRS89 / UTM 31N).

| File | What it holds |
|---|---|
| `cut_shells.json` | `{"ref14\|x\|y": {outline, facade, street, m2, rule, why, units, patios}}` — each empty premises' shape cut to its true size. **Assumed**, not surveyed. Rule A: one shop unit on the ground floor, the part behind the door kept as deep as the unit's area. Rule B: several shop units, the street front shared between the census doors, area within the units' sizes. 2,931 premises (501 A, 2,470 B). `x\|y` = the premises' census point as in `premises.json`. |
| `doors.json` | `{ref14: {o: [x, y] UTM origin, entr: [[x, y, street number]], doors: [[x, y, "empty" \| "active"]]}}` — building entrances (Catastro INSPIRE Addresses, points marked "Entrance"; 3,479 of 5,322 buildings) and every premises door (census 2024). |
| `facts/f_XX.json` | `{ref14: {c, up, down, n}}` by the first two characters of the reference. `c`: every premises of the building in the census `[x, y, address, empty/active, sector or offer, activity, flags]` (flags: street, market:, gallery:, centre:, axis: shopping street, night, 24h, coworking, tasting). `up` / `down`: floors above / below ground (Catastro INSPIRE building parts, highest part). `n`: number of Catastro units by use (CAT file). |

Units come from the Catastro CAT file (Barcelona urban, 08900U_14082026.CAT.gz, accessed 11 Nov 2026), never from the
Sede's Consulta_DNPRC web service or the Visor 3D (private use only).

Transformed for the Catastro licences: outlines and points rounded to 0,5 m in local metres, cut areas to 10 m², reasons without unit sizes, units reduced to counts by use (no areas, years or floor lists). The census is kept as it is
(CC BY 4.0).

Sources and licences: Cens d'activitats econòmiques en planta baixa 2024, Ajuntament de Barcelona (Open Data BCN, CC BY 4.0);
Dirección General del Catastro: INSPIRE Addresses and Buildings (INSPIRE licence) and the alphanumeric CAT file (download licence, clauses 6 and 12), transformed, accessed 11 Nov 2026.
