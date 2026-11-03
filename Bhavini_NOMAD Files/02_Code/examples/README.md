# inbox — drop a plan here and NOMAD works on it

1. Put a plan drawing here: PNG, JPG or PDF (one floor, one shop).
2. Optional: a file with the same name + `.json` that says what you know and what you want:
   ```json
   {"known_facade_m": 9.9, "height": 2.6, "n_studio": 0, "n_1bed": 2, "n_2bed": 1, "n_3bed": 0, "compact": false}
   ```
   `known_facade_m` = length of the longest street façade (from the dimension lines). Without it the
   scale is guessed and is often about 50% off.
3. In Grasshopper (NOMAD.gh) switch on **run inbox**. Every new plan gets a sheet:
   `results/sheets/<name>.png` (the picture) and `<name>.json` (the numbers), drawn in Rhino on layer
   "05 NOMAD sheet".

A plan is done again only when you change it or its .json.
