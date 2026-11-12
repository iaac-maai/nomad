# -*- coding: utf-8 -*-
"""Install Grasshopper packages for Rhino 7 from .yak files in nomad/tools/rhino_plugins/
(the same thing Rhino's Package Manager does: unzip to %APPDATA%\\McNeel\\Rhinoceros\\packages\\7.0\\<name>\\<version>
and write <name>\\manifest.txt with the active version). Runs inside Rhino, logs, then closes Rhino.
The packages load the next time Rhino starts."""
import os, zipfile, traceback
import Rhino

SRC = r"C:\Bhavini\AI\ADs\nomad\tools\rhino_grasshopper_plugins"
LOG = r"C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\logs\install_log.txt"
PKG = os.path.join(os.environ["APPDATA"], "McNeel", "Rhinoceros", "packages", "7.0")
PACKAGES = [("MagnetizingFloorPlanGeneration", "3.2.0", "MagnetizingFloorPlanGeneration-3.2.0-rh7_0-win.yak"),
            ("human-ui", "0.8.8", "human-ui-0.8.8-any-win.yak")]
# Not installed: PlanFinderGH needs Rhino 7.4+; MagnetizingFloorPlanGeneration is installed but needs a newer
# Rhino 7 than 7.1 to load. Decision 2026-10-28: stay on Rhino 7.1 (no update).

with open(LOG, "w") as log:
    try:
        for name, ver, fname in PACKAGES:
            dest = os.path.join(PKG, name, ver)
            if not os.path.isdir(dest):
                os.makedirs(dest)
            z = zipfile.ZipFile(os.path.join(SRC, fname))
            for member in z.namelist():
                if ".." in member or member.startswith(("/", "\\")):
                    raise Exception("unsafe path in package: " + member)
            z.extractall(dest)
            with open(os.path.join(PKG, name, "manifest.txt"), "w") as m:
                m.write(ver)
            log.write("installed %s %s -> %s (%d files)\n" % (name, ver, dest, len(z.namelist())))
    except Exception:
        log.write("ERROR\n" + traceback.format_exc())
Rhino.RhinoApp.Exit()
