"""Nomad - a rough value for the homes NOMAD fits in each empty shop, from open data.

Source: idealista18 (Rey-Blanco, Arbués, López, Páez 2024, Environment and Planning B; ODbL-1.0,
github.com/paezha/idealista18): 61,486 Barcelona sale listings of 2018 with asking price per m², floor and location.
For every empty premises of the 2024 census: the median asking price per m² of the listings within 500 m, and of the
ground-floor listings (floor 0, what a converted shop becomes) within 800 m. These are 2018 ASKING prices, not sale
prices or today's market: a first order of magnitude for an owner, to be updated with current data.
The cost of the works is not in open data: the website asks the user for a cost per m² (an architect's estimate).
Out: 8_report_and_city/output/value/premises_value.csv (ODbL: a database derived from idealista18 - keep the attribution and licence)
Run: .venv/Scripts/python 8_report_and_city/code/value.py
"""
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "8_report_and_city/input/value/raw/Barcelona_Sale.rda"
OUT = ROOT / "8_report_and_city/output/value"


def to_utm31(lat, lon):
    """WGS84 latitude/longitude -> ETRS89 / UTM zone 31N metres (same as the census and the Catastro)."""
    a, f, k0 = 6378137.0, 1 / 298.257222101, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat, lon = np.radians(lat), np.radians(lon)
    lon0 = math.radians(3.0)
    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    T, C, A = np.tan(lat) ** 2, ep2 * np.cos(lat) ** 2, np.cos(lat) * (lon - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * np.sin(2 * lat)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * np.sin(4 * lat) - (35 * e2 ** 3 / 3072) * np.sin(6 * lat))
    x = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000
    y = k0 * (M + N * np.tan(lat) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))
    return x, y


def near_median(px, py, lx, ly, val, r):
    """Median of val for the listings within r metres of each point (a grid of r-sized cells for speed)."""
    cell = {}
    for i, (x, y) in enumerate(zip(lx, ly)):
        cell.setdefault((int(x // r), int(y // r)), []).append(i)
    med, cnt = [], []
    for x, y in zip(px, py):
        cx, cy = int(x // r), int(y // r)
        idx = [i for dx in (-1, 0, 1) for dy in (-1, 0, 1) for i in cell.get((cx + dx, cy + dy), [])]
        idx = [i for i in idx if (lx[i] - x) ** 2 + (ly[i] - y) ** 2 <= r * r]
        med.append(round(float(np.median(val[idx]))) if len(idx) >= 5 else None)
        cnt.append(len(idx))
    return med, cnt


def main():
    import rdata, warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = rdata.read_rda(str(RAW))["Barcelona_Sale"]
    s = s[(s.UNITPRICE > 500) & (s.UNITPRICE < 20000) & (s.CONSTRUCTEDAREA >= 25)]
    lx, ly = to_utm31(s.LATITUDE.to_numpy(float), s.LONGITUDE.to_numpy(float))
    lx, ly = np.asarray(lx, float), np.asarray(ly, float)
    price = s.UNITPRICE.to_numpy(float)
    ground = (s.FLOORCLEAN.to_numpy(float) == 0)
    e = pd.read_csv(ROOT / "1_find_the_shops/output/zoning/empty_premises_zoning.csv")
    m_all, n_all = near_median(e.X_UTM_ETRS89.values, e.Y_UTM_ETRS89.values, lx, ly, price, 500.0)
    m_gr, n_gr = near_median(e.X_UTM_ETRS89.values, e.Y_UTM_ETRS89.values, lx[ground], ly[ground], price[ground], 800.0)
    out = pd.DataFrame({"ID_Global": e.ID_Global, "eur_m2_500m": m_all, "listings_500m": n_all, "eur_m2_ground_800m": m_gr,
                        "ground_listings_800m": n_gr})
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "premises_value.csv", index=False)
    print("listings used:", len(s), "| ground floor:", int(ground.sum()))
    print("premises with a price nearby:", out.eur_m2_500m.notna().sum(), "of", len(out), "| median €/m²:", out.eur_m2_500m.median(),
          "| ground-floor median €/m²:", out.eur_m2_ground_800m.median())


if __name__ == "__main__":
    main()
