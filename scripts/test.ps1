[CmdletBinding()]
param([string]$Compiler, [string]$Python = 'python', [string]$Node = 'node', [switch]$UseWsl, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
Push-Location $root
try {
    if (-not $SkipBuild) { & "$PSScriptRoot/build.ps1" -Compiler $Compiler -UseWsl:$UseWsl -Tests }
    $pythonExe = (Get-Command $Python -ErrorAction Stop).Source
    & $pythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Python/native-output tests failed.' }
    $nodeExe = (Get-Command $Node -ErrorAction Stop).Source
    & $nodeExe tests/test_dashboard_ui.js
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard interaction tests failed.' }
    foreach ($name in @('units', 'profile', 'start_gate', 'process')) {
        & (Join-Path $root "build/test_native_$name.exe")
        if ($LASTEXITCODE -ne 0) { throw "Native test failed: $name" }
    }
    & pwsh -NoLogo -NoProfile -File tests/test_startup_capture.ps1 -Python $pythonExe
    if ($LASTEXITCODE -ne 0) { throw 'PowerShell screenshot/startup tests failed.' }
    Write-Host 'All available checks passed. No desktop screenshot or stress tool was used.'
} finally { Pop-Location }
