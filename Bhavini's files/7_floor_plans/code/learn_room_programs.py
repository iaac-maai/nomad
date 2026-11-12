"""Nomad - learn room programs from real flats that pass every Nomad rule (Swiss Dwellings).

"Training" here means measuring: for flats with 0, 1, 2 and 3 bedrooms that pass all 9 rules,
what are the typical sizes of the living room, each bedroom, the bathroom, the kitchen and the
circulation? The generator uses these medians as its targets, and the 25th percentile as the
smallest size it will still try, so every generated room size is one that real, rule-passing
flats actually have.
Output: 7_floor_plans/output/generation/room_programs.json
"""
import json, os
import pandas as pd

OUT = "7_floor_plans/output/generation"
BED = {"BEDROOM", "ROOM"}
LIV = {"LIVING_ROOM", "LIVING_DINING", "KITCHEN_DINING", "DINING"}
KIT = {"KITCHEN"}
BATH = {"BATHROOM", "SANITARY_ROOMS", "TOILET"}
CIRC = {"CORRIDOR", "CORRIDORS_AND_HALLS", "STOREROOM", "LOBBY"}
NAMES = {0: "studio", 1: "1bed", 2: "2bed", 3: "3bed"}


def main():
    os.makedirs(OUT, exist_ok=True)
    U = pd.read_csv("4_laws_and_rules/output/rule_tests/sd_units.csv")
    R = pd.read_csv("4_laws_and_rules/output/rule_tests/sd_rooms.csv")
    ok = U[(U.usage == "RESIDENTIAL") & U.all_pass & (U.bedrooms <= 3)]
    R = R[R.unit_id.isin(ok.unit_id)]
    rows = []
    for uid, g in R.groupby("unit_id"):
        beds = g[g.type.isin(BED)].area_m2.sort_values(ascending=False).tolist()
        liv = g[g.type.isin(LIV)].area_m2.sum()
        if liv == 0 and beds:                      # unlabelled flat: largest room is the living room
            liv = beds.pop(0)
        rows.append({"unit_id": uid, "bedrooms": len(beds), "living": liv,
                     "bed_max": beds[0] if beds else None, "bed_min": beds[-1] if beds else None,
                     "kitchen": g[g.type.isin(KIT)].area_m2.sum(), "bath": g[g.type.isin(BATH)].area_m2.sum(),
                     "baths": int(g.type.isin(BATH).sum()), "circulation": g[g.type.isin(CIRC)].area_m2.sum()})
    df = pd.DataFrame(rows).merge(ok[["unit_id", "useful_m2"]], on="unit_id")
    programs = {}
    for b, name in NAMES.items():
        g = df[df.bedrooms == b]
        if len(g) < 30:
            continue
        q = lambda c, p: round(float(g[c].quantile(p)), 1)
        programs[name] = {
            "bedrooms": b, "flats_learned_from": int(len(g)),
            "useful_m2": {"p25": q("useful_m2", .25), "median": q("useful_m2", .5), "p75": q("useful_m2", .75)},
            "living_m2": {"p25": q("living", .25), "median": q("living", .5)},
            "main_bedroom_m2": {"p25": q("bed_max", .25), "median": q("bed_max", .5)} if b else None,
            "other_bedroom_m2": {"p25": q("bed_min", .25), "median": q("bed_min", .5)} if b > 1 else None,
            "kitchen_m2": {"p25": q("kitchen", .25), "median": q("kitchen", .5)},
            "bath_m2": {"p25": q("bath", .25), "median": q("bath", .5)},
            "baths_median": int(g.baths.median()),
            "circulation_m2": {"p25": q("circulation", .25), "median": q("circulation", .5)},
        }
    with open(f"{OUT}/room_programs.json", "w", encoding="utf-8") as f:
        json.dump({"source": "Swiss Dwellings v3.0.0 flats that pass all 9 Nomad rules", "programs": programs}, f, indent=1)
    for k, v in programs.items():
        print(f"{k:6} from {v['flats_learned_from']:5} flats | useful {v['useful_m2']['median']} m2 | living {v['living_m2']['median']} | "
              f"bed {v['main_bedroom_m2'] and v['main_bedroom_m2']['median']} / {v['other_bedroom_m2'] and v['other_bedroom_m2']['median']} | "
              f"kitchen {v['kitchen_m2']['median']} | bath {v['bath_m2']['median']} | circ {v['circulation_m2']['median']}")


if __name__ == "__main__":
    main()
