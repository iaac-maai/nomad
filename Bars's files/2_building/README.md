# 2 · Building

- **Input:** local Catastro source data in ignored `nomad/02_Code/data/`.
- **Code:** `code/transform_catastro.py` converts the building source for Bars's previous site.
- **Output:** building data in `app/data/`.
- **Used by:** Bars's previous website. Raw Catastro files stay local and are never committed.
