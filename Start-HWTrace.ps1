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
$exe = Join-Path $PSScriptRoot 'build/hwtrace.exe'
$filter = Join-Path $PSScriptRoot $config.filter
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Collector missing: $exe" }
if (-not (Test-Path -LiteralPath $filter -PathType Leaf)) { throw "Filter missing: $filter" }
$null = Get-Command ssh.exe -ErrorAction Stop
$processName = if ($config.process) { [string]$config.process } else { 'TM5.exe' }
$graceSeconds = if ($null -ne $config.grace_seconds) { [int]$config.grace_seconds } else { 600 }
if ($graceSeconds -lt 0 -or $graceSeconds -gt 86400) { throw 'grace_seconds must be between 0 and 86400.' }
& $exe $filter ([string]$config.ssh_command) $processName $graceSeconds
exit $LASTEXITCODE
