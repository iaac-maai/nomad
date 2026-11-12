# -*- coding: utf-8 -*-
"""Open rhino_grasshopper/NOMAD.gh in Grasshopper (run by OPEN_NOMAD.cmd after Rhino opens rhino_grasshopper/NOMAD.3dm)."""
import Rhino
gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
gh.LoadEditor()
gh.OpenDocument(r"C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\NOMAD.gh")
gh.ShowEditor()
