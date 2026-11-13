# 6 · Check the shop

- **Input:** local CAT file and census CSV in ignored `nomad/02_Code/data/`, plus premises in `app/data/premises.json`.
- **Code:** `code/annex4_grup.py` derives the Annex 4 group for each shop.
- **Output:** `output/annex4_grup.json`; the local spot-check stays under ignored `nomad/02_Code/results/`.
- **Used by:** Bars's previous site. To refresh its bundled copy, run from repo root:

  `Copy-Item "Bars's files/6_check_the_shop/output/annex4_grup.json" "Bars's files/app/data/annex4_grup.json"`

  This is the one documented duplicate; the build script does not copy it automatically.
