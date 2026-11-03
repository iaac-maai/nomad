@echo off
rem Opens the one NOMAD Rhino file with the one NOMAD Grasshopper file loaded.
start "" "C:\Program Files\Rhino 7\System\Rhino.exe" /nosplash "C:\Bhavini\AI\ADs\nomad\rhino\NOMAD.3dm" /runscript="_-RunPythonScript C:\Bhavini\AI\ADs\nomad\src\rhino\open_nomad.py"
