# AI use log

IAAC asks us to declare every AI tool we use. Add one row each time.

| Date | Who | Tool | What for | What we kept |
| --- | --- | --- | --- | --- |
| 2026-10-26 | | Claude | Starter kit scripts for experiments 1 and 2 | Scripts in exp1_daylight/ and exp2_rules/, reviewed by the team |
| 2026-10-27 | Bars | Claude | Debugging Grasshopper/Honeybee setup, switching Exp 1 to ground-floor shops, training script | Scripts and settings, reviewed by Bars |
| 2026-10-27 | Bars | Gemini 3.5 Flash Lite (API) | Drafting 10 rule cards x 5 runs from Decret 141/2012 (Exp 2) | Drafts only, scored against human gold cards |
| 2026-10-28 | Bars | Google Translate | Translating Decret 141/2012 from Catalan to write the gold cards | Nothing kept; gold cards checked against the Catalan PDF |
| 2026-10-28 | Bars | open-notebook + Gemini embeddings | Vector search over Decret 141/2012 (Exp 2c) | Search results used as excerpts for the rule cards |
| 2026-10-28 | Bars | Claude | Code for real-shop data (shops_from_catastro.py, predict_shops.py, map_shops.py), hypercadaster_ES setup, slide deck | Scripts, maps and slides, reviewed by Bars; 5 shops checked in Grasshopper/Radiance (mean error 0.27 DF) |
| 2026-10-28 | Bars | XGBoost (Exp 1 model) | Predicting daylight for 1,376 empty Eixample shops (Catastro via hypercadaster_ES, Open Data BCN census) | Predictions marked v0; only 4 % of shops inside the training range |
| 2026-11-01 | Bars | Claude | Street-width fix (ray from the street facade), EN 17037 thresholds from the Barcelona TMYx weather file (climate.onebuilding.org), lit-depth model and livability classes | Scripts and results reviewed by Bars; lit depth checked on 5 shops against Radiance (mean error 0.55 m) |