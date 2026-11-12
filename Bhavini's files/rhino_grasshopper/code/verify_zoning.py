# -*- coding: utf-8 -*-
"""Check, inside Rhino (IronPython 2.7), that Step 3 zoning works the way NOMAD.gh uses it. Closes Rhino.
Run: powershell -File rhino_grasshopper\code\run_in_rhino.ps1 -Script <this file> -Done C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\logs\zoning_log.txt"""
import os, sys, traceback
import Rhino
import scriptcontext as sc
ROOT = r"C:\Bhavini\AI\ADs\nomad"
sys.path[:0] = [os.path.join(ROOT, "rhino_grasshopper", "code"), os.path.join(ROOT, "7_floor_plans", "code"), os.path.join(ROOT, "6_check_the_shop", "code")]
LOG = os.path.join(ROOT, "rhino_grasshopper", "logs", "zoning_log.txt")


def log(m):
    with open(LOG, "a") as f:
        f.write((m if isinstance(m, str) else m.encode("utf-8")) + "\n")


open(LOG, "w").close()
try:
    import nomad_core as core
    for q in (u"2249707DF3824G", u"Valencia 640", u"València 640", u"nowhere 1"):
        r = core.zoning_lookup(q)
        log(u"%s -> %s" % (q, (u"%s %s | %s | %s" % (r["street"], r["num"], r["zone"], r["housing"])) if r else u"None"))
    shop = core.shop_by_id(146519)
    log(core.add_zoning(shop, u"Valencia 640").strip())
    case = core.run(shop, {"1bed": 2, "2bed": 1})
    log("verdict %s, first card %s" % (case["after"]["res"]["verdict"], case["after"]["res"]["cards"][0]["title"]))
except Exception:
    log("ERROR\n" + traceback.format_exc())
log("done")
sc.doc.Modified = False
Rhino.RhinoApp.Exit()
