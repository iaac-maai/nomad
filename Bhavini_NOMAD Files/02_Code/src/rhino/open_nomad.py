# -*- coding: utf-8 -*-
"""Open grasshopper/NOMAD.gh in Grasshopper (run by OPEN_NOMAD.cmd after Rhino opens rhino/NOMAD.3dm)."""
import Rhino
gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
gh.LoadEditor()
gh.OpenDocument(r"C:\Bhavini\AI\ADs\nomad\grasshopper\NOMAD.gh")
gh.ShowEditor()
