@echo off
rem Opens the one NOMAD Rhino file with the one NOMAD Grasshopper file loaded.
start "" "C:\Program Files\Rhino 7\System\Rhino.exe" /nosplash "C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\NOMAD.3dm" /runscript="_-RunPythonScript C:\Bhavini\AI\ADs\nomad\rhino_grasshopper\code\open_nomad.py"
