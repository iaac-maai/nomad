"""Nomad - estimated floor and clear heights from ICGC Territorial LiDAR v3.1 (2021-2023, CC BY 4.0) and the Catastro floor count.
Each 1 km tile is downloaded, reduced to two 1 m grids (top of building points, ground points) and the 300 MB file is removed.
Roof above the street / floors = average floor height; minus SLAB = average clear height. An estimate, never a measurement.
Run: .venv/Scripts/python src/building/lidar_heights.py grids [workers], then .venv/Scripts/python src/building/lidar_heights.py heights
Out: data/lidar/grid/*.npz, results/heights/heights.csv
"""
import csv, json, os, sys, time, urllib.request
from multiprocessing import Pool
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GRID, TMP, OUT = ROOT / "data/lidar/grid", ROOT / "data/lidar/tmp", ROOT / "results/heights"
BASE = "https://datacloud.icgc.cat/datacloud/lidar-territorial/laz_unzip/full10km%02d%02d/lidar-territorial-v3r1-full1km%03d%03d-2021-2023.laz"
SLAB = 0.30      # our assumption, not law: slab and finishes
LOW = 7.0        # a roof under 7 m above the street is a low roof over this floor


def shells():
    for path, kind in (("results/real_shops/shells.json", "shop"), ("results/warehouses/shells.json", None)):
        for ref, s in json.load(open(ROOT / path, encoding="utf-8")).items():
            ox, oy = s["origin_utm"]
            yield ref, kind or s["kind"], s, [(q[0] + ox, q[1] + oy) for q in s["outline"]]


