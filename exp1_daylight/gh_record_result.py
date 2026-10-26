# Nomad - Experiment 1 - Grasshopper Script component: RECORD ONE RESULT
#
# Paste this code into a second Script component.
# Inputs (rename exactly like this):
#   out_path : text  - full path to exp1_daylight/results.csv (created automatically)
#   row_json : text  - from the "read variant" component
#   results  : numbers - "results" output of HB Daylight Factor
#              IMPORTANT: right-click this input -> set it to "List Access"
#   points   : points - "points" output of HB Sensor Grid from Rooms (optional)
#              IMPORTANT: also "List Access"
#   write    : bool  - a Boolean Toggle; True = save the row
# Output:
#   status   : what happened (connect a Panel)
#
# One row per variant id. If the same id is simulated again, its row is replaced.
# Works in IronPython 2.7 and Python 3.

import csv
import json
import os

status = "waiting: set write = True and run the simulation"

values = [float(v) for v in (results or []) if v is not None]

if write and row_json and values:
    row = json.loads(row_json)
    n = len(values)
    srt = sorted(values)
    row["mean_df"] = round(sum(values) / n, 3)
    row["median_df"] = round(srt[n // 2], 3)
    row["share_df2"] = round(sum(1 for v in values if v >= 2.0) / float(n), 3)
    row["n_sensors"] = n
    row["df_values"] = json.dumps([round(v, 2) for v in values])
    pts = list(points or [])
    row["xs"] = json.dumps([round(p.X, 2) for p in pts]) if len(pts) == n else ""
    row["ys"] = json.dumps([round(p.Y, 2) for p in pts]) if len(pts) == n else ""

    table = {}
    fields = list(row.keys())
    if os.path.exists(out_path):
        with open(out_path) as f:
            for r in csv.DictReader(f):
                table[r["id"]] = r
    table[str(row["id"])] = row

    with open(out_path, "w") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for key in sorted(table, key=lambda k: int(k)):
            w.writerow(dict((k, table[key].get(k, "")) for k in fields))
    status = "saved variant %s: mean DF %.2f %%, %.0f %% of floor >= 2 %% DF (%d rows in file)" % (
        row["id"], row["mean_df"], 100 * row["share_df2"], len(table))
elif write and not values:
    status = "no results yet: is _run on HB Daylight Factor set to True?"
