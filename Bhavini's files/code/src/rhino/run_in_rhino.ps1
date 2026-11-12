# Nomad - run one Python script in a separate, self-closing Rhino 7 (never the user's NOMAD window).
# Why: since a plug-in update (D5 LiveSync), Rhino ignores /runscript at start-up. So we start Rhino
# with no file, wait until its command line is ready, and type the RunPythonScript command into it.
# Usage: powershell -File src\rhino\run_in_rhino.ps1 -Script C:\...\script.py -Done C:\...\log.txt [-TimeoutSec 600]
param([Parameter(Mandatory)][string]$Script, [Parameter(Mandatory)][string]$Done, [int]$TimeoutSec = 600)

Add-Type @"
using System; using System.Runtime.InteropServices;
public class NomadRhinoKeys { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l); }
"@

if (Test-Path $Done) { Remove-Item $Done }
$before = @(Get-Process Rhino -ErrorAction SilentlyContinue | ForEach-Object Id)
$p = Start-Process "C:\Program Files\Rhino 7\System\Rhino.exe" -ArgumentList "/nosplash" -PassThru
# wait for the main window titled "Untitled", then for plug-ins to finish loading
$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt 180) {
    $p.Refresh()
    if ($p.MainWindowHandle -ne 0 -and $p.MainWindowTitle -like "Untitled*") { break }
    Start-Sleep 2
}
Start-Sleep 25
$cmd = "_-RunPythonScript `"$Script`"`r"
# type the command; if the script has not started (no log yet) after 60 s, Rhino was still busy: type it again (3 tries)
for ($try = 1; $try -le 3; $try++) {
    foreach ($c in $cmd.ToCharArray()) { [NomadRhinoKeys]::PostMessage($p.MainWindowHandle, 0x0102, [IntPtr][int]$c, [IntPtr]0) | Out-Null }
    $t1 = Get-Date
    while (((Get-Date) - $t1).TotalSeconds -lt 60 -and -not (Test-Path $Done) -and -not $p.HasExited) { Start-Sleep 3 }
    if (Test-Path $Done) { break }
    [NomadRhinoKeys]::PostMessage($p.MainWindowHandle, 0x0100, [IntPtr]0x1B, [IntPtr]0) | Out-Null   # Esc: clear the command line
}
# wait until the script's log ends with "done" (or Rhino closes); then make sure this Rhino is gone
while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec -and -not $p.HasExited) {
    if ((Test-Path $Done) -and ((Get-Content $Done -Tail 1) -match "^(done|ERROR)")) { break }
    Start-Sleep 3
}
Start-Sleep 8
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
Start-Sleep 3
# Rhino may reopen itself after a hard stop: close any new Untitled Rhino that is not the user's
Get-Process Rhino -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id -and $_.MainWindowTitle -like "Untitled*" } | Stop-Process -Force
if (Test-Path $Done) { Get-Content $Done } else { "no log written: $Done" }
