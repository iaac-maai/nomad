# Doors and census facts per building (Bhavini, 11 Nov 2026)

Made by `nomad/02_Code/src/building/shop_data.py` (step 1 doors, step 3 facts, step 4 the licence-safe copy). Every
file is keyed by the 14-character cadastral reference (`ref14`) used in `04_Website/data/premises.json`.
Coordinates are local metres from the building's origin (`o` in `doors.json`, ETRS89 / UTM 31N).

| File | What it holds |
|---|---|
| `doors.json` | `{ref14: {o: [x, y] UTM origin, entr: [[x, y, street number]], doors: [[x, y, "empty" \| "active"]]}}` — building entrances (Catastro INSPIRE Addresses, points marked "Entrance"; 3,479 of 5,322 buildings) and every premises door (census 2024). |
| `facts/f_XX.json` | `{ref14: {c, up, down}}` by the first two characters of the reference. `c`: every premises of the building in the census `[x, y, address, empty/active, sector or offer, activity, flags]` (flags: street, market:, gallery:, centre:, axis: shopping street, night, 24h, coworking, tasting). `up` / `down`: floors above / below ground (Catastro INSPIRE building parts, highest part). |

Not here yet: the shop shapes cut to their true size (rules A and B) and the units per building. Their unit list came
from the Catastro's Consulta_DNPRC web service (Sede legal notice: private use only), so they will be rebuilt from the
CAT file (download licence) before they are added.

Transformed for the Catastro INSPIRE licence: points rounded to 0,5 m in local metres. The census is kept as it is
(CC BY 4.0).

Sources and licences: Cens d'activitats econòmiques en planta baixa 2024, Ajuntament de Barcelona (Open Data BCN, CC BY 4.0);
Dirección General del Catastro, INSPIRE Addresses and Buildings (INSPIRE licence, transformed data, cite the DGC).
