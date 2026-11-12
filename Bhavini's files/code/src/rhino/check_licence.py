# -*- coding: utf-8 -*-
"""Write Rhino's licence type and expiry (no serial numbers) to logs/rhino/licence_log.txt, then close Rhino.
Run:  Rhino.exe /nosplash /runscript="_-RunPythonScript C:\\Bhavini\\AI\\ADs\\nomad\\src\\rhino\\check_licence.py"
"""
import traceback
import Rhino

LOG = r"C:\Bhavini\AI\ADs\nomad\logs\rhino\licence_log.txt"
A = Rhino.RhinoApp
with open(LOG, "w") as f:
    for name in ["Version", "InstallationType", "InstallationTypeString", "IsLicenseValidated",
                 "LicenseExpires", "DaysUntilExpiration", "ValidationGracePeriodDaysLeft",
                 "IsCloudZooNode", "LicenseUserOrganization"]:
        try:
            f.write("%s: %s\n" % (name, getattr(A, name)))
        except Exception:
            f.write("%s: (not available) %s\n" % (name, traceback.format_exc().splitlines()[-1]))
A.Exit()
