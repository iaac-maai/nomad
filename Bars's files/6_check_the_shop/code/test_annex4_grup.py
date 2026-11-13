"""Tests for tools/annex4_grup.py on CAT records written by hand to the format's positions (no real Catastro data).
Run from the repo root:  python "Bars's files/6_check_the_shop/code/test_annex4_grup.py"
"""
import gzip
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import annex4_grup as A  # noqa: E402


def rec(kind, fields):
    r = [" "] * 1000
    r[0:2] = kind
    for start, (length, value) in fields.items():
        v = str(value).rjust(length, "0") if isinstance(value, int) else str(value).ljust(length)
        assert len(v) == length, (start, v)
        r[start - 1:start - 1 + length] = v
    return "".join(r)


def finca(ref, total, above, below):
    return rec("11", {31: (14, ref), 306: (7, total), 313: (7, above), 320: (7, below)})


def cons(ref, unit, floor, m2, uc="1", use="COM", door=""):
    return rec("14", {31: (14, ref), 51: (4, unit), 55: (4, uc), 65: (3, floor), 68: (3, door), 71: (3, use), 84: (7, m2)})


def unit(ref, cargo, use, floor="", door="", m2=0):
    return rec("15", {31: (14, ref), 45: (4, cargo), 252: (3, floor), 255: (3, door), 428: (1, use), 442: (10, m2)})


LINES = [
    # P1: a 100 m² shop in a 500 m² building -> 20 %, Grup C (the only candidate)
    finca("1111111AA1111A", 500, 500, 0), unit("1111111AA1111A", "0001", "C", "00", "01"),
    unit("1111111AA1111A", "0002", "V", "01", "01"), cons("1111111AA1111A", "0001", "00", 100),
    cons("1111111AA1111A", "0002", "01", 400, use="VIV"),
    # P2: a 300 m² shop (with 100 m² of basement) in a 500 m² building -> 60 %, Grup D
    finca("2222222AA2222A", 500, 400, 100), unit("2222222AA2222A", "0001", "C", "00", "01"),
    cons("2222222AA2222A", "0001", "00", 200), cons("2222222AA2222A", "0001", "-1", 100, use="ALM"),
    cons("2222222AA2222A", "0002", "01", 200, use="VIV"),
    # P3: two ground-floor shops, 100 and 400 m² of 600 -> 16,7 % (C) and 66,7 % (D): door decides, else unknown
    finca("3333333AA3333A", 600, 600, 0), unit("3333333AA3333A", "0001", "C", "00", "01"),
    unit("3333333AA3333A", "0002", "C", "00", "02"), cons("3333333AA3333A", "0001", "00", 100),
    cons("3333333AA3333A", "0002", "00", 400), cons("3333333AA3333A", "", "01", 100, use="ZCO"),
    # P4: two small shops, both Grup C (10 % and 20 %) -> "same"
    finca("4444444AA4444A", 1000, 1000, 0), unit("4444444AA4444A", "0001", "C", "00", "01"),
    unit("4444444AA4444A", "0002", "O", "00", "02"), cons("4444444AA4444A", "0001", "00", 100),
    cons("4444444AA4444A", "0002", "00", 200, use="OFI"), cons("4444444AA4444A", "0003", "01", 700, use="VIV"),
    # P5: a parcel with two buildings: the shop (150 m²) is in building 2 (200 m²) -> 75 % of its building, Grup D
    #     (of the whole 1 200 m² parcel it would be 12,5 %)
    finca("5555555AA5555A", 1200, 1200, 0), unit("5555555AA5555A", "0001", "C", "00", "01"),
    cons("5555555AA5555A", "0001", "00", 150, uc="2"), cons("5555555AA5555A", "0002", "01", 50, uc="2", use="VIV"),
    cons("5555555AA5555A", "0003", "00", 1000, uc="1", use="VIV"),
    # P6: 300 m² shop, 200 of them below ground, in 1 150 m² (250 below): 26 % whole (C), 80 % of the below-ground
    #     area (D if counted separately)
    finca("6666666AA6666A", 1150, 900, 250), unit("6666666AA6666A", "0001", "C", "00", "01"),
    cons("6666666AA6666A", "0001", "00", 100), cons("6666666AA6666A", "0001", "-1", 200, use="ALM"),
    cons("6666666AA6666A", "0002", "01", 850, use="VIV"),
]


def main():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "08_900_U_test.CAT.gz"
        with gzip.open(path, "wt", encoding="latin-1", newline="") as fh:
            fh.write("\r\n".join(LINES) + "\r\n")
        P = A.open_cat(path)
    checks = []

    def ok(name, cond):
        checks.append(cond)
        print(("PASS " if cond else "FAIL ") + name)

    r = A.classify(P, "1111111AA1111A", "")
    ok("P1 only candidate, 20 % -> C", r["grup"] == "C" and r["method"] == "only" and abs(r["ratio"] - 0.2) < 1e-9)
    r = A.classify(P, "2222222AA2222A", "")
    ok("P2 shop with basement, 60 % -> D", r["grup"] == "D" and abs(r["ratio"] - 0.6) < 1e-9 and r["shop_below_m2"] == 100)
    r = A.classify(P, "3333333AA3333A", "02")
    ok("P3 door 02 picks the 400 m² unit -> D", r["grup"] == "D" and r["method"] == "door" and r["cargo"] == "0002")
    r = A.classify(P, "3333333AA3333A", "1")
    ok("P3 door '1' matches '01' -> C", r["grup"] == "C" and r["cargo"] == "0001")
    r = A.classify(P, "3333333AA3333A", "30")
    ok("P3 no door match, groups differ -> unknown", r["grup"] == "unknown" and r.get("candidates") == 2)
    r = A.classify(P, "4444444AA4444A", "")
    ok("P4 two candidates, both C -> same, 10-20 %", r["grup"] == "C" and r["method"] == "same"
       and abs(r["ratio"] - 0.1) < 1e-9 and abs(r["ratio_max"] - 0.2) < 1e-9)
    r = A.classify(P, "5555555AA5555A", "")
    ok("P5 two buildings: shop's own building, 75 % -> D", r["grup"] == "D" and r["denominator"] == "building"
       and r["building_m2"] == 200)
    r = A.classify(P, "6666666AA6666A", "")
    ok("P6 whole building 26 % -> C; separately 80 % below -> D", r["grup"] == "C" and r["grup_separately"] == "D")
    ok("P7 parcel not in the file -> unknown", A.classify(P, "7777777AA7777A", "")["grup"] == "unknown")
    ok("residential units are never the shop", all(k != "0002" for k in [A.classify(P, "1111111AA1111A", "01").get("cargo")]))
    print(f"\n{sum(checks)} of {len(checks)} passed")
    sys.exit(0 if all(checks) else 1)


if __name__ == "__main__":
    main()
