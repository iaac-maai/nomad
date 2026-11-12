"""Nomad - every unit of every parcel from the Catastro's public, non-protected service (Consulta_DNPRC): floor, door, use,
built m2, year. It gives each premises' true size, not its shape. Protected data (owner, value) is not in this service.
In: the parcels in 1_find_the_shops/output/zoning/catastro_plans.json. Three requests at a time, stops on 10 errors in a row, resumable.
Out: private/catastro_units_DNPRC.jsonl  {"ref", "n", "units": [{"car", "pt", "pu", "es", "use", "m2", "year"}]} or {"ref", "error"}
Run: .venv/Scripts/python 2_building/code/catastro_units.py [limit]
"""
import json, sys, time
from multiprocessing.pool import ThreadPool
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "private/catastro_units_DNPRC.jsonl"
URL = "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPRC"
HEAD = {"User-Agent": "NOMAD student project (IAAC Barcelona); three requests at a time"}
PAUSE = 0.5
WORKERS = 3


def _row(rc, dt, de):
    i = ((dt.get("locs") or {}).get("lous") or {}).get("lourb", {}).get("loint") or {}
    return {"car": rc.get("car"), "pt": i.get("pt"), "pu": i.get("pu"), "es": i.get("es"), "use": de.get("luso"),
            "m2": float(de["sfc"]) if de.get("sfc") else None, "year": de.get("ant")}


def parse(d):
    r = d["consulta_dnprcResult"]
    if (r.get("control") or {}).get("cuerr"):
        return None, json.dumps(r.get("lerr"), ensure_ascii=False)[:200]
    if r.get("bico"):
        b = r["bico"]["bi"]
        return [_row(b["idbi"]["rc"], b["dt"], b.get("debi") or {})], None
    x = r["lrcdnp"]["rcdnp"]
    return [_row(u["rc"], u["dt"], u.get("debi") or {}) for u in (x if isinstance(x, list) else [x])], None


def one(ref):
    try:
        t = requests.get(URL, params={"RefCat": ref}, headers=HEAD, timeout=60)
        t.raise_for_status()
        us, err = parse(t.json())
        row = {"ref": ref, "n": len(us), "units": us} if us is not None else {"ref": ref, "error": err}
    except Exception as e:
        row = {"ref": ref, "error": str(e)[:200]}
    time.sleep(PAUSE)
    return row


def main(limit=None):
    refs = sorted(json.load(open(ROOT / "1_find_the_shops/output/zoning/catastro_plans.json", encoding="utf-8")))
    done = set()
    if OUT.exists():
        for l in open(OUT, encoding="utf-8"):
            r = json.loads(l)
            if "units" in r:
                done.add(r["ref"])                       # errors are tried again on the next run
    todo = [r for r in refs if r not in done][: limit or None]
    print("parcels %d, done %d, to do %d" % (len(refs), len(done), len(todo)), flush=True)
    bad = run = 0
    with open(OUT, "a", encoding="utf-8") as f, ThreadPool(WORKERS) as pool:
        for k, row in enumerate(pool.imap_unordered(one, todo), 1):
            bad += "error" in row
            run = run + 1 if "error" in row else 0
            f.write(json.dumps(row, ensure_ascii=False) + chr(10)); f.flush()
            if run >= 10:                            # the service is pushing back: stop, the next run resumes
                print("10 errors in a row, stopped at", k, flush=True)
                pool.terminate()
                break
            if k % 100 == 0 or k == len(todo):
                print(k, "of", len(todo), "errors", bad, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
