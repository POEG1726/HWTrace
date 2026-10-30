param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
. (Join-Path $root 'Startup-Capture.ps1')
$fixture = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhuQAAAAASUVORK5CYII=')
$temp = Join-Path ([IO.Path]::GetTempPath()) ('HWTrace startup test ' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $pythonExe = (Get-Command $Python).Source
    $receiver = Join-Path $root 'receiver.py'
    $db = Join-Path $temp 'test.sqlite3'
    $command = '"' + $pythonExe + '" "' + $receiver + '" --db "' + $db + '" --ack'
    $id = [Guid]::NewGuid().ToString('N')
    Send-StartupScreenshot -SshCommand $command -Png $fixture -CaptureId $id -CapturedAt '2026-10-30T04:00:00Z' -ProcessName 'TM5.exe'
    $actual = [IO.File]::ReadAllBytes((Join-Path $temp "screenshots/$id.png"))
    if ([Convert]::ToBase64String($actual) -ne [Convert]::ToBase64String($fixture)) { throw 'Binary upload changed PNG bytes.' }
    $script:already = $false; $script:captures = 0; $script:uploads = 0
    function Get-MonitoredProcessPresent { param($ProcessName); return $script:already }
    function New-DesktopScreenshot { $script:captures++; return ,$fixture }
    function Send-StartupScreenshot { param($SshCommand,$Png,$CaptureId,$CapturedAt,$ProcessName); $script:uploads++ }
    $a = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test'
    if ($a.Event -ne 'startup_waiting_for_process' -or $script:captures -ne 0 -or $script:uploads -ne 0) { throw 'Absent process triggered capture.' }
    $script:already = $true
    $b = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test'
    if ($b.Event -ne 'startup_screenshot_uploaded' -or $script:captures -ne 1 -or $script:uploads -ne 1) { throw 'Existing process must capture and upload once.' }
    function Send-StartupScreenshot { param($SshCommand,$Png,$CaptureId,$CapturedAt,$ProcessName); throw 'simulated receiver outage' }
    $c = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test' -WarningAction SilentlyContinue
    if ($c.Event -ne 'startup_screenshot_failed') { throw 'Capture upload failure must return a failure status without blocking collection.' }
    Write-Host 'PowerShell binary upload and startup branches: OK (synthetic PNG; no desktop capture).'
} finally {
    $resolved = [IO.Path]::GetFullPath($temp)
    $expectedParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($expectedParent,[StringComparison]::OrdinalIgnoreCase) -or -not ([IO.Path]::GetFileName($resolved)).StartsWith('HWTrace startup test ')) { throw 'Unexpected test cleanup path.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
