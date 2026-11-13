# Daylight outputs

`results.csv`, `results_shops.csv`, `shops_bcn.csv`, `shops_validation.csv`, and the variant CSVs are generated
or archived results used by the daylight code. `shops_validation.csv` contains `pred_mean_df`.

Git history confirms that Exp 4's XGBoost daylight model was later removed: commit `cb42307` is titled
“Remove the Exp 4 XGBoost daylight model and the daylight classes,” and removes `exp1_daylight/predict_shops.py`.
That script explicitly uses XGBoost's `XGBRegressor` to create `pred_mean_df` and writes the selected rows to
`shops_validation.csv`. The CSV was first added in commit `43d8afe`. So this column is from the old Exp 4 XGBoost
model, which was dropped after the jury.

Sources and licences for the source CSVs should be checked before publishing these outputs. Do not publish raw
Catastro or Visor data.