def tile(job):
    import laspy
    e, n = job
    out = GRID / ("%03d%03d.npz" % (e, n))
    if out.exists():
        return job, "have"
    url, tmp = BASE % (e // 10, n // 10, e, n), TMP / ("%03d%03d.laz" % (e, n))
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(url, tmp)
            break
        except urllib.error.HTTPError as err:
            if err.code == 404:
                np.savez_compressed(out, none=np.zeros(1))
                return job, "no tile"
            time.sleep(5)
        except Exception:
            time.sleep(5)
    else:
        return job, "failed"
    top, gnd = np.full((1000, 1000), np.nan, "f4"), np.full((1000, 1000), np.nan, "f4")
    with laspy.open(str(tmp)) as r:                    # in small pieces: a whole tile would take over 1 GB of memory
        for L in r.chunk_iterator(2000000):
            x, y, z, c = np.asarray(L.x), np.asarray(L.y), np.asarray(L.z), np.asarray(L.classification)
            ix, iy = np.clip((x - e * 1000).astype(int), 0, 999), np.clip((y - (4000 + n) * 1000).astype(int), 0, 999)
            b = c == 6
            np.fmax.at(top, (ix[b], iy[b]), z[b].astype("f4"))
            g = c == 2
            np.fmin.at(gnd, (ix[g], iy[g]), z[g].astype("f4"))
    np.savez_compressed(out, top=top, gnd=gnd)
    tmp.unlink()
    return job, "ok"


def grids(workers):
    GRID.mkdir(parents=True, exist_ok=True); TMP.mkdir(parents=True, exist_ok=True)
    need = set()
    for _, _, _, p in shells():
        a = np.array(p)
        for e in range(int((a[:, 0].min() - 30) // 1000), int((a[:, 0].max() + 30) // 1000) + 1):
            for n in range(int((a[:, 1].min() - 30) // 1000), int((a[:, 1].max() + 30) // 1000) + 1):
                need.add((e, n - 4000))
    jobs = sorted(need)
    print(len(jobs), "tiles", flush=True)
    t = time.time(); seen = {}
    with Pool(workers) as pool:
        for i, (job, st) in enumerate(pool.imap_unordered(tile, jobs)):
            seen[st] = seen.get(st, 0) + 1
            print(i + 1, job, st, round(time.time() - t), seen, flush=True)


def heights():
    from matplotlib.path import Path as P
    cache = {}
    def load(e, n):
        if (e, n) not in cache:
            f = GRID / ("%03d%03d.npz" % (e, n)); d = np.load(f) if f.exists() else {}
            cache[(e, n)] = (d["top"], d["gnd"]) if "top" in d else None
            if len(cache) > 40:
                cache.pop(next(iter(cache)))
        return cache[(e, n)]
    def window(p, m=0):
        a = np.array(p)
        x0, x1, y0, y1 = int(a[:, 0].min()) - m, int(a[:, 0].max()) + 1 + m, int(a[:, 1].min()) - m, int(a[:, 1].max()) + 1 + m
        T, G = np.full((x1 - x0, y1 - y0), np.nan, "f4"), np.full((x1 - x0, y1 - y0), np.nan, "f4")
        for e in range(x0 // 1000, (x1 - 1) // 1000 + 1):
            for n in range(y0 // 1000, (y1 - 1) // 1000 + 1):
                d = load(e, n - 4000)
                if d is None:
                    continue
                a0, a1, b0, b1 = max(x0, e * 1000), min(x1, (e + 1) * 1000), max(y0, n * 1000), min(y1, (n + 1) * 1000)
                T[a0 - x0:a1 - x0, b0 - y0:b1 - y0] = d[0][a0 - e * 1000:a1 - e * 1000, b0 - n * 1000:b1 - n * 1000]
                G[a0 - x0:a1 - x0, b0 - y0:b1 - y0] = d[1][a0 - e * 1000:a1 - e * 1000, b0 - n * 1000:b1 - n * 1000]
        return T, G, x0, y0
    OUT.mkdir(parents=True, exist_ok=True)
    F = ["ref", "kind", "floors", "m2", "roof_cover", "street_z", "roof_p25", "roof_p50", "roof_p75", "low_share", "floor_h", "clear_h", "low_roof_h", "status"]
    n, c = 0, {}
    with open(OUT / "heights.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, F); w.writeheader()
        for ref, kind, s, p in shells():
            T, G, x0, y0 = window(p, 25)
            xs, ys = np.meshgrid(np.arange(T.shape[0]) + x0 + .5, np.arange(T.shape[1]) + y0 + .5, indexing="ij")
            m = P(p).contains_points(np.c_[xs.ravel(), ys.ravel()]).reshape(xs.shape)
            r = T[m]; r = r[~np.isnan(r)]; g = G[~np.isnan(G)]
            row = dict(ref=ref, kind=kind, floors=s.get("floors") or "", m2=int(m.sum()), roof_cover=round(len(r) / max(int(m.sum()), 1), 2))
            if len(r) < 8 or len(g) < 8:
                row["status"] = "no lidar"
            else:
                g0 = float(np.median(g)); h = r - g0
                a, b, d = [round(float(np.percentile(h, q)), 1) for q in (25, 50, 75)]
                lows = h[(h >= 2.5) & (h < LOW)]
                fl = s.get("floors") or 0
                row.update(street_z=round(g0, 1), roof_p25=a, roof_p50=b, roof_p75=d, low_share=round(float(np.mean(h < LOW)), 2), status="estimate")
                if fl >= 1 and d >= 2.5 * fl * .8:
                    row["floor_h"] = round(d / fl, 2); row["clear_h"] = round(d / fl - SLAB, 2)
                else:
                    row["status"] = "floors and roof disagree"
                if len(lows) >= 8 and row["low_share"] >= .3:
                    row["low_roof_h"] = round(float(np.median(lows)), 1)
            w.writerow(row); n += 1; c[row["status"]] = c.get(row["status"], 0) + 1
    print(n, c)


def export():
    """site/data/heights.json {ref|kind: metres}: what the site's height box starts at. Shops and warehouses: clear height;
    commercial and office: one storey, floor to floor. Left out, so the default stays: no reading, floors and roof disagree,
    and readings outside 2 to 8 m clear (nearly all a wrong floor count)."""
    out = {}
    for r in csv.DictReader(open(OUT / "heights.csv", encoding="utf-8")):
        if r["status"] == "estimate" and 2.0 <= float(r["clear_h"]) <= 8.0:
            out[r["ref"] + "|" + r["kind"]] = float(r["clear_h"] if r["kind"] in ("shop", "warehouse") else r["floor_h"])
    json.dump(out, open(ROOT / "site" / "data" / "heights.json", "w"), separators=(",", ":"))
    print("heights.json", len(out))


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export()
    elif sys.argv[1] == "grids":
        grids(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        heights()
