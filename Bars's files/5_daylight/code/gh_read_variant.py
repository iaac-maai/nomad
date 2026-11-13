# Nomad - Experiment 1 - Grasshopper Script component: READ ONE VARIANT
#
# Paste this code into a Grasshopper "Script" component (Rhino 8) or a "GhPython Script" component.
# Inputs  (right-click each input to rename it exactly like this):
#   csv_path : text  - full path to Bars's files/5_daylight/output/variants.csv
#   i        : int   - which variant (connect a Number Slider, 0 to 49, integers)
# Outputs:
#   box        : the factory floor as a closed box (connect to HB Room from Solid -> _geo)
#   shade      : the building opposite (connect to HB Shade -> _geo); empty when there is none
#   ratios     : window ratio per direction N, E, S, W (connect to HB Apertures by Ratio -> _ratio)
#   win_height : window height in m (-> _win_height_)
#   sill       : sill height in m (-> _sill_height_)
#   row_json   : all parameters of this variant as text (connect to the recorder component)
#   info       : a short readable summary (connect a Panel to see it)
#
# Geometry: the street facade is the south side (y = 0). With lit_facades = 2 the north side
# (y = depth) also gets windows. Units: metres (use a Rhino template in metres).
# Works in IronPython 2.7 and Python 3.

import csv
import json
import Rhino.Geometry as rg


def read_row(path, idx):
    with open(path) as f:
        for r in csv.DictReader(f):
            if int(r["id"]) == int(idx):
                return r
    raise ValueError("variant %s not found in %s" % (idx, path))


row = read_row(csv_path, i)
W = float(row["width_m"])
D = float(row["depth_m"])
H = float(row["floor_height_m"])
wwr = float(row["wwr"])
lit = int(row["lit_facades"])
obs_d = float(row["obs_dist_m"])
obs_h = float(row["obs_height_m"])

box = rg.Box(rg.Plane.WorldXY, rg.Interval(0, W), rg.Interval(0, D), rg.Interval(0, H)).ToBrep()

# window ratio per cardinal direction: [north, east, south, west]
ratios = [wwr if lit == 2 else 0.0, 0.0, wwr, 0.0]
win_height = float(row["win_height_m"])
sill = float(row["sill_m"])

shade = None
if obs_h > 0.5:
    shade = rg.Box(rg.Plane.WorldXY, rg.Interval(-20, W + 20),
                   rg.Interval(-(obs_d + 10), -obs_d), rg.Interval(0, obs_h)).ToBrep()

row_json = json.dumps(row)
info = "variant %s | %.1f x %.1f m, h %.1f m | wwr %.2f | lit facades %d | opposite %.0f m high at %.0f m" % (
    row["id"], W, D, H, wwr, lit, obs_h, obs_d)
