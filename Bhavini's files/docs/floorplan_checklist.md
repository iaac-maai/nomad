# Floor plans: checklist (agreed 10 Nov 2026)

A. From footprints to real units
- [x] 1. Catastro unit list fetched (Consulta_DNPRC: floor, use, m² per unit): 5,330 buildings
- [x] 2. Shapes cut to the true area (2_building/code/shop_data.py (step 2), app/data/cut_shells.json): rule A 498, rule B 2,459, labelled assumed
- [x] 3. Every plan labelled by its source (site: basisRows / basisHtml): real plan / Catastro unit / building footprint / assumed shape, with each part (shape, hall and stair, light wells, windows, height) marked real or assumed; shown above the layouts, in Saved and Compare, and in the PDF report
- [x] 4. Building panel vs Design homes mismatch: Design homes now says why a building's unit plan was not used (app/data/unit_skips.json)
- [x] 5. Light wells (patis de llums) from Catastro building parts into the shop shapes (2_building/code/light_wells.py): 2,856 shops, 4,817 wells open to the sky; no flat over them (plan3, site engine); slivers under about a wall thickness pass. Still to do: count them for light and air; roofed wells (610 shops) kept as information
- [x] 6. Hall and stair where there is no plan: rule C (2_building/code/shop_data.py step 2b, app/data/cores.json), door to stair tower 93 % / light well 91 % / box 72 % on the right place; 2,942 buildings, labelled assumed. Backlog: per-building size

B. Facade into the plans (Av. Diagonal 413 first)
- [ ] 7. Ground floor split into its real shops: width from the arches, depth from the unit area; entrance arch = hall and stair
- [ ] 8. Real openings on the street wall in the plan generator (not 60 % glass)
- [ ] 9. Real heights; mezzanine check against MPGM 1999 art. 225 (2,50 m below and above)

C. Liveability (jury)
- [ ] 10. Privacy from the pavement for ground-floor homes
- [ ] 11. Use of the deep back part (storage, shared rooms, work)
- [ ] 12. Noise: service rooms on the street as a score, not a rule
- [ ] 13. Lofts / mezzanines: read MPGM 1999 art. 225 before adding

D. Team and sources
- [x] Census + land registry facts in Find your shop (status, offer, where, other premises, doors, year, floors, units) — app/data/facts/
- [ ] 14. Daylight sensor grid (jury) — Bars
- [ ] 15. Real plans for test buildings from Arxiu Municipal / COAC — requests by Bhavini

E. Later
- Facades on corner buildings (Bars first), facades read on click (backend), 3D facade, publishing (only when asked)
- Facade panel hidden in the app (SHOW_FACADE = false) until Bars's work
