# -*- coding: utf-8 -*-
"""List the Grasshopper plug-in libraries Rhino 7 loaded (and how many components each has).
Writes logs/rhino/plugins_log.txt, then closes Rhino. Run with Rhino.exe /runscript."""
import os, traceback, collections
import Rhino, clr

LOG = r"C:\Bhavini\AI\ADs\nomad\logs\rhino\plugins_log.txt"
try:
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    gh.LoadEditor()
    clr.AddReference("Grasshopper")
    import Grasshopper as GH
    counts = collections.Counter()
    for proxy in GH.Instances.ComponentServer.ObjectProxies:
        counts[proxy.Desc.Category] += 1
    with open(LOG, "w") as f:
        for lib in GH.Instances.ComponentServer.Libraries:
            f.write("library: %s %s | %s\n" % (lib.Name, lib.Version, lib.Location))
        for cat, n in sorted(counts.items()):
            f.write("category: %s (%d components)\n" % (cat, n))
except Exception:
    with open(LOG, "w") as f:
        f.write("ERROR\n" + traceback.format_exc())
Rhino.RhinoApp.Exit()
