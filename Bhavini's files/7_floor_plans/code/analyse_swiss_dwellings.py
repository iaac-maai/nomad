"""Nomad - analyse the rule test on Swiss Dwellings (output of check_swiss_dwellings.py).
Writes 4_laws_and_rules/output/rule_tests/analysis.md (tables you can paste into a presentation) and prints the key numbers."""
import json
import pandas as pd

U = pd.read_csv("4_laws_and_rules/output/rule_tests/sd_units.csv")
R = pd.read_csv("4_laws_and_rules/output/rule_tests/sd_rooms.csv")
S = json.load(open("4_laws_and_rules/output/rule_tests/sd_summary.json", encoding="utf-8"))
RULES = S["rules"]
SHELL = ["r_useful_40", "r_height_250", "r_windows_1_8", "r_facade_s9"]   # rules a bare commercial shell can be tested on

out = ["# Nomad rulebook test on Swiss Dwellings v3.0.0", "",
       "Source: Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0). Rules: Decret 141/2012 Annex 1 + Barcelona MPGM 2004.",
       "This is a stress test (Swiss plans, Catalan rules), not an accuracy score: the dataset has no legal labels.", ""]

res = U[U.usage == "RESIDENTIAL"]
out += [f"## 1. Residential: {len(res):,} apartments, {len(R[R.usage == 'RESIDENTIAL']):,} rooms", "",
        "| Rule | Pass rate | Fails |", "|---|---|---|"]
for k, txt in RULES.items():
    out.append(f"| {txt} | {res[k].mean():.1%} | {(~res[k]).sum():,} |")
out += ["", f"**All 9 rules pass: {res.all_pass.mean():.1%}** of apartments.", ""]

fail_counts = (~res[list(RULES)]).sum().sort_values(ascending=False)
out += ["Most common reason a flat fails: " + ", ".join(f"`{k}` ({v:,})" for k, v in fail_counts.head(3).items()), ""]

by_bed = res.groupby(res.bedrooms.clip(upper=4)).agg(units=("all_pass", "size"), all_pass=("all_pass", "mean"),
                                                     median_m2=("useful_m2", "median"))
out += ["### By number of bedrooms (4 = 4 or more)", "", "| Bedrooms | Units | Median useful m² | All rules pass |", "|---|---|---|---|"]
for b, r in by_bed.iterrows():
    out.append(f"| {b} | {int(r.units):,} | {r.median_m2:.0f} | {r.all_pass:.1%} |")

com = U[U.usage == "COMMERCIAL"].copy()
com["shell_ok"] = com[SHELL].all(axis=1)
out += ["", f"## 2. Commercial units: {len(com):,} (the Nomad case: could this local become housing?)", "",
        "A shop has no bedrooms yet, so only the rules a bare shell can meet are tested:", "",
        "| Rule | Pass rate |", "|---|---|"]
for k in SHELL:
    out.append(f"| {RULES[k]} | {com[k].mean():.1%} |")
out += ["", f"**Shell passes all 4: {com.shell_ok.mean():.1%}** ({com.shell_ok.sum()} of {len(com)}) - candidates for conversion.", ""]
com["dwellings_80"] = (com.useful_m2 / 0.8 / 80).apply(lambda x: int(-(-x // 1)))   # built ≈ useful / 0.8
out += [f"If converted, the Barcelona density rule (built / 80 m²) would allow about "
        f"{com[com.shell_ok].dwellings_80.sum()} dwellings in the {com.shell_ok.sum()} candidate shells "
        "(assuming useful = 80% of built).", ""]

rr = R[R.usage == "RESIDENTIAL"]
beds = rr[rr.type.isin(["BEDROOM", "ROOM"])]
out += ["## 3. Room-level facts", "",
        f"- Bedrooms: {len(beds):,}; median {beds.area_m2.median():.1f} m²; under 6 m²: {(beds.area_m2 < 6).sum():,}; "
        f"no 2,00 m square: {(beds.square_200 == False).sum():,}",
        f"- Window ratio (glazing 0-2,5 m / floor area), bedrooms: median {beds.window_ratio.median():.2f} "
        f"(rule: ≥ 0,125); below 1/8: {(beds.window_ratio < 0.125).mean():.1%}",
        "",
        "## 4. Method notes (limits)", "",
        "- Useful area = all rooms except balconies, loggias, shafts, stairs, lifts, voids, basements (Decret 141 'superfície útil').",
        "- 2,00 / 2,60 m square: room eroded with a square-corner buffer (exact for rooms with walls parallel to the square).",
        "- Windows: each window polygon is linked to the rooms it touches (0,45 m search across the wall); only glazing "
        "between 0 and 2,5 m above that room's floor counts (Decret 141 3.9.1). A window shared by two rooms counts for both.",
        "- Façade S/9 uses total window width as a strict proxy for façade length: real façade is longer, so this rule "
        "under-reports passes.",
        "- ROOM (unlabelled room) is treated as a bedroom; when no room is labelled living, the largest one is tested for the 2,80 m circle."]

with open("4_laws_and_rules/output/rule_tests/analysis.md", "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("\n".join(out))
