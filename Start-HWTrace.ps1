[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'collector.json')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Create collector.json from collector.example.json and configure the receiver SSH command first. Missing: $ConfigPath"
}
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($config.ssh_command) -or $config.ssh_command.Contains('CHANGE_ME')) {
    throw 'Set ssh_command to a verified, noninteractive receiver command with --ack.'
}
$relativeExe = if ($config.executable) { [string]$config.executable } else { 'build/hwtrace.exe' }
$exe = Join-Path $PSScriptRoot $relativeExe
$filter = Join-Path $PSScriptRoot $config.filter
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Collector missing: $exe" }
if (-not (Test-Path -LiteralPath $filter -PathType Leaf)) { throw "Filter missing: $filter" }
$null = Get-Command ssh.exe -ErrorAction Stop
$processName = if ($config.process) { [string]$config.process } else { 'TM5.exe,y-cruncher.exe' }
$graceSeconds = if ($null -ne $config.grace_seconds) { [int]$config.grace_seconds } else { 600 }
if ($graceSeconds -lt 0 -or $graceSeconds -gt 86400) { throw 'grace_seconds must be between 0 and 86400.' }
. (Join-Path $PSScriptRoot 'Startup-Capture.ps1')
$context = Initialize-StartupContext -ProcessName $processName -SshCommand ([string]$config.ssh_command) -CollectorPath $exe
Write-Host 'Collection elapsed time starts when the native collector launches (500 ms sampling).'
$collectorExit = 1
try {
    & $exe $filter ([string]$config.ssh_command) $processName $graceSeconds $context.Id $context.Event
    $collectorExit = $LASTEXITCODE
} finally {
    if ($context.Worker) { $context.Worker.Dispose() }
}
exit $collectorExit
